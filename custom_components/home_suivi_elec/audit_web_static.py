#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = "custom_components/home_suivi_elec/web_static"

CSS_EXT = {".css"}
JS_EXT = {".js"}
HTML_EXT = {".html", ".htm"}

RE_CSS_VAR_USE = re.compile(r"var\(\s*(--[a-zA-Z0-9\-_]+)")
RE_CSS_VAR_DEF = re.compile(r"(--[a-zA-Z0-9\-_]+)\s*:")

# V2 selectors/classes to forbid (Option A)
RE_V2_BODY_THEME_SELECTOR = re.compile(r"\bbody\.hse[_a-zA-Z0-9-]+\b")
RE_V2_HSE_CLASS_TOKEN = re.compile(r"\bhse_(light|dark|ocean|forest|sunset|minimal|neon)\b|\bhse(light|dark|ocean|forest|sunset|minimal|neon)\b", re.IGNORECASE)

# data-theme should exist in JS/CSS world
RE_DATA_THEME_ATTR_SELECTOR = re.compile(r"\[data-theme\s*=\s*['\"][^'\"]+['\"]\]|\bdata-theme\b")
RE_JS_SET_DATA_THEME = re.compile(r"(document\.documentElement|document\.querySelector\(['\"]html['\"]\))\.(setAttribute|dataset)\s*", re.IGNORECASE)

# Hardcoded colors (simple but effective)
RE_COLOR_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RE_COLOR_RGB = re.compile(r"\brgba?\(")
RE_COLOR_HSL = re.compile(r"\bhsla?\(")

# allowlist patterns (shadows etc can be acceptable; tweak later)
ALLOWLIST_COLOR_CONTEXT = [
    re.compile(r"box-shadow\s*:"),
    re.compile(r"text-shadow\s*:"),
]

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def is_allowed_color_line(line: str) -> bool:
    for rx in ALLOWLIST_COLOR_CONTEXT:
        if rx.search(line):
            return True
    return False

def scan_css(path: Path, text: str) -> dict:
    used = sorted(set(RE_CSS_VAR_USE.findall(text)))
    defined = sorted(set(RE_CSS_VAR_DEF.findall(text)))

    v2_selectors = []
    for m in RE_V2_BODY_THEME_SELECTOR.finditer(text):
        v2_selectors.append(m.group(0))

    hardcoded = []
    for i, line in enumerate(text.splitlines(), start=1):
        if is_allowed_color_line(line):
            continue
        if RE_COLOR_HEX.search(line) or RE_COLOR_RGB.search(line) or RE_COLOR_HSL.search(line):
            hardcoded.append({"line": i, "text": line.strip()[:200]})

    has_data_theme = bool(RE_DATA_THEME_ATTR_SELECTOR.search(text))

    return {
        "used_vars": used,
        "defined_vars": defined,
        "v2_body_theme_selectors": sorted(set(v2_selectors)),
        "hardcoded_colors": hardcoded,
        "mentions_data_theme": has_data_theme,
    }

def scan_js(path: Path, text: str) -> dict:
    v2_body_hse = []
    # crude detection of body.classList add/remove with hse
    for i, line in enumerate(text.splitlines(), start=1):
        if "classList" in line and ("hse_" in line or "hsedark" in line or "hselight" in line):
            v2_body_hse.append({"line": i, "text": line.strip()[:200]})

    sets_data_theme = bool(RE_JS_SET_DATA_THEME.search(text)) and ("data-theme" in text or "dataset.theme" in text)

    return {
        "suspect_v2_body_classlist": v2_body_hse,
        "sets_data_theme": sets_data_theme,
    }

