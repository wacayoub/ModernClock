"""Inspect/install/undo native Enigma2 clock integration. Python 3.8+."""
import argparse
import ast
import datetime
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import re
import shutil
import sys
import types
import xml.etree.ElementTree as ET

MARKER = "# MODERN_CLOCK_NATIVE_1"
LIB = "usr/lib/enigma2/python"
TARGETS = (LIB + "/StartEnigma.py", LIB + "/Screens/Time.py", "usr/share/enigma2/setup.xml")
TIME_WRAPPER = '''# MODERN_CLOCK_NATIVE_1
from importlib.machinery import SourcelessFileLoader
from importlib.util import spec_from_loader, module_from_spec
from os.path import dirname, join

_loader = SourcelessFileLoader("Screens._ModernClockOriginalTime", join(dirname(__file__), "..", "Components", "ModernClock", "original_time.pyc"))
_spec = spec_from_loader(_loader.name, _loader)
_original = module_from_spec(_spec)
_loader.exec_module(_original)

class Time(_original.Time):
    def __init__(self, session):
        _original.Time.__init__(self, session)
        try:
            from Components.ModernClock.native import attach
            attach(self)
        except Exception as clock_error:
            print("[ModernClock] time settings: %s" % clock_error)
'''
ROWS = (
    ("Horloge permanente : activer", "enabled"),
    ("Horloge : style", "style"),
    ("Horloge : police de caracteres", "font"),
    ("Horloge : taille", "size"),
    ("Horloge : couleur des chiffres", "text_color"),
    ("Horloge : opacite des chiffres", "text_opacity"),
    ("Horloge : transparence des chiffres", "text_transparency"),
    ("Horloge : emplacement", "anchor"),
    ("Horloge : afficher les secondes", "seconds"),
    ("Horloge : afficher la date", "date"),
    ("Horloge : format 12 heures", "twelve"),
    ("Horloge : masquer dans les menus", "hide_menus"),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_constructor(source, class_name, lines):
    if MARKER in source:
        raise ValueError("Native integration already present; inspect backup before updating")
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
    if len(classes) != 1:
        raise ValueError("Unsupported image: expected class " + class_name)
    constructors = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name == "__init__"]
    if len(constructors) != 1:
        raise ValueError("Unsupported constructor: " + class_name)
    constructor = constructors[0]
    source_lines = source.splitlines(True)
    first = source_lines[constructor.body[0].lineno - 1]
    indentation = re.match(r"[ \t]*", first).group()
    inserted = indentation + MARKER + "\n"
    inserted += "".join(indentation + line + "\n" for line in lines)
    index = constructor.end_lineno
    if source_lines[index - 1] and not source_lines[index - 1].endswith("\n"):
        source_lines[index - 1] += "\n"
    source_lines.insert(index, inserted)
    result = "".join(source_lines)
    ast.parse(result)
    return result


def patch_setup(source):
    if "config.misc.modernclock." in source:
        raise ValueError("Native clock settings already present")
    root = ET.fromstring(source)
    setups = [element for element in root.iter("setup") if element.attrib.get("key") == "Time"]
    if len(setups) != 1:
        raise ValueError("Unsupported image: expected native Time setup")
    matches = list(re.finditer(r'<setup\b[^>]*\bkey=[\"\']Time[\"\'][^>]*>.*?</setup>', source, re.DOTALL))
    if len(matches) != 1:
        raise ValueError("Cannot locate Time setup safely")
    items = "\n\t\t<!-- Modern Clock native date/time settings -->\n"
    for title, key in ROWS:
        items += '\t\t<item level="0" text="%s">config.misc.modernclock.%s</item>\n' % (title, key)
    match = matches[0]
    section = match.group()
    end = section.rfind("</setup>")
    patched = source[:match.start()] + section[:end] + items + section[end:] + source[match.end():]
    ET.fromstring(patched)
    return patched


