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

### Friendly status sensors

| Sensor | Possible status labels |
| --- | --- |
| Rx power status | Good, Weak signal, Signal too weak, Strong signal, Signal too strong |
| Tx power status | Good, Low transmit power, High transmit power |
| Temperature status | Normal, Cold, Warm, Hot |
| Voltage status | Normal, Low voltage, High voltage |
| Bias current status | Normal, Low current, High current, Limits not set, Invalid reading |
| ONU registration status | Starting up, Waiting for registration, Exchanging serial number, Aligning link timing, Connected, Recovering connection, Disabled by provider, Unrecognized state |

Each status includes a description in its attributes. Measurement statuses also include the original reading and the limits used to classify it. Rx power status includes the margin to each configured limit in dB. Missing measurements become unknown. All sensors share the same two status-page requests.

### Default status limits

Open the integration's options and select **Status limits** to adjust the ranges for your module. Saving limits updates the status sensors in Home Assistant.

| Measurement | Default classification |
| --- | --- |
| Rx power | Below −27 dBm is Signal too weak. From −27 to −25 dBm is Weak signal. Above −25 and below −10 dBm is Good. From −10 to −8 dBm is Strong signal. Above −8 dBm is Signal too strong. |
| Tx power | From +0.5 to +5 dBm is Good. Below this range is Low transmit power. Above it is High transmit power. |
| Temperature | Below 0 °C is Cold. From 0 to below 60 °C is Normal. From 60 to below 70 °C is Warm. At 70 °C or higher it is Hot. |
| Voltage | From 3.135 to 3.465 V is Normal. Below this range is Low voltage. Above it is High voltage. |
| Bias current | Limits not set until you provide both limits from your module's specification. Values within the configured range are Normal. Values outside it are Low current or High current. A negative reading is Invalid reading. |

The optical defaults use the GPON Class B+ ONU reference values in [ITU-T G.984.2, Table A.1](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-G.984.2-201908-I!!PDF-E&lang=e&type=items). The integration does not detect the module's optical class. Change these limits for other classes or manufacturer specifications. The 2 dB receive warning margin is an advisory buffer chosen by this integration. Set it to 0 to disable the Weak signal and Strong signal warnings.

The temperature and voltage defaults are generic guidelines for a commercial 3.3 V SFP module, with a 60 °C warm warning chosen by this integration. For example, the [Fibrain GPON SFP datasheet](https://fibrain.pl/wp-content/uploads/2020/12/DSH_FTS-GPON-OLT-CMAX.pdf) specifies a 0 to 70 °C operating range and a 3.135 to 3.465 V supply range. Internal sensor temperature can differ from the specified ambient or case temperature, so use the limits recommended for your module's reported measurement.

These labels are advisory comparisons. The status pages do not provide the module's factory alarm thresholds, and the integration does not read them from the SFP interface. [SFF-8472, section 9.4](https://members.snia.org/document/dl/25916) defines manufacturer-specific alarm and warning limits, including bias current. There is no single default bias current range suitable for every module.

For example, an Rx reading of −26.38 dBm displays **Weak signal** with the default limits. It is inside the reference range but only about 0.62 dB above the lower limit. This label alone does not mean the connection has failed.

### ONU registration states

The original **ONU state** sensor keeps the firmware's code and gains a description attribute. **ONU registration status** shows its friendly label.

| ONU state | Friendly status | Meaning |
| --- | --- | --- |
| O1 | Starting up | The ONU is initializing and checking its GPON readiness. |
| O2 | Waiting for registration | The ONU receives and responds to the provider's optical signal. |
| O3 | Exchanging serial number | The ONU identifies itself to the provider using its GPON serial number. |
| O4 | Aligning link timing | The provider measures the link delay and adjusts transmission timing. |
| O5 | Connected | The GPON optical connection is established with the provider. |
| O6 | Recovering connection | The ONU is recovering after a loss of signal or framing. |
| O7 | Disabled by provider | Upstream transmission is disabled until the provider enables it. |

O1 to O5 follow the [Zyxel GPON registration guide](https://service-provider.zyxel.com/compact-help/AX-DX-EX-PX-WiFi6-Series/AX-DX-EX-PX_5-70/h_WebTutorials.html). O6 and O7 follow [ITU-T G.984.3, section 10.2.2](https://www.itu.int/rec/dologin_pub.asp?id=T-REC-G.984.3-201401-I!!PDF-E&lang=e&type=items). Connected describes GPON registration and does not test Internet access. Other codes display Unrecognized state, with the original code retained in the attributes.

## Refresh and connection settings

The default refresh interval is **30 seconds**. Each poll makes two sequential GET requests shared by all sensors. Open the integration's options and select **Refresh interval** to change it, between 10 and 3600 seconds. Changing the interval preserves your status limits.

Use **Reconfigure** to change the device address or credentials. Re-enter the password if authentication is enabled. The MAC address provides a stable identity, so changing the management address does not create new entities. A different stick at the same address is rejected instead of overwriting the original device's readings.

## Read-only behavior

The integration reads the two status pages:

- `GET /status.asp`
- `GET /status_pon.asp`

When the stick requests authentication, it also uses `GET /admin/login.asp` and submits **only** the login form with `POST /boaform/admin/formLogin`. It does not submit the status pages' Refresh forms, follow redirects, read settings pages, or expose configuration/reboot controls. Adding or changing the integration's options changes only Home Assistant configuration.

Both pages must be valid before a snapshot is published. When either page is unreachable or invalid, the sensors become unavailable instead of displaying stale readings as current. Polling resumes after ordinary connection failures. Empty or `N/A` readings become unknown, rather than a fabricated zero.

## Dashboard

[`examples/dashboard.yaml`](examples/dashboard.yaml) contains built-in Home Assistant cards for both status pages, the friendly statuses, and a history graph. Paste it into a Manual dashboard card. The example uses the default `sensor.aot5222zy_*` entity IDs. Adjust them if you rename the device/entities or Home Assistant assigns a suffix.

## Development and verification

Run commands from the repository directory. Use **Python 3.14.2 or newer in the 3.14 series** for the pinned Home Assistant test environment. For the first run:

```sh
./scripts/test.sh --setup
```

`--setup` creates `.venv` if needed and installs `requirements-dev.txt`. If Python has a different executable path, use `PYTHON=/path/to/python3.14 ./scripts/test.sh --setup`. A normal run reuses the environment:

```sh
./scripts/test.sh
```

The script checks HACS metadata, repository layout, translations, brand images, installed dependencies, lint, formatting, and the complete test suite. Tests cover status boundaries, ONU state descriptions, shared polling, options form display, and saving or clearing module-specific limits. It stops at the first failing check and returns a nonzero exit code. Full output is saved to `.test-results/test-*.log`, including failed runs.


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
