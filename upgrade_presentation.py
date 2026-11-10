"""Upgrade an existing native clock with fonts/styles, preserving its settings."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import xml.etree.ElementTree as ET

from install_native import add_presentation_settings, write_atomic

MODULE = Path("/usr/lib/enigma2/python/Components/ModernClock")
SETUP = Path("/usr/share/enigma2/setup.xml")
SETUP_KEY = str(SETUP).lstrip("/")


def preflight(payload):
    if not (MODULE / "original_time.pyc").is_file() or not (MODULE / "native.py").is_file():
        raise ValueError("Existing native integration not found")
    for path in payload.glob("*.py"):
        compile(path.read_bytes(), str(path), "exec")
    source = SETUP.read_text(encoding="utf-8")
    result = add_presentation_settings(source)
    ET.fromstring(result)
    originals = []
    for path in sorted(Path("/var/backups").glob("modern-clock-*/manifest.json")):
        manifest = json.loads(path.read_text())
        if SETUP_KEY in manifest.get("files", {}):
            originals.append((path, manifest))
    if not originals:
        raise ValueError("Original integration backup not found")
    manifest_path, manifest = originals[-1]
    if hashlib.sha256(SETUP.read_bytes()).hexdigest() != manifest["files"][SETUP_KEY]["installed"]:
        raise ValueError("Time settings changed since installation; inspect before upgrading")
    return result.encode("utf-8"), manifest_path, manifest


def upgrade(payload):
    xml, original_manifest, manifest = preflight(payload)
    backup = Path("/var/backups") / ("modernclock-design-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup.mkdir(exist_ok=False)
    shutil.copytree(MODULE, backup / "ModernClock")
    shutil.copy2(SETUP, backup / "setup.xml")
    shutil.copy2(original_manifest, backup / "original-manifest.json")
    (backup / "clock-preferences.json").write_text(json.dumps([line for line in Path("/etc/enigma2/settings").read_text().splitlines() if line.startswith("config.misc.modernclock.")], indent=2))
    try:
        # All images are complete before the new code and options are activated.
        for path in (payload / "glyphs").rglob("*.png"):
            target = MODULE / path.relative_to(payload)
            data = path.read_bytes()
            if target.is_file() and target.read_bytes() == data:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(target, data)
        for path in payload.iterdir():
            if path.is_file() and path.suffix != ".pyc":
                write_atomic(MODULE / path.name, path.read_bytes())
        for path in MODULE.glob("*.py"):
            py_compile.compile(str(path), cfile=str(path.with_suffix(".pyc")), doraise=True)
        write_atomic(SETUP, xml)
        manifest["files"][SETUP_KEY]["installed"] = hashlib.sha256(xml).hexdigest()
        write_atomic(original_manifest, json.dumps(manifest, indent=2).encode())
        os.sync()
    except Exception:
        shutil.copytree(backup / "ModernClock", MODULE, dirs_exist_ok=True)
        shutil.copy2(backup / "setup.xml", SETUP)
        shutil.copy2(backup / "original-manifest.json", original_manifest)
        raise
    print(json.dumps({"upgraded": True, "backup": str(backup), "fonts": 5, "styles": 5, "restart_required": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "install"))
    args = parser.parse_args()
    payload = Path(__file__).resolve().parent / "payload/Components/ModernClock"
    if args.action == "inspect":
        preflight(payload)
        print(json.dumps({"compatible": True, "glyphs": len(list((payload / "glyphs").rglob("*.png")))}))
    else:
        upgrade(payload)
