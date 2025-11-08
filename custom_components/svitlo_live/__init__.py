from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_REGION,
    CONF_QUEUE,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import SvitloCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Svitlo.live v2 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Фіксований інтервал опитування (15 хв)
    config = {
        CONF_REGION: entry.data[CONF_REGION],
        CONF_QUEUE: entry.data[CONF_QUEUE],
        "scan_interval_seconds": DEFAULT_SCAN_INTERVAL,
    }

    coordinator = SvitloCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Svitlo.live v2 entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
