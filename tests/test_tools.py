"""Exercise the live-check command against the read-only localhost ONU simulator."""

import asyncio
import json
import sys
from pathlib import Path

CHECK_STATUS = Path(__file__).resolve().parents[1] / "tools/check_status.py"


async def run_status_check(host: str | None, working_directory: Path) -> tuple[int, str, str]:
    host_args = ("--host", host) if host is not None else ()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(CHECK_STATUS),
        *host_args,
        cwd=working_directory,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(20):
            stdout, stderr = await process.communicate()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    return process.returncode, stdout.decode(), stderr.decode()


async def test_live_check_requires_an_explicit_address(tmp_path):
    returncode, stdout, stderr = await run_status_check(None, tmp_path)
    assert returncode == 2
    assert stdout == ""
    assert "required: --host" in stderr


async def test_live_check_prints_complete_status(onu_server, tmp_path):
    host, _, requests = onu_server
    returncode, stdout, stderr = await run_status_check(host, tmp_path)
    assert returncode == 0, stderr
    readings = json.loads(stdout)
    assert len(readings) == 16
    assert readings["device_name"] == "AOT5222ZY"
    assert readings["rx_power"] == -26.382721
    assert readings["onu_id"] == 0
    assert requests == [("GET", "/status.asp", None), ("GET", "/status_pon.asp", None)]


async def test_live_check_returns_failure_on_server_error(onu_server, tmp_path):
    host, state, requests = onu_server
    state["status"] = 500
    returncode, stdout, stderr = await run_status_check(host, tmp_path)
    assert returncode == 1
    assert stdout == ""
    assert "Could not read ONU status:" in stderr
    assert requests == [("GET", "/status.asp", None)]


async def test_live_check_returns_failure_when_credentials_are_required(onu_server, tmp_path):
    host, state, requests = onu_server
    state["form_auth"] = ("test-user", "test-password")
    returncode, stdout, stderr = await run_status_check(host, tmp_path)
    assert returncode == 1
    assert stdout == ""
    assert "Could not read ONU status:" in stderr
    assert state["login_posts"] == []
    assert all(method == "GET" for method, _, _ in requests)
    assert "test-password" not in stderr
