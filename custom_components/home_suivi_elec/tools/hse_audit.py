#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path("custom_components/home_suivi_elec")
OUT = Path("hse_audit_report.json")

RE_LISTEN = re.compile(r"async_listen\(\s*['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z0-9_]+)", re.I)
RE_FIRE_1 = re.compile(r"async_fire\(\s*['\"]([^'\"]+)['\"]", re.I)
RE_FIRE_2 = re.compile(r"bus\.async_fire\(\s*['\"]([^'\"]+)['\"]", re.I)
RE_ADD_ENT = re.compile(r"\basync_add_entities\(", re.I)

# repère hass.data[...] = ... ou hass.data.get(...).get("xxx") etc.
RE_HASS_DATA_KEY = re.compile(r"hass\.data(?:\.get\([^)]+\))?\s*(?:\[|\.\w+\(|\.get\()\s*['\"]([^'\"]+)['\"]", re.I)

# repère pop("xxx") / get("xxx") sur un dict (utile pour pending pools)
RE_POP_KEY = re.compile(r"\.pop\(\s*['\"]([^'\"]+)['\"]", re.I)
RE_GET_KEY = re.compile(r"\.get\(\s*['\"]([^'\"]+)['\"]", re.I)

def scan_file(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    lines = txt.splitlines()

    listeners = []
    fires = []
    add_entities_lines = []
    hass_data_keys = []
    pops = []
    gets = []

    for i, line in enumerate(lines, start=1):
        m = RE_LISTEN.search(line)
        if m:
            listeners.append({"event": m.group(1), "handler": m.group(2), "line": i, "code": line.strip()})

        if RE_ADD_ENT.search(line):
            add_entities_lines.append({"line": i, "code": line.strip()})

        for r in (RE_FIRE_1, RE_FIRE_2):
            fm = r.search(line)
            if fm:
                fires.append({"event": fm.group(1), "line": i, "code": line.strip()})

        dm = RE_HASS_DATA_KEY.search(line)
        if dm:
            hass_data_keys.append({"key": dm.group(1), "line": i, "code": line.strip()})

        pm = RE_POP_KEY.search(line)
        if pm:
            pops.append({"key": pm.group(1), "line": i, "code": line.strip()})

        gm = RE_GET_KEY.search(line)
        if gm:
            gets.append({"key": gm.group(1), "line": i, "code": line.strip()})

    return {
        "file": str(path),
        "listeners": listeners,
        "fires": fires,
        "async_add_entities": add_entities_lines,
        "hass_data_keys": hass_data_keys,
        "pops": pops,
        "gets": gets,
    }

def main():
    if not ROOT.exists():
        raise SystemExit(f"Chemin introuvable: {ROOT} (lance le script depuis le répertoire HA config)")

    report = {
        "root": str(ROOT),
        "files_scanned": 0,
        "by_file": [],
        "events": {"listeners": {}, "fires": {}},
        "hass_data_keys": {},
        "async_add_entities_files": [],
        "pops_summary": {},
    }

    py_files = sorted([p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts and p.suffix == ".py"])

    for p in py_files:
        data = scan_file(p)
        report["files_scanned"] += 1
        report["by_file"].append(data)

        if data["async_add_entities"]:
            report["async_add_entities_files"].append(str(p))

        for item in data["listeners"]:
            report["events"]["listeners"].setdefault(item["event"], []).append(
                {"file": data["file"], "line": item["line"], "handler": item["handler"]}
            )

        for item in data["fires"]:
            report["events"]["fires"].setdefault(item["event"], []).append(
                {"file": data["file"], "line": item["line"]}
            )

        for item in data["hass_data_keys"]:
            k = item["key"]
            report["hass_data_keys"].setdefault(k, []).append({"file": data["file"], "line": item["line"]})

        for item in data["pops"]:
            k = item["key"]
            report["pops_summary"].setdefault(k, []).append({"file": data["file"], "line": item["line"]})

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {OUT} généré ({report['files_scanned']} fichiers).")
    print("À regarder en priorité : events.listeners / events.fires / async_add_entities_files / pops_summary.")

if __name__ == "__main__":
    main()
