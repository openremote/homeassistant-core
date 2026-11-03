"""Coordinator that polls the local API of the Sensorbox."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from solyx_energy_local_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyCertificateError,
    SolyxEnergyDataError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_INTERVAL_SECONDS, DOMAIN, STALE_AFTER_SECONDS

if TYPE_CHECKING:
    from solyx_energy_local_api.client import SolyxEnergyLocalApiClient
    from solyx_energy_local_api.models import LocalInfo, LocalStatus

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type SolyxEnergyLocalConfigEntry = ConfigEntry[SolyxEnergyLocalCoordinator]


@dataclass(frozen=True)
class SolyxEnergyData:
    """Hold a snapshot of the values of a Nymo, the same as the Solyx Energy Cloud integration."""

    boiler_current: float | None
    boiler_power: float | None
    boiler_voltage: float | None
    days_since_maximum_temperature: float | None
    grid_power: float | None
    legionella_days: float | None
    saved_this_month: float | None
    saved_this_week: float | None
    saved_today: float | None


def _kilowatt_hours(watt_hours: int) -> float:
    """Convert Wh to whole kWh, rounded down like the Sensorbox reports them to the cloud."""
    return float(watt_hours // 1000)


def _is_fresh(status: LocalStatus, age: int | None) -> bool:
    """Whether the Sensorbox read the values recently from a Nymo that is connected.

    The Sensorbox keeps serving the last values it read, so they go stale when the
    Nymo stops answering.
    """
    return (
        status.nymo.connected is not False
        and age is not None
        and age <= STALE_AFTER_SECONDS
    )


def to_cloud_values(status: LocalStatus) -> SolyxEnergyData:
    """Map the local status to the values and units the Solyx Energy cloud reports.

    Stale values are None.
    """
    nymo_fresh = _is_fresh(status, status.nymo.age)
    boiler = status.nymo.boiler if nymo_fresh else None
    grid = status.nymo.grid if nymo_fresh else None
    savings = status.savings
    if savings and not _is_fresh(status, savings.age):
        savings = None
    settings = status.settings
    if settings and not _is_fresh(status, settings.age):
        settings = None
    legionella = settings.legionella if settings else None
    return SolyxEnergyData(
        boiler_current=boiler.current if boiler else None,
        boiler_power=float(boiler.power) if boiler else None,
        boiler_voltage=float(boiler.voltage) if boiler else None,
        days_since_maximum_temperature=(
            float(legionella.days_since_max_temperature) if legionella else None
        ),
        grid_power=float(grid.power) if grid else None,
        legionella_days=float(legionella.interval_days) if legionella else None,
        saved_this_month=_kilowatt_hours(savings.this_month) if savings else None,
        saved_this_week=_kilowatt_hours(savings.this_week) if savings else None,
        saved_today=float(savings.today) if savings else None,
    )


class SolyxEnergyLocalCoordinator(DataUpdateCoordinator[SolyxEnergyData]):
    """Coordinator that fetches the status of a Nymo from its Sensorbox."""

    config_entry: SolyxEnergyLocalConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: SolyxEnergyLocalApiClient,
        config_entry: SolyxEnergyLocalConfigEntry,
    ) -> None:
        """Initialize the coordinator for a single Nymo."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DATA_INTERVAL_SECONDS),
        )
        self.api_client = api_client
        # The config entry's unique ID is the device ID reported by the Sensorbox.
        self.device_id: str = config_entry.unique_id or ""
        # Identity and firmware versions, read once when the entry is set up.
        self.info: LocalInfo | None = None

    @override
    async def _async_setup(self) -> None:
        """Read the device info, which does not change while the Sensorbox runs."""
        try:
            self.info = await self.api_client.async_get_info()
        except (SolyxEnergyAuthError, SolyxEnergyCertificateError) as err:
            raise ConfigEntryAuthFailed(f"Auth error: {err}") from err
        except SolyxEnergyDataError as err:
            raise UpdateFailed(f"API error: {err}") from err

    @override
    async def _async_update_data(self) -> SolyxEnergyData:
        """Fetch the status from the Sensorbox and map it to the entity values."""
        try:
            _LOGGER.debug("Retrieving the status from the Sensorbox")
            status = await self.api_client.async_get_status()
        except (SolyxEnergyAuthError, SolyxEnergyCertificateError) as err:
            raise ConfigEntryAuthFailed(f"Auth error: {err}") from err
        except SolyxEnergyDataError as err:
            raise UpdateFailed(f"API error: {err}") from err
        return to_cloud_values(status)
