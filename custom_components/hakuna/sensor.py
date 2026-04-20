"""Sensor entities for Hakuna integration."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, VERSION
from .coordinator import HakunaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# A deliberately small, opinionated set of sensors. We used to expose
# seconds / hours / minutes variants of everything plus every possible
# absence sub-field — it created a noisy entity list without actually
# being useful. The kept sensors are the ones that answer the questions
# users typically ask: how many hours, when's my vacation, am I clocked in.

SENSOR_DESCRIPTIONS = [
    # Overtime: the formatted string users actually read, plus a numeric
    # hours variant that can be graphed in the more-info panel.
    SensorEntityDescription(
        key="overtime",
        name="Überstunden",
        icon="mdi:clock-plus-outline",
    ),
    SensorEntityDescription(
        key="overtime_hours",
        name="Überstunden (Stunden)",
        icon="mdi:clock-plus-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),

    # Vacation balance as Hakuna itself reports it.
    SensorEntityDescription(
        key="vacation_remaining",
        name="Resturlaub",
        icon="mdi:beach",
        native_unit_of_measurement="Tage",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="vacation_redeemed",
        # Named "Urlaub genommen" (not "Genommener Urlaub") so the device
        # info view lists it *after* "Resturlaub" alphabetically — users
        # read the remaining balance first and the consumed amount below.
        name="Urlaub genommen",
        icon="mdi:calendar-check",
        native_unit_of_measurement="Tage",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),

    # Current timer — a formatted duration for display and a timestamp for
    # "started 4 hours ago" style cards.
    SensorEntityDescription(
        key="timer_duration",
        name="Timer Dauer",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="timer_start_time",
        name="Timer Startzeit",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),

    # Worked-time aggregates (derived from time entries + running timer).
    SensorEntityDescription(
        key="worked_today_hours",
        name="Gearbeitet heute",
        icon="mdi:calendar-today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="worked_week_hours",
        name="Gearbeitet diese Woche",
        icon="mdi:calendar-week",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="worked_month_hours",
        name="Gearbeitet diesen Monat",
        icon="mdi:calendar-month",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),

    # Next vacation — just the start date (as a timestamp) and the
    # countdown in days. Users who want end-dates or per-type tracking can
    # build a template sensor from the `upcoming` attribute below.
    SensorEntityDescription(
        key="next_vacation_start",
        name="Nächster Urlaub",
        icon="mdi:beach",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="next_vacation_days_until",
        name="Tage bis zum Urlaub",
        icon="mdi:beach",
        native_unit_of_measurement="Tage",
        state_class=SensorStateClass.MEASUREMENT,
    ),

    # Target hours (what you "should" work in the current period) and the
    # progress percentage. Both target sensors expose the full-period
    # target (whole week / whole month) as an attribute so dashboards can
    # show "8h 28m / 42h 30m" kind of numbers.
    SensorEntityDescription(
        key="target_week_hours",
        name="Sollzeit diese Woche",
        icon="mdi:target",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="target_month_hours",
        name="Sollzeit diesen Monat",
        icon="mdi:target",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="progress_week_percent",
        name="Fortschritt Woche",
        icon="mdi:percent",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="progress_month_percent",
        name="Fortschritt Monat",
        icon="mdi:percent",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hakuna sensors."""
    coordinator: HakunaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        HakunaSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class HakunaSensor(CoordinatorEntity[HakunaDataUpdateCoordinator], SensorEntity):
    """Representation of a Hakuna sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HakunaDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Hakuna",
            manufacturer="Hakuna AG",
            model="Time Tracking",
            sw_version=VERSION,
            entry_type="service",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        key = self.entity_description.key
        data = self.coordinator.data
        overview = data.get("overview", {}) or {}
        timer = data.get("timer")

        # Overtime
        if key == "overtime":
            return overview.get("overtime")
        if key == "overtime_hours":
            seconds = overview.get("overtime_in_seconds")
            if seconds is None:
                return None
            return round(seconds / 3600, 2)

        # Vacation balance
        if key == "vacation_remaining":
            return (overview.get("vacation") or {}).get("remaining_days")
        if key == "vacation_redeemed":
            return (overview.get("vacation") or {}).get("redeemed_days")

        # Timer
        if key == "timer_duration":
            return timer.get("duration") if timer else None
        if key == "timer_start_time":
            return _timer_start_datetime(timer)

        # Worked-time aggregates
        if key == "worked_today_hours":
            return round((data.get("worked_today_seconds") or 0) / 3600, 2)
        if key == "worked_week_hours":
            return round((data.get("worked_week_seconds") or 0) / 3600, 2)
        if key == "worked_month_hours":
            return round((data.get("worked_month_seconds") or 0) / 3600, 2)

        # Next vacation
        if key == "next_vacation_start":
            a = _next_vacation(data)
            return _to_midnight_dt(a.get("start_date")) if a else None
        if key == "next_vacation_days_until":
            a = _next_vacation(data)
            return _days_until(a.get("start_date")) if a else None

        # Target / progress
        if key == "target_week_hours":
            return data.get("target_week_hours")
        if key == "target_month_hours":
            return data.get("target_month_hours")
        if key == "progress_week_percent":
            return _percent(
                data.get("worked_week_seconds"),
                data.get("target_week_hours"),
            )
        if key == "progress_month_percent":
            return _percent(
                data.get("worked_month_seconds"),
                data.get("target_month_hours"),
            )

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs: dict[str, Any] = {}
        key = self.entity_description.key
        data = self.coordinator.data

        if data is None:
            return attrs

        overview = data.get("overview", {}) or {}
        timer = data.get("timer")

        # Cross-reference the different overtime representations.
        if key == "overtime":
            seconds = overview.get("overtime_in_seconds")
            if seconds is not None:
                attrs["seconds"] = seconds
                attrs["hours"] = round(seconds / 3600, 2)
        if key == "overtime_hours":
            if overview.get("overtime") is not None:
                attrs["formatted"] = overview.get("overtime")

        # Surface the notes / project / task on the timer_duration sensor
        # so users don't need a second sensor just to see them.
        if key == "timer_duration" and timer:
            attrs["note"] = timer.get("note") or None
            user = timer.get("user") or {}
            attrs["user_name"] = user.get("name")
            task = timer.get("task") or {}
            attrs["task"] = task.get("name")
            project = timer.get("project")
            if isinstance(project, dict):
                attrs["project"] = project.get("name")
            elif project:
                attrs["project"] = str(project)

        # Expose the upcoming absences list alongside the countdown so
        # dashboards can iterate without a separate entity for every piece.
        if key in ("next_vacation_start", "next_vacation_days_until", "vacation_remaining"):
            upcoming = data.get("upcoming_absences") or []
            attrs["upcoming"] = [_summarize_absence(a) for a in upcoming[:10]]
            a = _next_vacation(data)
            if a:
                attrs["next_vacation"] = _summarize_absence(a)
            next_any = _next_absence(data)
            if next_any:
                attrs["next_absence"] = _summarize_absence(next_any)

        # Target sensors: expose the full-period target so dashboards can
        # render "8.3h / 42.5h" style numbers.
        if key == "target_week_hours":
            attrs["full_week_hours"] = data.get("target_week_full_hours")
            attrs["daily_target_hours"] = data.get("daily_target_hours")
            attrs["work_days"] = data.get("work_days")
        if key == "target_month_hours":
            attrs["full_month_hours"] = data.get("target_month_full_hours")
            attrs["daily_target_hours"] = data.get("daily_target_hours")
            attrs["work_days"] = data.get("work_days")

        # Progress sensors: expose worked/target in a convenient form.
        if key == "progress_week_percent":
            attrs["worked_hours"] = round(
                (data.get("worked_week_seconds") or 0) / 3600, 2
            )
            attrs["target_hours"] = data.get("target_week_hours")
            attrs["full_week_hours"] = data.get("target_week_full_hours")
        if key == "progress_month_percent":
            attrs["worked_hours"] = round(
                (data.get("worked_month_seconds") or 0) / 3600, 2
            )
            attrs["target_hours"] = data.get("target_month_hours")
            attrs["full_month_hours"] = data.get("target_month_full_hours")

        return attrs


# ==================== Module helpers ====================

def _timer_start_datetime(timer: dict[str, Any] | None) -> datetime | None:
    """Parse a timer's start date+time into an aware datetime."""
    if not timer:
        return None
    date_str = timer.get("date")
    time_str = timer.get("start_time")
    if not (date_str and time_str):
        return None
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt_util.as_local(dt.replace(tzinfo=dt_util.get_default_time_zone()))
    except ValueError as err:
        _LOGGER.warning(
            "Could not parse Hakuna timer start time '%s %s': %s",
            date_str, time_str, err,
        )
        return None


