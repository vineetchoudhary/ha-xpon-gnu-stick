"""Verify setup flows and entity lifecycle in the real Home Assistant runtime."""

from unittest.mock import patch

import aiohttp
import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.xpon_gnu_stick.api import (
    DEVICE_FIELDS,
    PON_FIELDS,
    OnuAuthError,
    OnuConnectionError,
    OnuStatus,
    parse_status_page,
)
from custom_components.xpon_gnu_stick.const import DOMAIN


async def add_device(hass, host):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={CONF_HOST: host}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_initial_setup_requires_an_address_and_never_uses_a_fallback(hass):
    with patch("custom_components.xpon_gnu_stick.config_flow.OnuClient.async_get_status") as fetch:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] is FlowResultType.FORM
        schema = result["data_schema"]
        host_field = next(field for field in schema.schema if field.schema == CONF_HOST)
        assert host_field.default is vol.UNDEFINED
        with pytest.raises(vol.Invalid):
            schema({})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: ""})
        assert result["errors"] == {CONF_HOST: "invalid_host"}
        fetch.assert_not_called()


async def test_setup_all_16_sensors_and_unload(hass, onu_server):
    host, _, requests = onu_server
    entry = await add_device(hass, host)
    assert entry.state is ConfigEntryState.LOADED
    states = {state.entity_id: state for state in hass.states.async_all("sensor")}
    assert len(states) == 16
    assert states["sensor.aot5222zy_rx_power"].state == "-26.382721"
    assert states["sensor.aot5222zy_rx_power"].attributes["unit_of_measurement"] == "dBm"
    assert states["sensor.aot5222zy_temperature"].attributes["state_class"] == "measurement"
    assert states["sensor.aot5222zy_bias_current"].attributes["unit_of_measurement"] == "mA"
    assert states["sensor.aot5222zy_uptime"].state == "1:21"
    assert states["sensor.aot5222zy_onu_state"].state == "O5"
    assert states["sensor.aot5222zy_onu_id"].state == "0"
    assert entry.unique_id == "3c:f7:5d:af:ff:48"
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 16
    assert len({entity.unique_id for entity in entities}) == 16
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert devices[0].model == "AOT5222ZY"
    assert devices[0].sw_version == "V1.0-220923"
    assert devices[0].configuration_url == host
    assert requests == [("GET", "/status.asp", None), ("GET", "/status_pon.asp", None)] * 2
    coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not coordinator._listeners
    assert coordinator._unsub_refresh is None
    assert all(state.state == "unavailable" for state in hass.states.async_all("sensor"))


async def test_failed_poll_marks_every_sensor_unavailable_then_recovers(hass, onu_server):
    host, state, _ = onu_server
    entry = await add_device(hass, host)
    state["status"] = 500
    await entry.runtime_data.async_refresh()
    assert all(sensor.state == "unavailable" for sensor in hass.states.async_all("sensor"))
    state["status"] = 200
    state["pon"] = state["pon"].replace("37.277344 C", "40.000000 C")
    await entry.runtime_data.async_refresh()
    assert hass.states.get("sensor.aot5222zy_temperature").state == "40.0"
    assert hass.states.get("sensor.aot5222zy_onu_state").state == "O5"


async def test_replaced_device_does_not_change_existing_identity(hass, onu_server):
    host, state, _ = onu_server
    entry = await add_device(hass, host)
    state["device"] = state["device"].replace("3cf75dafff48", "001122334455")
    await entry.runtime_data.async_refresh()
    assert entry.unique_id == "3c:f7:5d:af:ff:48"
    assert all(sensor.state == "unavailable" for sensor in hass.states.async_all("sensor"))


async def test_duplicate_device(hass, onu_server):
    host, _, _ = onu_server
    await add_device(hass, host)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={CONF_HOST: host}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "error, expected", [(OnuAuthError(), "invalid_auth"), (OnuConnectionError(), "cannot_connect")]
)
async def test_flow_errors(hass, error, expected):
    with patch(
        "custom_components.xpon_gnu_stick.config_flow.OnuClient.async_get_status",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={CONF_HOST: "onu.example"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_bad_host_and_missing_username_never_fetch(hass):
    with patch("custom_components.xpon_gnu_stick.config_flow.OnuClient.async_get_status") as fetch:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={CONF_HOST: "http://onu/reboot.asp"}
        )
        assert result["errors"] == {CONF_HOST: "invalid_host"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "onu.example", CONF_PASSWORD: "secret"}
        )
        assert result["errors"] == {CONF_USERNAME: "username_required"}
        fetch.assert_not_called()


async def test_options_change_polling_interval_and_reload(hass, onu_server):
    host, _, _ = onu_server
    entry = await add_device(hass, host)
    old_coordinator = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    for invalid in (0, 9, 3601):
        with pytest.raises(vol.Invalid):
            schema({CONF_SCAN_INTERVAL: invalid})
    await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: 60})
    await hass.async_block_till_done()
    assert entry.options[CONF_SCAN_INTERVAL] == 60
    assert entry.runtime_data is not old_coordinator
    assert entry.runtime_data.update_interval.total_seconds() == 60
    assert len(hass.states.async_all("sensor")) == 16


async def test_reconfigure_preserves_entity_identity(hass, onu_server):
    host, _, _ = onu_server
    entry = await add_device(hass, host)
    ids_before = {state.entity_id for state in hass.states.async_all("sensor")}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    host_field = next(field for field in result["data_schema"].schema if field.schema == CONF_HOST)
    assert host_field.default() == host
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: host})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert {state.entity_id for state in hass.states.async_all("sensor")} == ids_before


async def test_reconfigure_rejects_different_device(hass, onu_server):
    host, state, _ = onu_server
    entry = await add_device(hass, host)
    state["device"] = state["device"].replace("3cf75dafff48", "001122334455")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data={CONF_HOST: host},
    )
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == "3c:f7:5d:af:ff:48"


async def test_auth_expiry_starts_reauth_and_restores_sensors(hass, onu_server):
    host, state, _ = onu_server
    entry = await add_device(hass, host)
    state["auth"] = aiohttp.encode_basic_auth("reader", "secret")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert all(sensor.state == "unavailable" for sensor in hass.states.async_all("sensor"))
    flows = hass.config_entries.flow.async_progress()
    flow = next(flow for flow in flows if flow["context"]["source"] == "reauth")
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_USERNAME: "reader", CONF_PASSWORD: "secret"}
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.data[CONF_USERNAME] == "reader"
    assert hass.states.get("sensor.aot5222zy_onu_state").state == "O5"


async def test_startup_connection_failure_is_retryable(hass, onu_server, device_html, pon_html):
    host, _, _ = onu_server
    snapshot = OnuStatus(
        {
            **parse_status_page(device_html, DEVICE_FIELDS),
            **parse_status_page(pon_html, PON_FIELDS),
        },
        "3c:f7:5d:af:ff:48",
    )
    # First call validates the flow; the startup refresh then loses connectivity.
    with patch(
        "custom_components.xpon_gnu_stick.api.OnuClient.async_get_status",
        side_effect=[snapshot, OnuConnectionError()],
    ):
        entry = await add_device(hass, host)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("sensor")
