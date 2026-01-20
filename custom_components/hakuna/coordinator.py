"""Data update coordinator for Hakuna."""
from __future__ import annotations

import logging
from datetime import timedelta
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
            # Get timer status
            timer = await self.api_client.get_timer()

            # Get overview (overtime, vacation)
            overview = await self.api_client.get_overview()

            # Get presence info (for team status if available)
            try:
                presence = await self.api_client.get_presence()
            except HakunaApiError:
                presence = []

            # Get managed users (if supervisor/admin)
            try:
                users = await self.api_client.get_users()
            except HakunaApiError:
                users = []

            # Get tasks (needed for timer start)
            try:
                tasks = await self.api_client.get_tasks()
            except HakunaApiError:
                tasks = []

            # Find default task
            default_task_id = None
            for task in tasks:
                if task.get("default") and not task.get("archived"):
                    default_task_id = task.get("id")
                    break
            # Fallback to first non-archived task
            if default_task_id is None and tasks:
                for task in tasks:
                    if not task.get("archived"):
                        default_task_id = task.get("id")
                        break

            return {
                "timer": timer,
                "overview": overview,
                "presence": presence,
                "users": users,
                "tasks": tasks,
                "default_task_id": default_task_id,
                "timer_running": timer is not None,
            }

        except HakunaAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except HakunaApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
