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
        daily_target_hours: float = 8.5,
        work_days: set[int] | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            api_client: Hakuna API client.
            update_interval: How often to refresh data.
            daily_target_hours: Expected hours per work day (e.g. 8.5).
            work_days: Set of ISO weekday numbers (0=Mon..6=Sun) that
                count as work days for target computation. Defaults to
                Mon-Fri.
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Hakuna",
            update_interval=update_interval,
        )
        self.api_client = api_client
        self.daily_target_hours = daily_target_hours
        self.work_days = work_days if work_days else {0, 1, 2, 3, 4}

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

            # Compute target hours for this week / month.
            # Target = daily_target × number of work days in the period,
            # minus days that are fully covered by an absence that grants
            # work time (vacation, sick days, etc. — the day is "paid
            # without needing to work").
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            month_start = today.replace(day=1)

            target_week_hours = _target_hours(
                week_start,
                min(week_end, today),
                self.work_days,
                self.daily_target_hours,
                absences_year,
            )
            target_month_hours = _target_hours(
                month_start,
                today,
                self.work_days,
                self.daily_target_hours,
                absences_year,
            )
            # Full-period targets (whole week / whole month) so dashboards
            # can show "45h of 42.5h" instead of the progressive target.
            target_week_full_hours = _target_hours(
                week_start,
                week_end,
                self.work_days,
                self.daily_target_hours,
                absences_year,
            )
            try:
                last_day = (month_start.replace(month=month_start.month + 1)
                            - timedelta(days=1))
            except ValueError:
                last_day = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
            target_month_full_hours = _target_hours(
                month_start,
                last_day,
                self.work_days,
                self.daily_target_hours,
                absences_year,
            )

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
                "target_week_hours": target_week_hours,
                "target_month_hours": target_month_hours,
                "target_week_full_hours": target_week_full_hours,
                "target_month_full_hours": target_month_full_hours,
                "daily_target_hours": self.daily_target_hours,
                "work_days": sorted(self.work_days),
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


def _target_hours(
    start: date,
    end: date,
    work_days: set[int],
    daily_target: float,
    absences: list[dict[str, Any]],
) -> float:
    """Compute the expected work hours in the given inclusive date range.

    For each calendar day in [start, end]:
      * Skip days whose weekday is NOT in `work_days`.
      * If a day is fully or half covered by an absence whose type has
        `grants_work_time=true` (Ferien, Krankheit, Feiertag, ...), the
        corresponding hours are deducted from the target. Half-day
        absences deduct half the daily target.

    Returns the net target in hours.
    """
    if end < start:
        return 0.0

    total = 0.0
    cur = start
    while cur <= end:
        if cur.weekday() in work_days:
            absence_factor = _absence_factor_for_day(cur, absences)
            total += daily_target * (1.0 - absence_factor)
        cur += timedelta(days=1)
    return round(total, 2)


def _absence_factor_for_day(
    day: date, absences: list[dict[str, Any]]
) -> float:
    """Return how much of a work day is covered by granted absences.

    0.0 = nothing, work full day.
    0.5 = half the day is absence-covered.
    1.0 = full day absence (vacation, sick, ...).
    """
    covered = 0.0
    for a in absences:
        atype = a.get("absence_type") or {}
        if not atype.get("grants_work_time"):
            continue
        start = _parse_date(a.get("start_date"))
        end = _parse_date(a.get("end_date"))
        if not (start and end and start <= day <= end):
            continue

        # Only a single-day absence can be a half day; multi-day ranges
        # cover the full day.
        if start == end:
            first = bool(a.get("first_half_day"))
            second = bool(a.get("second_half_day"))
            if first and second:
                covered = max(covered, 1.0)
            elif first or second:
                covered = max(covered, 0.5)
            else:
                # Neither flag set → treat as full day
                covered = max(covered, 1.0)
        else:
            covered = max(covered, 1.0)

    return min(covered, 1.0)


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


