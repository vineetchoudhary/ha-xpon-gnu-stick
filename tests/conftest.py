"""Real Home Assistant and a local read-only ONU test server."""

from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from aiohttp import ThreadedResolver, web
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_setup as async_setup_loader
from homeassistant.setup import async_setup_component

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def device_html():
    return (FIXTURES / "device_status.html").read_text()


@pytest.fixture
def pon_html():
    return (FIXTURES / "pon_status.html").read_text()


@pytest.fixture
def login_html():
    return (FIXTURES / "login.html").read_text()


@pytest_asyncio.fixture
async def onu_server(device_html, pon_html, login_html):
    requests = []
    state = {
        "device": device_html,
        "pon": pon_html,
        "status": 200,
        "auth": None,
        "form_auth": None,
        "login_html": login_html,
        "login_posts": [],
        "sessions": set(),
        "protected_response": "redirect",
        "expire_before_pon": False,
        "login_redirect": "/",
        "login_status": 302,
        "ip_session": False,
        "ip_authenticated": False,
        "csrf": False,
    }

    async def status_page(request):
        requests.append((request.method, request.path, request.headers.get("Authorization")))
        if request.path == "/admin/login.asp":
            response = web.Response(text=state["login_html"], content_type="text/html")
            if state["csrf"]:
                response.set_cookie("csrf", "seed", path="/")
            return response
        if request.path == "/boaform/admin/formLogin" and request.method == "POST":
            payload = dict(await request.post())
            state["login_posts"].append(payload)
            if (payload.get("username"), payload.get("password")) != state["form_auth"] or (
                state["csrf"]
                and (request.cookies.get("csrf") != "seed" or payload.get("csrf_token") != "seed")
            ):
                return web.Response(text=state["login_html"], content_type="text/html")
            token = f"session-{len(state['login_posts'])}"
            state["sessions"].add(token)
            response = web.Response(
                status=state["login_status"],
                headers={"Location": state["login_redirect"]}
                if state["login_status"] == 302
                else {},
            )
            if state["ip_session"]:
                state["ip_authenticated"] = True
            else:
                response.set_cookie("session", token, path="/")
            return response
        if request.path == "/status_pon.asp" and state["expire_before_pon"]:
            state["sessions"].clear()
            state["expire_before_pon"] = False
        if (
            state["form_auth"]
            and request.cookies.get("session") not in state["sessions"]
            and not state["ip_authenticated"]
        ):
            if state["protected_response"] == "html":
                return web.Response(text=state["login_html"], content_type="text/html")
            return web.Response(status=302, headers={"Location": "/admin/login.asp"})
        if state["auth"] and request.headers.get("Authorization") != state["auth"]:
            return web.Response(status=401, headers={"WWW-Authenticate": 'Basic realm="ONU"'})
        if state["status"] == 302:
            return web.Response(status=302, headers={"Location": "/settings.asp"})
        if state["status"] != 200:
            return web.Response(status=state["status"])
        key = "device" if request.path == "/status.asp" else "pon"
        return web.Response(text=state[key], content_type="text/html")

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", status_page)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}", state, requests
    await runner.cleanup()


@pytest_asyncio.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    async_setup_loader(instance)
    instance.config_entries = ConfigEntries(instance, {})
    assert await async_load_base_functionality(instance)
    assert await async_setup_component(instance, "homeassistant", {})
    # mDNS is unrelated to this HTTP integration. Keep discovery traffic off
    # the physical network while exercising Home Assistant's shared session.
    resolver = ThreadedResolver()
    with patch(
        "homeassistant.helpers.aiohttp_client._async_get_or_create_resolver", return_value=resolver
    ):
        yield instance
        await instance.async_stop(force=True)
    await resolver.close()