def _to_midnight_dt(date_str: str | None) -> datetime | None:
    """Convert an ISO date string to a tz-aware datetime at local midnight."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return None
    dt = datetime(d.year, d.month, d.day, 0, 0, 0)
    return dt_util.as_local(dt.replace(tzinfo=dt_util.get_default_time_zone()))


def _days_until(date_str: str | None) -> int | None:
    """Return whole days from today until the given date."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return None
    return (d - date.today()).days


def _upcoming_only_in_future(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return absences that start today or later."""
    today = date.today()
    out: list[dict[str, Any]] = []
    for a in data.get("upcoming_absences") or []:
        try:
            start = date.fromisoformat(a.get("start_date") or "")
        except ValueError:
            continue
        if start >= today:
            out.append(a)
    return out


def _next_vacation(data: dict[str, Any]) -> dict[str, Any] | None:
    """First upcoming absence where absence_type.is_vacation is true."""
    for a in _upcoming_only_in_future(data):
        atype = a.get("absence_type") or {}
        if atype.get("is_vacation"):
            return a
    return None


def _next_absence(data: dict[str, Any]) -> dict[str, Any] | None:
    """First upcoming absence regardless of type."""
    entries = _upcoming_only_in_future(data)
    return entries[0] if entries else None


def _percent(worked_seconds: float | int | None, target_hours: float | None) -> int | None:
    """Return worked/target as an integer percent, or None when undefined."""
    if worked_seconds is None or not target_hours or target_hours <= 0:
        return None
    return round((worked_seconds / 3600) / target_hours * 100)


def _summarize_absence(absence: dict[str, Any]) -> dict[str, Any]:
    """Compact dict of the fields dashboards typically need."""
    atype = absence.get("absence_type") or {}
    return {
        "start_date": absence.get("start_date"),
        "end_date": absence.get("end_date"),
        "type": atype.get("name"),
        "is_vacation": atype.get("is_vacation"),
        "first_half_day": absence.get("first_half_day"),
        "second_half_day": absence.get("second_half_day"),
    }
