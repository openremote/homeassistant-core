"""Fixtures and helpers for the Solyx Energy Local tests."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from solyx_energy_local_api.client import SolyxEnergyLocalApiClient
from solyx_energy_local_api.models import LocalInfo, LocalStatus

from homeassistant.components.solyx_energy_local.const import CONF_CERT_SHA256, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN

from .const import CERT_SHA256, DEVICE_ID, HOST, TOKEN

if TYPE_CHECKING:
    from collections.abc import Generator

    from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for the Solyx Energy Local integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: 443,
            CONF_TOKEN: TOKEN,
            CONF_CERT_SHA256: CERT_SHA256,
        },
        title=f"Nymo {DEVICE_ID}",
    )


@pytest.fixture
def mock_local_api_client() -> AsyncMock:
    """Return a mocked SolyxEnergyLocalApiClient instance."""
    client = AsyncMock(spec=SolyxEnergyLocalApiClient)
    client.async_get_status.return_value = LocalStatus.from_dict(
        load_json_object_fixture("status.json", DOMAIN)
    )
    info = LocalInfo.from_dict(load_json_object_fixture("info.json", DOMAIN))
    client.async_get_info.return_value = info
    client.async_test_connection.return_value = info
    return client


@pytest.fixture
def mock_api_client_class(mock_local_api_client: AsyncMock) -> Generator[AsyncMock]:
    """Patch SolyxEnergyLocalApiClient so integration setup and config flow use the mock."""
    with (
        patch(
            "homeassistant.components.solyx_energy_local.SolyxEnergyLocalApiClient",
            return_value=mock_local_api_client,
        ),
        patch(
            "homeassistant.components.solyx_energy_local.config_flow.SolyxEnergyLocalApiClient",
            return_value=mock_local_api_client,
        ) as config_flow_class,
    ):
        mock_local_api_client.config_flow_class = config_flow_class
        yield mock_local_api_client


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry, preventing full integration setup."""
    with patch(
        "homeassistant.components.solyx_energy_local.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_api_client_class: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Solyx Energy Local integration and return the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
