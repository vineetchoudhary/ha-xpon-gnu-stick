"""Check the repository layout, HACS metadata, translations, and local brand images."""

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/vineetchoudhary/ha-xpon-gnu-stick"


def validate_repository(root: Path) -> None:
    """Raise ValueError for packaging errors before running the simulator suite."""
    components = root / "custom_components"
    integrations = sorted(
        path for path in components.iterdir() if (path / "manifest.json").is_file()
    )
    if len(integrations) != 1:
        raise ValueError("HACS expects one integration under custom_components/.")

    integration = integrations[0]
    manifest = json.loads((integration / "manifest.json").read_text())
    required = {"domain", "name", "version", "documentation", "issue_tracker", "codeowners"}
    if missing := required - manifest.keys():
        raise ValueError(f"Manifest is missing HACS fields: {', '.join(sorted(missing))}.")
    if manifest["domain"] != integration.name:
        raise ValueError("The integration folder must match its manifest domain.")
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]):
        raise ValueError("Use a major.minor.patch version in manifest.json.")
    if (
        manifest["documentation"] != REPOSITORY
        or manifest["issue_tracker"] != f"{REPOSITORY}/issues"
    ):
        raise ValueError("Manifest links must point to the XPON ONU Stick repository.")
    if not manifest["codeowners"] or any(
        not owner.startswith("@") for owner in manifest["codeowners"]
    ):
        raise ValueError("Manifest codeowners must contain GitHub handles starting with @.")

    hacs = json.loads((root / "hacs.json").read_text())
    if hacs.get("name") != manifest["name"]:
        raise ValueError("HACS and Home Assistant display names must match.")
    if hacs.get("content_in_root", False) or hacs.get("zip_release", False):
        raise ValueError("HACS must install from the custom_components folder in this repository.")
    requirements = (root / "requirements-dev.txt").read_text().splitlines()
    if f"homeassistant=={hacs.get('homeassistant')}" not in requirements:
        raise ValueError("The advertised minimum Home Assistant version must be tested.")

    strings = json.loads((integration / "strings.json").read_text())
    english = json.loads((integration / "translations/en.json").read_text())
    if strings != english:
        raise ValueError("English translations must match strings.json.")

    for filename, size in (("icon.png", 256), ("icon@2x.png", 512)):
        with Image.open(integration / "brand" / filename) as icon:
            if icon.format != "PNG" or icon.size != (size, size) or icon.mode != "RGBA":
                raise ValueError(f"brand/{filename} must be a {size}x{size} RGBA PNG.")
            icon.verify()


if __name__ == "__main__":
    try:
        validate_repository(ROOT)
    except (OSError, ValueError, KeyError, TypeError) as err:
        sys.exit(f"Repository validation failed: {err}")
    print("Repository layout, HACS metadata, translations, and brand images are valid.")
