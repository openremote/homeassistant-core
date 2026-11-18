"""Base entity for the Solyx Energy Local integration."""

import re
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolyxEnergyLocalCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription

_MAC_PATTERN = re.compile(r"[0-9A-Fa-f]{12}")


class SolyxNymoEntity(CoordinatorEntity[SolyxEnergyLocalCoordinator]):
    """Base class for the Nymo entities of the Solyx Energy Local integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolyxEnergyLocalCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize a Solyx Nymo entity."""
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.device_id
        self._attr_unique_id = f"{device_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Nymo",
            manufacturer="Solyx Energy",
            model="Nymo",
            serial_number=device_id,
            sw_version=coordinator.info.firmware_version if coordinator.info else None,
        )
        # The device ID is the Wi-Fi MAC of the Sensorbox; it links the device to its network entry.
        if _MAC_PATTERN.fullmatch(device_id):
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, format_mac(device_id))
            }
