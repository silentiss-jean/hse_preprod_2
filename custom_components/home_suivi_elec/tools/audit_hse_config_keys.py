#!/usr/bin/env python3
import ast
import csv
import json
import re
from pathlib import Path

RE_CAMEL = re.compile(r"[A-Z]")
RE_SNAKE = re.compile(r"^[a-z0-9_]+$")

def load_canonical_conf_keys_from_const(const_path: Path) -> set[str]:
    tree = ast.parse(const_path.read_text(encoding="utf-8"), filename=str(const_path))
    canonical = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id.startswith("CONF_"):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    canonical.add(node.value.value)
    return canonical

def classify_key(key: str, canonical: set[str]) -> str:
    if key in canonical:
        return "canonical_v2"
    if RE_CAMEL.search(key):
        return "camelCase"
    if RE_SNAKE.match(key):
        # snake_case mais pas dans la liste canonique -> potentiellement "unknown"
        return "snake_unknown"
    # ex: prixhthc, hcstart (tout en minuscule, sans underscore) => legacy compact
    return "legacy_compact"

def iter_hse_entries(core_config_entries: dict) -> list[dict]:
    # format attendu: {"data": {"entries": [ ... ]}, ...}
    data = core_config_entries.get("data", {})
    entries = data.get("entries", [])
    return [e for e in entries if e.get("domain") == "home_suivi_elec"]

def audit_entry(entry: dict, canonical: set[str]):
    out = []
    entry_id = entry.get("entry_id")
    title = entry.get("title")
    for section in ("data", "options"):
        payload = entry.get(section) or {}
        if not isinstance(payload, dict):
            continue
        for k in sorted(payload.keys()):
            out.append({
                "entry_id": entry_id,
                "title": title,
                "section": section,
                "key": k,
                "classification": classify_key(k, canonical),
            })
    return out

def main():
    hass_config = Path(".")
    core_path = hass_config / ".storage" / "core.config_entries"
    const_path = hass_config / "custom_components" / "home_suivi_elec" / "const.py"

    if not core_path.exists():
        raise SystemExit(f"Missing {core_path}")
    if not const_path.exists():
        raise SystemExit(f"Missing {const_path}")

    core = json.loads(core_path.read_text(encoding="utf-8"))
    canonical = load_canonical_conf_keys_from_const(const_path)

    rows = []
    entries = iter_hse_entries(core)
    for e in entries:
        rows.extend(audit_entry(e, canonical))

    csv_path = Path("audit_hse_keys.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["entry_id", "title", "section", "key", "classification"])
        w.writeheader()
        w.writerows(rows)

    # petit résumé
    counts = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1

    print(f"Wrote {csv_path} ({len(rows)} rows)")
    for k in sorted(counts.keys()):
        print(f"- {k}: {counts[k]}")

    # print les clés non-canoniques les plus importantes
    non = [r for r in rows if r["classification"] != "canonical_v2"]
    if non:
        print("\nNon-canonical keys (sample):")
        for r in non[:50]:
            print(f"{r['section']}.{r['key']} -> {r['classification']} (entry {r['entry_id']})")

if __name__ == "__main__":
    main()