def add_presentation_settings(source):
    """Upgrade an existing native Time section without changing other options."""
    root = ET.fromstring(source)
    section = root.find(".//setup[@key='Time']")
    if section is None:
        raise ValueError("Time settings not found")
    matches = list(re.finditer(r'<setup\b[^>]*\bkey=[\"\']Time[\"\'][^>]*>.*?</setup>', source, re.DOTALL))
    if len(matches) != 1:
        raise ValueError("Cannot locate Time settings safely")
    match = matches[0]
    text = match.group()
    additions = ""
    for title, key in ROWS:
        if key in ("style", "font") and "config.misc.modernclock.%s</item>" % key not in text:
            additions += '\n\t\t<item level="0" text="%s">config.misc.modernclock.%s</item>' % (title, key)
    if not additions:
        return source
    anchor = re.search(r'<item\b[^>]*>\s*config\.misc\.modernclock\.enabled\s*</item>', text)
    if anchor is None:
        raise ValueError("Existing native clock settings not found")
    text = text[:anchor.end()] + additions + text[anchor.end():]
    result = source[:match.start()] + text + source[match.end():]
    ET.fromstring(result)
    return result


def prepare(root):
    sources = {}
    for name in TARGETS:
        path = root / name
        if name == TARGETS[1] and not path.exists():
            compiled = path.with_suffix(".pyc")
            data = compiled.read_bytes()
            if data[:4] != importlib.util.MAGIC_NUMBER:
                raise ValueError("Run inspection with the receiver's Python version")
            code = marshal.loads(data[16:])
            classes = [node for node in code.co_consts if isinstance(node, types.CodeType) and node.co_name == "Time"]
            if len(classes) != 1 or "addSaveNotifier" not in next(node for node in classes[0].co_consts if isinstance(node, types.CodeType) and node.co_name == "__init__").co_names:
                raise ValueError("Unsupported compiled Time class")
            sources[name] = None
            continue
        if not path.is_file() or path.is_symlink():
            raise ValueError("Unsupported image or path: " + name)
        sources[name] = path.read_text(encoding="utf-8")
    patched = {
        TARGETS[0]: patch_constructor(sources[TARGETS[0]], "Session", [
            "try:",
            "    from Components.ModernClock.native import start as start_modern_clock",
            "    start_modern_clock(self)",
            "except Exception as clock_error:",
            '    print("[ModernClock] startup: %s" % clock_error)',
        ]),
        TARGETS[1]: TIME_WRAPPER if sources[TARGETS[1]] is None else patch_constructor(sources[TARGETS[1]], "Time", [
            "try:",
            "    from Components.ModernClock.native import attach as attach_modern_clock",
            "    attach_modern_clock(self)",
            "except Exception as clock_error:",
            '    print("[ModernClock] time settings: %s" % clock_error)',
        ]),
        TARGETS[2]: patch_setup(sources[TARGETS[2]]),
    }
    return {name: text.encode("utf-8") for name, text in patched.items()}


def write_atomic(path, data):
    temp = path.with_name(path.name + ".modern-clock-tmp")
    mode = path.stat().st_mode if path.exists() else 0o644
    temp.write_bytes(data)
    os.chmod(str(temp), mode)
    os.replace(str(temp), str(path))


