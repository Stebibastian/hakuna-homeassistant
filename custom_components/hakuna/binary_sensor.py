"""Binary sensor entities for Hakuna integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HakunaDataUpdateCoordinator


BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="timer_running",
        name="Eingestempelt",
        icon="mdi:clock-check",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hakuna binary sensors."""
    coordinator: HakunaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        HakunaBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    # Add binary sensors for team members if presence data is available
    if coordinator.data and coordinator.data.get("presence"):
        for member in coordinator.data["presence"]:
            user = member.get("user", {})
            if user.get("id") and user.get("name"):
                entities.append(
                    HakunaTeamMemberSensor(coordinator, entry, user)
                )

    async_add_entities(entities)


class HakunaBinarySensor(CoordinatorEntity[HakunaDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a Hakuna binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HakunaDataUpdateCoordinator,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return true if the timer is running."""
        if self.coordinator.data is None:
            return None

        key = self.entity_description.key

        if key == "timer_running":
            return self.coordinator.data.get("timer_running", False)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs = {}
        
        if self.coordinator.data is None:
            return attrs

        timer = self.coordinator.data.get("timer")
        
        if timer:
            attrs["start_time"] = timer.get("start_time")
            attrs["duration"] = timer.get("duration")
            attrs["duration_seconds"] = timer.get("duration_in_seconds")
            attrs["note"] = timer.get("note")
            attrs["date"] = timer.get("date")
            
            if timer.get("task"):
                attrs["task"] = timer["task"].get("name")
                attrs["task_id"] = timer["task"].get("id")
                
            if timer.get("project"):
                project = timer["project"]
                if isinstance(project, dict):
                    attrs["project"] = project.get("name")
                    attrs["project_id"] = project.get("id")
                else:
                    attrs["project_id"] = project
                    
            if timer.get("user"):
                attrs["user_name"] = timer["user"].get("name")
                attrs["user_id"] = timer["user"].get("id")

        return attrs


class HakunaTeamMemberSensor(CoordinatorEntity[HakunaDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a team member presence sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HakunaDataUpdateCoordinator,
        entry: ConfigEntry,
        user: dict[str, Any],
    ) -> None:
        """Initialize the team member sensor."""
        super().__init__(coordinator)
        self._user_id = user.get("id")
        self._user_name = user.get("name")
        self._entry_id = entry.entry_id
        
        self._attr_unique_id = f"{entry.entry_id}_team_{self._user_id}"
        self._attr_name = f"{self._user_name} anwesend"
        self._attr_icon = "mdi:account-clock"
        self._attr_device_class = BinarySensorDeviceClass.PRESENCE
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Hakuna",
            manufacturer="Hakuna AG",
            model="Time Tracking",
            entry_type="service",
        )
        self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool | None:
        """Return true if the team member has a timer running."""
        if self.coordinator.data is None:
            return None

        presence = self.coordinator.data.get("presence", [])
        
        for member in presence:
            user = member.get("user", {})
            if user.get("id") == self._user_id:
                return member.get("has_timer_running", False)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        attrs = {
            "user_id": self._user_id,
            "user_name": self._user_name,
        }
        
        if self.coordinator.data is None:
            return attrs

        presence = self.coordinator.data.get("presence", [])
        
        for member in presence:
            user = member.get("user", {})
            if user.get("id") == self._user_id:
                attrs["absent_first_half_day"] = member.get("absent_first_half_day")
                attrs["absent_second_half_day"] = member.get("absent_second_half_day")
                attrs["groups"] = user.get("groups", [])
                attrs["status"] = user.get("status")
                break

        return attrs
