"""Config flow for the Solyx Energy Local integration."""

import logging
from typing import TYPE_CHECKING, Any, override

import probatio
from solyx_energy_local_api.client import (
    DEFAULT_PORT,
    SolyxEnergyLocalApiClient,
    normalize_fingerprint,
)
from solyx_energy_local_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyCertificateError,
    SolyxEnergyDataError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_CERT_SHA256, DISCOVERY_DEVICE_ID, DOMAIN

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)

# The access token and certificate fingerprint are shown in the Solyx Energy app.
CREDENTIALS_SCHEMA = {
    probatio.Required(CONF_TOKEN): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
    probatio.Required(CONF_CERT_SHA256): TextSelector(),
}
STEP_USER_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_HOST): TextSelector(), **CREDENTIALS_SCHEMA}
)
STEP_CREDENTIALS_SCHEMA = probatio.Schema(CREDENTIALS_SCHEMA)


class SolyxEnergyLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for a Nymo on the home network."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port = DEFAULT_PORT

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a Nymo that is set up by its address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**user_input, CONF_PORT: DEFAULT_PORT}
            device_id = await self._async_validate(data, errors)
            if device_id is not None:
                # Setting up by hand takes over from a discovery of the same Nymo.
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: data[CONF_HOST]}
                )
                return self._async_create_entry(device_id, data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self,
        discovery_info: ZeroconfServiceInfo,
    ) -> ConfigFlowResult:
        """Handle a Nymo that is found on the network over mDNS."""
        device_id = discovery_info.properties.get(DISCOVERY_DEVICE_ID)
        if not device_id:
            return self.async_abort(reason="not_solyx_device")

        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        await self.async_set_unique_id(device_id)
        # A Nymo that is already set up may have a new IP address.
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        self.context["title_placeholders"] = {"device_id": device_id}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Ask for the access token and certificate fingerprint of a discovered Nymo."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {CONF_HOST: self._host, CONF_PORT: self._port, **user_input}
            device_id = await self._async_validate(data, errors)
            if device_id is not None:
                if device_id != self.unique_id:
                    return self.async_abort(reason="wrong_device")
                return self._async_create_entry(device_id, data)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CREDENTIALS_SCHEMA, user_input
            ),
            description_placeholders={
                "device_id": self.unique_id or "",
                "host": self._host or "",
            },
            errors=errors,
        )

    def _async_create_entry(
        self, device_id: str, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create the config entry with a normalized fingerprint."""
        data[CONF_CERT_SHA256] = normalize_fingerprint(data[CONF_CERT_SHA256])
        return self.async_create_entry(title=f"Nymo {device_id}", data=data)

    async def _async_validate(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> str | None:
        """Connect to the Sensorbox and return its device ID, or fill in the errors."""
        try:
            client = SolyxEnergyLocalApiClient(
                async_get_clientsession(self.hass),
                data[CONF_HOST],
                data[CONF_TOKEN],
                data[CONF_CERT_SHA256],
                port=data[CONF_PORT],
            )
        except ValueError:
            errors[CONF_CERT_SHA256] = "invalid_fingerprint"
            return None

        try:
            info = await client.async_test_connection()
        except SolyxEnergyAuthError:
            errors["base"] = "invalid_auth"
        except SolyxEnergyCertificateError:
            errors["base"] = "certificate_mismatch"
        except SolyxEnergyDataError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while connecting to the Sensorbox")
            errors["base"] = "unknown"
        else:
            return info.device_id
        return None
