"""Checks the Community Applications metadata before it reaches main.

CA reads templates/ and plugins/ straight from main, so a broken file or a
template pointing at an image that does not exist goes live for every user.
Exits non-zero with one line per problem.
"""

import json
import pathlib
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_BASE = "https://raw.githubusercontent.com/benjaminmue/unraid/main/"
EM_DASH = "—"
problems = []


def parse(path):
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as err:
        problems.append(f"{path.relative_to(ROOT)}: invalid XML: {err}")
        return None


def ghcr_tag_exists(image):
    """Asks GHCR anonymously whether repository:tag has a manifest."""
    name, _, tag = image.removeprefix("ghcr.io/").rpartition(":")
    token_url = f"https://ghcr.io/token?scope=repository:{name}:pull"
    with urllib.request.urlopen(token_url, timeout=20) as res:
        token = json.load(res)["token"]
    req = urllib.request.Request(
        f"https://ghcr.io/v2/{name}/manifests/{tag}",
        method="HEAD",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": ", ".join([
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.docker.distribution.manifest.v2+json",
            ]),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20):
            return True
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return False
        raise


names, ports = {}, {}
for path in sorted((ROOT / "templates").glob("*.xml")):
    rel = path.relative_to(ROOT)
    root = parse(path)
    if root is None:
        continue
    name = (root.findtext("Name") or "").strip()
    image = (root.findtext("Repository") or "").strip()
    beta = (root.findtext("Beta") or "").strip().lower() == "true"
    template_url = (root.findtext("TemplateURL") or "").strip()

    if not name or not image:
        problems.append(f"{rel}: Name and Repository are required")
        continue
    if name in names:
        problems.append(f"{rel}: Name {name} also used by {names[name]}")
    names[name] = rel
    if template_url != RAW_BASE + rel.as_posix():
        problems.append(f"{rel}: TemplateURL must be {RAW_BASE + rel.as_posix()}")

    # Channel rules: <app>-beta tracks :beta with the BETA flag, <app> tracks
    # :latest without it. Mixing them puts a test build in the release entry.
    tag = image.rpartition(":")[2]
    if name.endswith("-beta") != beta or beta != (tag == "beta"):
        problems.append(f"{rel}: {name} with image tag :{tag} and Beta={beta} do not match")

    for config in root.iter("Config"):
        if config.get("Type") == "Port":
            port = config.get("Default")
            if port in ports:
                problems.append(f"{rel}: default port {port} also used by {ports[port]}")
            ports[port] = rel

    if image.startswith("ghcr.io/") and not ghcr_tag_exists(image):
        problems.append(f"{rel}: image {image} does not exist on GHCR")

for path in sorted((ROOT / "plugins").glob("*.xml")) + [ROOT / "ca_profile.xml"]:
    parse(path)

for path in sorted(ROOT.rglob("*")):
    if path.suffix in {".xml", ".md", ".json"} and ".git" not in path.parts:
        if EM_DASH in path.read_text(encoding="utf-8"):
            problems.append(f"{path.relative_to(ROOT)}: contains an em-dash, use a hyphen")

for problem in problems:
    print(f"::error::{problem}")
print(f"{len(names)} templates checked, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