def extract_index_links(index_text: str) -> dict:
    # very basic link/script extraction
    css = re.findall(r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)["\']', index_text, flags=re.IGNORECASE)
    js = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', index_text, flags=re.IGNORECASE)
    return {"css_links": css, "js_links": js}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--mode", choices=["report", "gate"], default="gate")
    ap.add_argument("--out", default="audit_web_static_report.json")
    ap.add_argument("--index", default="index.html")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 2

    report = {
        "root": str(root),
        "mode": args.mode,
        "files": {},
        "summary": {},
        "gate": {"pass": True, "failures": []},
    }

    # Scan index.html
    index_path = root / args.index
    index_info = {}
    if index_path.exists():
        t = read_text(index_path)
        index_info = extract_index_links(t)
        report["index"] = {"path": str(index_path), **index_info}
    else:
        report["index"] = {"path": str(index_path), "missing": True}
        report["gate"]["pass"] = False
        report["gate"]["failures"].append({"rule": "index_missing", "path": str(index_path)})

    # Gather files
    all_css = list(root.rglob("*.css"))
    all_js = list(root.rglob("*.js"))
    all_html = [p for ext in HTML_EXT for p in root.rglob(f"*{ext}")]

    used_vars_all = set()
    defined_vars_all = set()

    v2_css_hits = []
    v2_js_hits = []
    hardcoded_color_hits = []

    for p in all_css:
        txt = read_text(p)
        info = scan_css(p, txt)
        report["files"][str(p)] = {"type": "css", **info}
        used_vars_all.update(info["used_vars"])
        defined_vars_all.update(info["defined_vars"])
        if info["v2_body_theme_selectors"]:
            v2_css_hits.append({"path": str(p), "selectors": info["v2_body_theme_selectors"]})
        if info["hardcoded_colors"]:
            hardcoded_color_hits.append({"path": str(p), "count": len(info["hardcoded_colors"]), "examples": info["hardcoded_colors"][:5]})

    for p in all_js:
        txt = read_text(p)
        info = scan_js(p, txt)
        report["files"][str(p)] = {"type": "js", **info}
        if info["suspect_v2_body_classlist"]:
            v2_js_hits.append({"path": str(p), "examples": info["suspect_v2_body_classlist"][:5]})

    undefined_vars = sorted(v for v in used_vars_all if v not in defined_vars_all)

    report["summary"] = {
        "counts": {
            "css": len(all_css),
            "js": len(all_js),
            "html": len(all_html),
        },
        "theme": {
            "used_vars_total": len(used_vars_all),
            "defined_vars_total": len(defined_vars_all),
            "undefined_vars": undefined_vars,
            "v2_css_hits": v2_css_hits,
            "v2_js_hits": v2_js_hits,
            "hardcoded_color_files": hardcoded_color_hits,
        },
    }

    # Gating rules (Option A)
    def fail(rule, details):
        report["gate"]["pass"] = False
        report["gate"]["failures"].append({"rule": rule, **details})

    # Rule: index must not include legacy style.css (adjust if you want to keep temporarily)
    if index_info.get("css_links"):
        if any("style.css" in href for href in index_info["css_links"]):
            fail("index_links_legacy_style_css", {"hint": "Remove style.css from index.html for Option A.", "links": index_info["css_links"]})

    # Rule: no v2 selectors in css
    if v2_css_hits:
        fail("v2_css_body_hse_selectors_present", {"count": len(v2_css_hits), "files": v2_css_hits[:10]})

    # Rule: no v2 body classList usage in js
    if v2_js_hits:
        fail("v2_js_body_classlist_present", {"count": len(v2_js_hits), "files": v2_js_hits[:10]})

    # Rule: no undefined vars
    if undefined_vars:
        fail("undefined_css_variables", {"count": len(undefined_vars), "vars": undefined_vars[:50]})

    # Hardcoded colors: warning in report mode, fail in gate mode (tweak)
    if args.mode == "gate" and hardcoded_color_hits:
        fail("hardcoded_colors_present", {"files": hardcoded_color_hits[:10]})

    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if report["gate"]["pass"]:
        print("PASS: Option A gating OK")
        return 0
    else:
        print("FAIL: Option A gating failed")
        for f in report["gate"]["failures"]:
            print(f"- {f['rule']}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
