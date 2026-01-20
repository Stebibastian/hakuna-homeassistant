"""Button entities for Hakuna integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HakunaDataUpdateCoordinator
from .api import HakunaApiClient

_LOGGER = logging.getLogger(__name__)


BUTTON_DESCRIPTIONS = [
    ButtonEntityDescription(
        key="start_timer",
        name="Timer starten",
        icon="mdi:play",
    ),
    ButtonEntityDescription(
        key="stop_timer",
        name="Timer stoppen",
        icon="mdi:stop",
    ),
    ButtonEntityDescription(
        key="cancel_timer",
        name="Timer abbrechen",
        icon="mdi:close-circle-outline",
    ),
    ButtonEntityDescription(
        key="refresh",
        name="Daten aktualisieren",
        icon="mdi:refresh",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hakuna buttons."""
    coordinator: HakunaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api_client: HakunaApiClient = hass.data[DOMAIN][entry.entry_id]["api_client"]

    entities = [
        HakunaButton(coordinator, api_client, entry, description)
        for description in BUTTON_DESCRIPTIONS
    ]

    async_add_entities(entities)


class HakunaButton(CoordinatorEntity[HakunaDataUpdateCoordinator], ButtonEntity):
    """Representation of a Hakuna button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HakunaDataUpdateCoordinator,
        api_client: HakunaApiClient,
        entry: ConfigEntry,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._api_client = api_client
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Hakuna",
            manufacturer="Hakuna AG",
            model="Time Tracking",
            entry_type="service",
        )

    @property
    def available(self) -> bool:
        """Return if button is available based on timer state."""
        if not self.coordinator.data:
            return False

        timer_running = self.coordinator.data.get("timer_running", False)
        key = self.entity_description.key

        # Start button only available when timer is NOT running
        if key == "start_timer":
            return not timer_running

        # Stop/Cancel buttons only available when timer IS running
        if key in ("stop_timer", "cancel_timer"):
            return timer_running

        return True

    async def async_press(self) -> None:
        """Handle the button press."""
        key = self.entity_description.key

        try:
            if key == "start_timer":
                # Get default task_id from coordinator data
                task_id = None
                if self.coordinator.data:
                    task_id = self.coordinator.data.get("default_task_id")

                if task_id is None:
                    _LOGGER.warning("No default task found, trying to start timer without task_id")

                await self._api_client.start_timer(task_id=task_id)
                _LOGGER.info("Hakuna timer started with task_id=%s", task_id)
            elif key == "stop_timer":
                await self._api_client.stop_timer()
                _LOGGER.info("Hakuna timer stopped")
            elif key == "refresh":
                _LOGGER.info("Hakuna data refresh requested")
            elif key == "cancel_timer":
                await self._api_client.cancel_timer()
                _LOGGER.info("Hakuna timer cancelled")

            # Refresh data after action
            await self.coordinator.async_request_refresh()

        except Exception as err:
            _LOGGER.error("Error performing Hakuna action %s: %s", key, err)
            raise
