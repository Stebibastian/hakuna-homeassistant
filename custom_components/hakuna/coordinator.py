"""Data update coordinator for Hakuna."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HakunaApiClient, HakunaApiError, HakunaAuthError

_LOGGER = logging.getLogger(__name__)


class HakunaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Hakuna data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: HakunaApiClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Hakuna",
            update_interval=update_interval,
        )
        self.api_client = api_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hakuna API."""
        try:
            today = date.today()
            month_start = today.replace(day=1)
            # Monday of current week
            week_start = today - timedelta(days=today.weekday())

            # Core data
            timer = await self.api_client.get_timer()
            overview = await self.api_client.get_overview()

            # Absences for the full year (used for today's status + upcoming list)
            try:
                absences_year = await self.api_client.get_absences(year=today.year)
            except HakunaApiError as err:
                _LOGGER.debug("Could not fetch absences: %s", err)
                absences_year = []

            # Time entries for the current month (derive week/today from that)
            try:
                time_entries_month = await self.api_client.get_time_entries(
                    start_date=month_start,
                    end_date=today,
                )
            except HakunaApiError as err:
                _LOGGER.debug("Could not fetch time entries: %s", err)
                time_entries_month = []

            # Optional: presence/users/tasks (best-effort)
            try:
                presence = await self.api_client.get_presence()
            except HakunaApiError:
                presence = []

            try:
                users = await self.api_client.get_users()
            except HakunaApiError:
                users = []

            try:
                tasks = await self.api_client.get_tasks()
            except HakunaApiError:
                tasks = []

            # Find default task for the start-timer button
            default_task_id = None
            for task in tasks:
                if task.get("default") and not task.get("archived"):
                    default_task_id = task.get("id")
                    break
            if default_task_id is None and tasks:
                for task in tasks:
                    if not task.get("archived"):
                        default_task_id = task.get("id")
                        break

            # Derive today's absence from the year list
            absence_today = _find_absence_for_date(absences_year, today)

            # Sum worked time from time entries (finished entries)
            worked_today_seconds = _sum_duration(
                _filter_entries_by_date(time_entries_month, today, today)
            )
            worked_week_seconds = _sum_duration(
                _filter_entries_by_date(time_entries_month, week_start, today)
            )
            worked_month_seconds = _sum_duration(time_entries_month)

            # Add current running timer duration (best-effort)
            if timer and timer.get("duration_in_seconds"):
                running = int(timer.get("duration_in_seconds") or 0)
                worked_today_seconds += running
                worked_week_seconds += running
                worked_month_seconds += running

            # Compute upcoming absences (future-only, sorted)
            upcoming = _upcoming_absences(absences_year, today)

            # Compute vacation days taken this year (from past absences of type is_vacation)
            vacation_days_taken_year = _vacation_days_taken(absences_year, today)

            return {
                "timer": timer,
                "overview": overview,
                "presence": presence,
                "users": users,
                "tasks": tasks,
                "default_task_id": default_task_id,
                "timer_running": timer is not None,
                "absences_year": absences_year,
                "absence_today": absence_today or {"absent": False},
                "time_entries_month": time_entries_month,
                "worked_today_seconds": worked_today_seconds,
                "worked_week_seconds": worked_week_seconds,
                "worked_month_seconds": worked_month_seconds,
                "upcoming_absences": upcoming,
                "vacation_days_taken_year": vacation_days_taken_year,
            }

        except HakunaAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except HakunaApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err


# ==================== Helpers ====================

def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string safely."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _filter_entries_by_date(
    entries: list[dict[str, Any]],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Return entries whose date is within [start, end] inclusive."""
    out: list[dict[str, Any]] = []
    for e in entries:
        d = _parse_date(e.get("date"))
        if d and start <= d <= end:
            out.append(e)
    return out


def _sum_duration(entries: list[dict[str, Any]]) -> int:
    """Sum duration_in_seconds across entries, defensively."""
    total = 0
    for e in entries:
        secs = e.get("duration_in_seconds")
        if secs is None:
            continue
        try:
            total += int(secs)
        except (TypeError, ValueError):
            continue
    return total


def _find_absence_for_date(
    absences: list[dict[str, Any]], target: date
) -> dict[str, Any] | None:
    """Return a structured description if there is an absence covering `target`."""
    for a in absences:
        start = _parse_date(a.get("start_date"))
        end = _parse_date(a.get("end_date"))
        if start and end and start <= target <= end:
            atype = a.get("absence_type") or {}
            return {
                "absent": True,
                "type": atype.get("name"),
                "is_vacation": atype.get("is_vacation"),
                "first_half_day": a.get("first_half_day"),
                "second_half_day": a.get("second_half_day"),
                "start_date": a.get("start_date"),
                "end_date": a.get("end_date"),
            }
    return None


def _upcoming_absences(
    absences: list[dict[str, Any]], today: date
) -> list[dict[str, Any]]:
    """Return all absences that have not ended yet, sorted by start date."""
    def key(a: dict[str, Any]) -> str:
        return a.get("start_date") or "9999-12-31"

    out: list[dict[str, Any]] = []
    for a in absences:
        end = _parse_date(a.get("end_date"))
        if end and end >= today:
            out.append(a)
    out.sort(key=key)
    return out


def _vacation_days_taken(
    absences: list[dict[str, Any]], today: date
) -> float:
    """Count vacation days already taken this year (before today).

    Counts half-days as 0.5 days.
    """
    total = 0.0
    for a in absences:
        atype = a.get("absence_type") or {}
        if not atype.get("is_vacation"):
            continue
        start = _parse_date(a.get("start_date"))
        end = _parse_date(a.get("end_date"))
        if not (start and end):
            continue
        # Only count days that have already passed
        effective_end = min(end, today - timedelta(days=1))
        if effective_end < start:
            continue
        days = (effective_end - start).days + 1
        # Half-day adjustment only applies if the absence is a single day
        if start == end:
            halves = 0
            if a.get("first_half_day"):
                halves += 1
            if a.get("second_half_day"):
                halves += 1
            if halves == 1:
                days = 0.5
        total += days
    return total
