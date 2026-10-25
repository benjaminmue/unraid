"""Checks the Community Applications metadata before it reaches main.

CA reads templates/ and plugins/ straight from main, so a broken file or a
template pointing at an image that does not exist goes live for every user.
Exits non-zero with one line per problem.
"""

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_BASE = "https://raw.githubusercontent.com/benjaminmue/unraid/main/"
EM_DASH = "—"
# CA writes a main category as "Backup:" and a subcategory as "Tools:Utilities".
# A trailing colon on a subcategory ("Tools:Utilities:") is not a category CA
# knows, and the app page shows "Template Errors: Unknown category".
CATEGORY = re.compile(r"^[A-Za-z]+:([A-Za-z]+)?$")
problems = []


def parse(path):
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as err:
        problems.append(f"{path.relative_to(ROOT)}: invalid XML: {err}")
        return None


def check_categories(rel, root):
    for token in (root.findtext("Category") or "").split():
        if not CATEGORY.match(token):
            problems.append(f"{rel}: category {token} is not 'Main:' or 'Main:Sub'")


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
    check_categories(rel, root)
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

def plg_url_of(url):
    """The pluginURL a published .plg declares for itself, None if unreadable."""
    try:
        with urllib.request.urlopen(url, timeout=20) as res:
            text = res.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return None
    m = re.search(r'<!ENTITY\s+pluginURL\s+"([^"]+)"', text)
    return m.group(1) if m else None


# Plugin channels: <plugin>.xml installs the .plg from the plugin's main branch,
# <plugin>-beta.xml the one from its beta branch, with the BETA flag. Both .plg
# install under the same plugin name, so one replaces the other; the published
# .plg must name the same URL, or Unraid's update check would follow another
# channel than the entry the user picked.
for path in sorted((ROOT / "plugins").glob("*.xml")):
    rel = path.relative_to(ROOT)
    root = parse(path)
    if root is None:
        continue
    name = (root.findtext("Name") or "").strip()
    url = (root.findtext("PluginURL") or "").strip()
    beta = (root.findtext("Beta") or "").strip().lower() == "true"
    if not name or not url:
        problems.append(f"{rel}: Name and PluginURL are required")
        continue
    if name in names:
        problems.append(f"{rel}: name {name} also used by {names[name]}")
    names[name] = rel
    check_categories(rel, root)
    branch = "beta" if beta else "main"
    if path.stem.endswith("-beta") != beta or f"/refs/heads/{branch}/" not in url:
        problems.append(f"{rel}: file name, Beta={beta} and PluginURL {url} do not match one channel")
    declared = plg_url_of(url)
    if declared != url:
        problems.append(f"{rel}: the .plg at {url} declares pluginURL {declared}")

parse(ROOT / "ca_profile.xml")

for path in sorted(ROOT.rglob("*")):
    if path.suffix in {".xml", ".md", ".json"} and ".git" not in path.parts:
        if EM_DASH in path.read_text(encoding="utf-8"):
            problems.append(f"{path.relative_to(ROOT)}: contains an em-dash, use a hyphen")

for problem in problems:
    print(f"::error::{problem}")
print(f"{len(names)} templates and plugins checked, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