def install(root, payload, replace_legacy=False):
    patched = prepare(root)
    runtime_dir = root / LIB / "Components/ModernClock"
    if runtime_dir.exists():
        raise ValueError("Native clock directory already exists")
    legacy = []
    for name in ("ModernClock", "PermanentClock"):
        if (root / LIB / "Plugins/Extensions" / name).exists():
            if not replace_legacy:
                raise ValueError("Inspect existing %s, then explicitly use --replace-legacy" % name)
            legacy.append(name)
    backup = root / "var/backups" / ("modern-clock-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, str(backup / "restore.py"))
    manifest = {"files": {}, "legacy": legacy}
    compiled_time = (root / TARGETS[1]).with_suffix(".pyc")
    if not (root / TARGETS[1]).exists():
        saved_pyc = backup / LIB / "Screens/Time.pyc"
        saved_pyc.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(compiled_time), str(saved_pyc))
        manifest["compiled_time"] = digest(saved_pyc.read_bytes())
    for name, data in patched.items():
        source = root / name
        saved = backup / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(str(source), str(saved))
        manifest["files"][name] = {"original": digest(saved.read_bytes()) if source.exists() else None, "installed": digest(data)}
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    changed = []
    moved = []
    try:
        runtime_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(payload / "Components/ModernClock"), str(runtime_dir))
        if "compiled_time" in manifest:
            shutil.copy2(str(backup / LIB / "Screens/Time.pyc"), str(runtime_dir / "original_time.pyc"))
        for path in runtime_dir.glob("*.py"):
            compile(path.read_bytes(), str(path), "exec")
        for name, data in patched.items():
            write_atomic(root / name, data)
            changed.append(name)
        for name in legacy:
            origin = root / LIB / "Plugins/Extensions" / name
            if origin.resolve().parent != (root / LIB / "Plugins/Extensions").resolve():
                raise ValueError("Unexpected legacy clock path")
            (backup / "legacy").mkdir(exist_ok=True)
            shutil.move(str(origin), str(backup / "legacy" / name))
            moved.append(name)
    except Exception:
        for name in changed:
            if manifest["files"][name]["original"] is None:
                (root / name).unlink()
            else:
                shutil.copy2(str(backup / name), str(root / name))
        for name in moved:
            shutil.move(str(backup / "legacy" / name), str(root / LIB / "Plugins/Extensions" / name))
        if runtime_dir.is_dir():
            shutil.rmtree(str(runtime_dir))
        raise
    print("Installed native clock; backup: " + str(backup))
    print("GUI has not been restarted by this installer.")


def undo(root, backup):
    backup = backup.resolve()
    if backup.parent != (root / "var/backups").resolve() or not backup.name.startswith("modern-clock-"):
        raise ValueError("Backup must be inside the receiver's var/backups directory")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest["files"]) != set(TARGETS):
        raise ValueError("Unexpected backup file list")
    for name, info in manifest["files"].items():
        if digest((root / name).read_bytes()) != info["installed"]:
            raise ValueError("Image file changed since installation; manual merge required: " + name)
        if info["original"] is not None and digest((backup / name).read_bytes()) != info["original"]:
            raise ValueError("Backup checksum mismatch: " + name)
    if "compiled_time" in manifest:
        saved_pyc = backup / LIB / "Screens/Time.pyc"
        if digest(saved_pyc.read_bytes()) != manifest["compiled_time"]:
            raise ValueError("Original compiled Time module checksum mismatch")
    for name in TARGETS:
        if manifest["files"][name]["original"] is None:
            (root / name).unlink()
        else:
            write_atomic(root / name, (backup / name).read_bytes())
    if "compiled_time" in manifest:
        saved_pyc = backup / LIB / "Screens/Time.pyc"
        write_atomic(root / LIB / "Screens/Time.pyc", saved_pyc.read_bytes())
    for name in manifest.get("legacy", []):
        if name not in ("ModernClock", "PermanentClock"):
            raise ValueError("Unexpected legacy clock name")
        destination = root / LIB / "Plugins/Extensions" / name
        if destination.exists():
            raise ValueError("Legacy clock restored separately; inspect before undo")
        shutil.move(str(backup / "legacy" / name), str(destination))
    # Keep runtime files and backups for recovery; no startup hook references them.
    print("Original system files restored. GUI restart required.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "install", "undo"))
    parser.add_argument("--root", default="/")
    parser.add_argument("--backup")
    parser.add_argument("--replace-legacy", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.action == "inspect":
        patches = prepare(root)
        print(json.dumps({"status": "compatible-source-structure", "python": sys.version.split()[0], "targets": list(patches), "already_installed_clocks": [name for name in ("ModernClock", "PermanentClock") if (root / LIB / "Plugins/Extensions" / name).exists()]}, indent=2))
    elif args.action == "install":
        install(root, Path(__file__).resolve().parent / "payload", args.replace_legacy)
    else:
        if not args.backup:
            parser.error("undo requires --backup")
        undo(root, Path(args.backup))


if __name__ == "__main__":
    main()
