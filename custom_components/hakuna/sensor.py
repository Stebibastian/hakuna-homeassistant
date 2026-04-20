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


SENSOR_DESCRIPTIONS = [
    # ==================== Overtime ====================
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
    SensorEntityDescription(
        key="overtime_seconds",
        name="Überstunden (Sekunden)",
        icon="mdi:clock-plus-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # ==================== Vacation ====================
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
        name="Genommener Urlaub",
        icon="mdi:calendar-check",
        native_unit_of_measurement="Tage",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # ==================== Timer ====================
    SensorEntityDescription(
        key="timer_duration",
        name="Timer Dauer",
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="timer_duration_hours",
        name="Timer Dauer (Stunden)",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="timer_duration_seconds",
        name="Timer Dauer (Sekunden)",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="timer_start_time",
        name="Timer Startzeit",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="timer_project",
        name="Timer Projekt",
        icon="mdi:folder-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="timer_task",
        name="Timer Aufgabe",
        icon="mdi:checkbox-marked-outline",
        entity_registry_enabled_default=False,
    ),
    # ==================== Worked time aggregates ====================
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
    # ==================== Upcoming absences ====================
    SensorEntityDescription(
        key="next_vacation_start",
        name="Nächster Urlaub (Start)",
        icon="mdi:beach",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="next_vacation_end",
        name="Nächster Urlaub (Ende)",
        icon="mdi:beach",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_vacation_days_until",
        name="Tage bis zum Urlaub",
        icon="mdi:beach",
        native_unit_of_measurement="Tage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Non-vacation absence tracking (Home Office, Kompensation, ...).
    # Disabled by default — enable individually if you want dashboards for
    # non-vacation absences. When the next absence is a vacation these
    # sensors will carry the same value as the next_vacation_* ones, so
    # keeping them off avoids duplicate noise for most users.
    SensorEntityDescription(
        key="next_absence_start",
        name="Nächste Abwesenheit (Start)",
        icon="mdi:calendar-alert",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_absence_end",
        name="Nächste Abwesenheit (Ende)",
        icon="mdi:calendar-alert",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_absence_type",
        name="Nächste Abwesenheit (Typ)",
        icon="mdi:calendar-alert",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_absence_days_until",
        name="Tage bis zur Abwesenheit",
        icon="mdi:calendar-alert",
        native_unit_of_measurement="Tage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # ==================== Team / Company ====================
    SensorEntityDescription(
        key="managed_users_count",
        name="Verwaltbare Personen",
        icon="mdi:account-group",
        native_unit_of_measurement="Personen",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
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

    # ------------------------------------------------------------------
    # native_value
    # ------------------------------------------------------------------

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
        if key == "overtime_seconds":
            return overview.get("overtime_in_seconds")

        # Vacation
        if key == "vacation_remaining":
            return (overview.get("vacation") or {}).get("remaining_days")
        if key == "vacation_redeemed":
            return (overview.get("vacation") or {}).get("redeemed_days")

        # Timer
        if key == "timer_duration":
            return timer.get("duration") if timer else None
        if key == "timer_duration_hours":
            if not timer:
                return None
            seconds = timer.get("duration_in_seconds")
            if seconds is None:
                return None
            return round(seconds / 3600, 2)
        if key == "timer_duration_seconds":
            return timer.get("duration_in_seconds") if timer else None
        if key == "timer_start_time":
            return _timer_start_datetime(timer)
        if key == "timer_project":
            if timer and timer.get("project"):
                project = timer["project"]
                if isinstance(project, dict):
                    return project.get("name")
                return str(project)
            return None
        if key == "timer_task":
            if timer and timer.get("task"):
                return timer["task"].get("name")
            return None

        # Worked time aggregates (seconds -> hours, 2 decimals)
        if key == "worked_today_hours":
            return round((data.get("worked_today_seconds") or 0) / 3600, 2)
        if key == "worked_week_hours":
            return round((data.get("worked_week_seconds") or 0) / 3600, 2)
        if key == "worked_month_hours":
            return round((data.get("worked_month_seconds") or 0) / 3600, 2)

        # Upcoming absences
        if key in (
            "next_vacation_start",
            "next_vacation_end",
            "next_vacation_days_until",
        ):
            absence = _next_absence(data, vacation_only=True)
            if not absence:
                return None
            if key == "next_vacation_start":
                return _to_midnight_dt(absence.get("start_date"))
            if key == "next_vacation_end":
                return _to_midnight_dt(absence.get("end_date"))
            if key == "next_vacation_days_until":
                return _days_until(absence.get("start_date"))

        if key in (
            "next_absence_start",
            "next_absence_end",
            "next_absence_type",
            "next_absence_days_until",
        ):
            absence = _next_absence(data, vacation_only=False)
            if not absence:
                return None
            if key == "next_absence_start":
                return _to_midnight_dt(absence.get("start_date"))
            if key == "next_absence_end":
                return _to_midnight_dt(absence.get("end_date"))
            if key == "next_absence_type":
                return (absence.get("absence_type") or {}).get("name")
            if key == "next_absence_days_until":
                return _days_until(absence.get("start_date"))

        # Team
        if key == "managed_users_count":
            users = data.get("users") or []
            return len(users)

        return None

    # ------------------------------------------------------------------
    # extra_state_attributes
    # ------------------------------------------------------------------

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

        # Overtime variants cross-reference each other
        if key == "overtime":
            seconds = overview.get("overtime_in_seconds")
            if seconds is not None:
                attrs["seconds"] = seconds
                attrs["hours"] = round(seconds / 3600, 2)
        if key in ("overtime_hours", "overtime_seconds"):
            if overview.get("overtime") is not None:
                attrs["formatted"] = overview.get("overtime")

        # Timer metadata
        if key == "timer_duration" and timer:
            attrs["note"] = timer.get("note")
            user = timer.get("user") or {}
            if user:
                attrs["user_name"] = user.get("name")
                attrs["user_id"] = user.get("id")

        # Expose list of upcoming absences on both the vacation-remaining sensor
        # (for easy dashboard template access) and on the next_* sensors.
        if key in (
            "vacation_remaining",
            "next_vacation_start",
            "next_absence_start",
        ):
            upcoming = data.get("upcoming_absences") or []
            attrs["upcoming"] = [_summarize_absence(a) for a in upcoming[:10]]

        # Next vacation/absence sensors expose the raw absence dict
        if key.startswith("next_vacation"):
            a = _next_absence(data, vacation_only=True)
            if a:
                attrs["absence"] = _summarize_absence(a)
        if key.startswith("next_absence"):
            a = _next_absence(data, vacation_only=False)
            if a:
                attrs["absence"] = _summarize_absence(a)

        # Managed users list
        if key == "managed_users_count":
            users = data.get("users") or []
            attrs["names"] = [u.get("name") for u in users if u.get("name")]

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
    """Return whole days from today until the given date (0 if today, negative if past)."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return None
    return (d - date.today()).days


def _next_absence(data: dict[str, Any], *, vacation_only: bool) -> dict[str, Any] | None:
    """Return the first upcoming absence (optionally vacation-only)."""
    upcoming = data.get("upcoming_absences") or []
    today = date.today()
    for a in upcoming:
        start = a.get("start_date")
        try:
            start_d = date.fromisoformat(start) if start else None
        except ValueError:
            start_d = None
        # Only count absences that start today or in the future — skip ongoing
        # ones that started in the past (they would pollute the "next" value).
        if start_d is None or start_d < today:
            continue
        if vacation_only:
            atype = a.get("absence_type") or {}
            if not atype.get("is_vacation"):
                continue
        return a
    return None


def _summarize_absence(absence: dict[str, Any]) -> dict[str, Any]:
    """Build a compact dict with the attributes most templates will need."""
    atype = absence.get("absence_type") or {}
    return {
        "start_date": absence.get("start_date"),
        "end_date": absence.get("end_date"),
        "type": atype.get("name"),
        "is_vacation": atype.get("is_vacation"),
        "first_half_day": absence.get("first_half_day"),
        "second_half_day": absence.get("second_half_day"),
    }
