"""Tests for the Solyx Energy Local sensor platform."""

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)
from solyx_energy_local_api.exceptions import SolyxEnergyDataError
from solyx_energy_local_api.models import LocalStatus

from homeassistant.components.solyx_energy_local.const import (
    DATA_INTERVAL_SECONDS,
    DOMAIN,
)
from homeassistant.components.solyx_energy_local.coordinator import (
    SolyxEnergyData,
    to_cloud_values,
)
from homeassistant.const import STATE_UNAVAILABLE

from .const import DEVICE_ID

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from freezegun.api import FrozenDateTimeFactory
    from syrupy.assertion import SnapshotAssertion

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import EntityRegistry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """All sensors have the values, units and device classes of the cloud integration."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


def test_savings_in_whole_kilowatt_hours() -> None:
    """This week and this month are whole kWh, rounded down like the Sensorbox reports them to the cloud."""
    status = LocalStatus.from_dict(load_json_object_fixture("status.json", DOMAIN))
    values = to_cloud_values(status)
    assert values.saved_this_week == 9.0
    assert values.saved_this_month == 41.0
    assert values.saved_today == 1200.0


async def test_sensors_unavailable_when_unreachable(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    init_integration: MockConfigEntry,
    mock_api_client_class: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The sensors become unavailable when the Sensorbox stops answering."""
    mock_api_client_class.async_get_status.side_effect = SolyxEnergyDataError
    freezer.tick(DATA_INTERVAL_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}-boiler_power"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


def test_values_before_first_read() -> None:
    """Right after a restart the Sensorbox has not read the Nymo yet, so all values are unknown."""
    status = LocalStatus.from_dict(
        {
            "controlSource": "CLOUD",
            "nymo": {"connected": None, "boiler": None, "grid": None},
            "savings": None,
            "settings": None,
        }
    )
    assert to_cloud_values(status) == SolyxEnergyData(
        boiler_current=None,
        boiler_power=None,
        boiler_voltage=None,
        days_since_maximum_temperature=None,
        grid_power=None,
        legionella_days=None,
        saved_this_month=None,
        saved_this_week=None,
        saved_today=None,
    )
