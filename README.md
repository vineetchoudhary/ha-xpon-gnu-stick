# XPON ONU Stick for Home Assistant

A local, read-only custom integration for the Device Status and PON Status pages on an ONU stick. It connects to the stick's own management web interface, independently of the router, switch, or media converter hosting it. Verified against an **AOT5222ZY running V1.0-220923**. 

## Install

### HACS (recommended)

With [HACS installed and configured](https://www.hacs.xyz/docs/use/), open the repository directly:

[![Open XPON ONU Stick in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vineetchoudhary&repository=ha-xpon-gnu-stick&category=integration)

Select your Home Assistant instance if prompted, download **XPON ONU Stick**, and restart Home Assistant. Then add **XPON ONU Stick** from **Settings → Devices & services → Add integration** and enter your ONU's address and credentials.

Alternatively, add the custom repository manually:

1. Open **HACS** from the Home Assistant sidebar.
2. Open the **⋮** menu in the top-right corner and select **Custom repositories**.
3. Enter `https://github.com/vineetchoudhary/ha-xpon-gnu-stick` as the repository URL.
4. Choose **Integration** as the type/category and click **Add**.
5. Search HACS for **XPON ONU Stick**, open it, and click **Download**.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration**, and search for **XPON ONU Stick**.
8. Enter your ONU's management address (hostname, IP address, or HTTP(S) base URL) and the username/password you use on its login page. The address field starts blank. Leave credentials blank only if the status pages are accessible directly.

### Manual installation

1. Copy `custom_components/xpon_gnu_stick` into Home Assistant's `/config/custom_components/` directory. 
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**, and search for **XPON ONU Stick**.
4. Enter your ONU's management address (hostname, IP address, or HTTP(S) base URL) and the username/password you use on its login page. The address field starts blank. Leave credentials blank only if the status pages are accessible directly.


## Sensors

| Page | Sensor | Unit / format |
| --- | --- | --- |
| Device Status | Device name | Text |
| Device Status | Uptime | Original firmware text, e.g. `1:21` |
| Device Status | Firmware version | Text |
| Device Status | CPU usage | % |
| Device Status | Memory usage | % |
| Device Status | IP address | Text |
| Device Status | Subnet mask | Text |
| Device Status | MAC address | Original firmware text |
| PON Status | Temperature | °C |
| PON Status | Voltage | V |
| PON Status | Tx power | dBm |
| PON Status | Rx power | dBm |
| PON Status | Bias current | mA |
| GPON Status | ONU state | Text, e.g. `O5` |
| GPON Status | ONU ID | Integer, including `0` |
| GPON Status | LOID status | Text, e.g. `Initial Status` |

Numeric measurements retain the precision supplied by the stick and support history/statistics. Suggested display precision keeps the dashboard readable. ONU ID is an identifier, so it does not accumulate statistics. Uptime remains the firmware's original text rather than guessing its format.

Device name, firmware, and LAN information are diagnostic sensors. They are enabled and can still be added to dashboards.

## Refresh and connection settings

The default refresh interval is **30 seconds**. Each poll makes two sequential GET requests shared by all sensors. Change the interval from the integration's options, between 10 and 3600 seconds.

Use **Reconfigure** to change the device address or credentials. Re-enter the password if authentication is enabled. The MAC address provides a stable identity, so changing the management address does not create new entities. A different stick at the same address is rejected instead of overwriting the original device's readings.

## Read-only behavior

The integration reads the two status pages:

- `GET /status.asp`
- `GET /status_pon.asp`

When the stick requests authentication, it also uses `GET /admin/login.asp` and submits **only** the login form with `POST /boaform/admin/formLogin`. It does not submit the status pages' Refresh forms, follow redirects, read settings pages, or expose configuration/reboot controls. Adding or changing the integration's options changes only Home Assistant configuration.

Both pages must be valid before a snapshot is published. When either page is unreachable or invalid, the sensors become unavailable instead of displaying stale readings as current. Polling resumes after ordinary connection failures. Empty or `N/A` readings become unknown, rather than a fabricated zero.

## Dashboard

[`examples/dashboard.yaml`](examples/dashboard.yaml) contains built-in Home Assistant cards for both status pages and a history graph. Paste it into a Manual dashboard card. The example uses the default `sensor.aot5222zy_*` entity IDs. Adjust them if you rename the device/entities or Home Assistant assigns a suffix.

## Development and verification

Run commands from the repository directory. Use **Python 3.14.2 or newer in the 3.14 series** for the pinned Home Assistant test environment. For the first run:

```sh
./scripts/test.sh --setup
```

`--setup` creates `.venv` if needed and installs `requirements-dev.txt`. If Python has a different executable path, use `PYTHON=/path/to/python3.14 ./scripts/test.sh --setup`. A normal run reuses the environment:

```sh
./scripts/test.sh
```

The script checks HACS metadata, repository layout, translations, brand images, installed dependencies, lint, formatting, and the complete test suite. It stops at the first failing check and returns a nonzero exit code. Full output is saved to `.test-results/test-*.log`, including failed runs.


### Test the real stick

To run all checks and then read current Device Status and PON Status values from this computer, pass your ONU management address with `--host`. There is no default address. Replace the example `http://onu.example` below with your device's address:

```sh
./scripts/test.sh --live --host http://onu.example
```

If the stick requires authentication:

```sh
./scripts/test.sh --live --host http://onu.example --username YOUR_USERNAME
```

The script prompts privately for the password, then prints all 16 readings as JSON. Passwords are not passed as command-line arguments or saved in the test log. The live readings themselves are included in the log. A connection, authentication, or parsing failure makes the script fail. Use `./scripts/test.sh --help` for all options.