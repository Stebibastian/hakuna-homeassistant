"""Hakuna Time Tracking Integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_DAILY_TARGET_HOURS,
    DEFAULT_DAILY_TARGET_HOURS,
    CONF_WORK_DAYS,
    DEFAULT_WORK_DAYS,
)
from .coordinator import HakunaDataUpdateCoordinator
from .api import HakunaApiClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hakuna from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    api_client = HakunaApiClient(
        session=session,
        api_token=entry.data["api_token"],
        company=entry.data.get("company"),
    )

    # Parse work-day string "0,1,2,3,4" into a set of weekday numbers.
    work_days_raw = entry.options.get(CONF_WORK_DAYS, DEFAULT_WORK_DAYS)
    try:
        work_days: set[int] = {
            int(d.strip())
            for d in str(work_days_raw).split(",")
            if d.strip().isdigit() and 0 <= int(d.strip()) <= 6
        }
    except ValueError:
        work_days = {0, 1, 2, 3, 4}
    if not work_days:
        work_days = {0, 1, 2, 3, 4}

    coordinator = HakunaDataUpdateCoordinator(
        hass,
        api_client=api_client,
        update_interval=timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
        daily_target_hours=float(
            entry.options.get(CONF_DAILY_TARGET_HOURS, DEFAULT_DAILY_TARGET_HOURS)
        ),
        work_days=work_days,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
