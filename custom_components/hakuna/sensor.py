"""Sensor entities for Hakuna integration."""
from __future__ import annotations

import logging
from datetime import datetime
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

from .const import DOMAIN
from .coordinator import HakunaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS = [
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
        entity_registry_enabled_default=False,
    ),
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
            entry_type="service",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        key = self.entity_description.key
        data = self.coordinator.data
        overview = data.get("overview", {})
        timer = data.get("timer")

        if key == "overtime":
            return overview.get("overtime")
        elif key == "overtime_hours":
            seconds = overview.get("overtime_in_seconds")
            if seconds is None:
                return None
            return round(seconds / 3600, 2)
        elif key == "overtime_seconds":
            return overview.get("overtime_in_seconds")
        elif key == "vacation_remaining":
            vacation = overview.get("vacation", {})
            return vacation.get("remaining_days")
        elif key == "vacation_redeemed":
            vacation = overview.get("vacation", {})
            return vacation.get("redeemed_days")
        elif key == "timer_duration":
            if timer:
                return timer.get("duration")
            return None
        elif key == "timer_duration_hours":
            if timer:
                seconds = timer.get("duration_in_seconds")
                if seconds is None:
                    return None
                return round(seconds / 3600, 2)
            return None
        elif key == "timer_duration_seconds":
            if timer:
                return timer.get("duration_in_seconds")
            return None
        elif key == "timer_start_time":
            if timer:
                date_str = timer.get("date")
                time_str = timer.get("start_time")
                if date_str and time_str:
                    try:
                        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                        # Make timezone-aware using Home Assistant's configured timezone
                        return dt_util.as_local(dt.replace(tzinfo=dt_util.get_default_time_zone()))
                    except ValueError as err:
                        _LOGGER.warning(
                            "Could not parse Hakuna timer start time '%s %s': %s",
                            date_str, time_str, err
                        )
                        return None
            return None
        elif key == "timer_project":
            if timer and timer.get("project"):
                project = timer["project"]
                if isinstance(project, dict):
                    return project.get("name")
                return str(project)
            return None
        elif key == "timer_task":
            if timer and timer.get("task"):
                return timer["task"].get("name")
            return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs: dict[str, Any] = {}
        key = self.entity_description.key
        data = self.coordinator.data

        if data is None:
            return attrs

        overview = data.get("overview", {})
        timer = data.get("timer")

        # Expose formatted "HH:MM" on numeric overtime sensors for dashboard display.
        if key in ("overtime_hours", "overtime_seconds"):
            if overview.get("overtime") is not None:
                attrs["formatted"] = overview.get("overtime")

        # Expose seconds on the string overtime sensor for advanced templates.
        if key == "overtime":
            seconds = overview.get("overtime_in_seconds")
            if seconds is not None:
                attrs["seconds"] = seconds
                attrs["hours"] = round(seconds / 3600, 2)

        if key == "timer_duration" and timer:
            attrs["note"] = timer.get("note")
            if timer.get("user"):
                attrs["user_name"] = timer["user"].get("name")
                attrs["user_id"] = timer["user"].get("id")

        return attrs
