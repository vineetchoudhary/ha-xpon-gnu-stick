"""UI setup, authentication, connection changes, and polling options."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import OnuAuthError, OnuClient, OnuConnectionError, OnuParseError, normalize_host
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def _connection_schema(defaults: dict[str, Any], *, include_host: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if include_host:
        host_field = vol.Required(CONF_HOST)
        if CONF_HOST in defaults:
            host_field = vol.Required(CONF_HOST, default=defaults[CONF_HOST])
        fields[host_field] = str
    fields[vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, ""))] = str
    fields[vol.Optional(CONF_PASSWORD, default="")] = TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    )
    return vol.Schema(fields)


class OnuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a device after verifying both read-only status pages."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OnuOptionsFlow:
        return OnuOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_connection_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_connection_step("reconfigure", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_connection_step("reauth_confirm", user_input)

    async def _async_connection_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        entry = None
        if step_id == "reconfigure":
            entry = self._get_reconfigure_entry()
        elif step_id == "reauth_confirm":
            entry = self._get_reauth_entry()
        defaults = dict(entry.data) if entry else {}
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_HOST: user_input.get(CONF_HOST, defaults.get(CONF_HOST, "")),
                CONF_USERNAME: user_input.get(CONF_USERNAME, "").strip(),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
            }
            defaults.update(data)
            try:
                data[CONF_HOST] = normalize_host(data[CONF_HOST])
                if data[CONF_PASSWORD] and not data[CONF_USERNAME]:
                    errors[CONF_USERNAME] = "username_required"
                else:
                    client = OnuClient(
                        async_get_clientsession(self.hass),
                        data[CONF_HOST],
                        data[CONF_USERNAME],
                        data[CONF_PASSWORD],
                    )
                    status = await client.async_get_status()
                    await self.async_set_unique_id(status.mac_address)
                    if entry:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(entry, data=data)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=str(status.values["device_name"]),
                        data=data,
                    )
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            except OnuAuthError:
                errors["base"] = "invalid_auth"
            except OnuConnectionError:
                errors["base"] = "cannot_connect"
            except OnuParseError:
                errors["base"] = "unsupported_device"

        return self.async_show_form(
            step_id=step_id,
            data_schema=_connection_schema(defaults, include_host=step_id != "reauth_confirm"),
            errors=errors,
        )


class OnuOptionsFlow(OptionsFlowWithReload):
    """Change only Home Assistant's polling frequency."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    ),
                }
            ),
        )
