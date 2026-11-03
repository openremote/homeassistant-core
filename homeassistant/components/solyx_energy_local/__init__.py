"""The Solyx Energy Local integration."""

from solyx_energy_local_api.client import SolyxEnergyLocalApiClient

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CERT_SHA256
from .coordinator import SolyxEnergyLocalConfigEntry, SolyxEnergyLocalCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: SolyxEnergyLocalConfigEntry
) -> None:
    """Set up a Nymo from a config entry."""
    api_client = SolyxEnergyLocalApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_TOKEN],
        entry.data[CONF_CERT_SHA256],
        port=entry.data[CONF_PORT],
    )
    coordinator = SolyxEnergyLocalCoordinator(hass, api_client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: SolyxEnergyLocalConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
