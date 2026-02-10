#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple


ALLOWED_ROOT = Path("custom_components/home_suivi_elec/web_static")

CSS_VAR_USE_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9-_]+)\s*(?:,[^)]+)?\)")
CSS_VAR_DEF_RE = re.compile(r"(--[a-zA-Z0-9-_]+)\s*:")

# Détection "V2 body themes" (body.hsedark, body.hselight, etc.)
BODY_THEME_SELECTOR_RE = re.compile(r"\bbody\.hse[a-zA-Z0-9_-]+\b")

# Indices simple de "v2 body.classList.add('hse...')"
BODY_CLASSLIST_HSE_RE = re.compile(
    r"\bbody\.classList\.(add|remove|toggle)\s*\(\s*['\"]hse[a-zA-Z0-9_-]+['\"]\s*\)"
)

# Indice simple de setAttribute('data-theme', ...)
SET_DATA_THEME_RE = re.compile(r"\bsetAttribute\(\s*['\"]data-theme['\"]\s*,")
DATA_THEME_IN_HTML_RE = re.compile(r"\bdata-theme\s*=")

# Heuristique "couleur codée en dur" — uniquement dans les déclarations (après ":")
# Important: on exige un séparateur après l'hex pour éviter les faux positifs type "#cacheStatsPanel"
HARDCODED_COLOR_RE = re.compile(
    r"(?i)"
    r"(:[^;]*#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})(?=$|[\s,);]))"
    r"|(:[^;]*\brgba?\()"
    r"|(:[^;]*\blinear-gradient\()"
)

HTML_CSS_LINK_RE = re.compile(r'(?i)<link[^>]+rel=["\']stylesheet["\'][^>]*>')
HREF_RE = re.compile(r'(?i)\bhref=["\']([^"\']+)["\']')


# --- Thèmes: autorisés à contenir des couleurs en dur (style.hse.themes*.css)
def is_theme_css_file(p: Path) -> bool:
    return p.name.startswith("style.hse.themes") and p.suffix.lower() == ".css"


@dataclass
class FileReport:
    path: str
    type: str  # css/js/html
    used_vars: List[str]
    defined_vars: List[str]
    v2_body_theme_selectors: List[str]
    hardcoded_colors_count: int
    mentions_data_theme: bool
    suspect_v2_body_classlist: bool
    sets_data_theme: bool


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def normalize_rel(p: Path, root: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)


def scan_css(text: str) -> Tuple[Set[str], Set[str], Set[str], int, bool]:
    used = set(m.group(1) for m in CSS_VAR_USE_RE.finditer(text))
    defined = set(m.group(1) for m in CSS_VAR_DEF_RE.finditer(text))
    v2_selectors = set(BODY_THEME_SELECTOR_RE.findall(text))

    # Retire commentaires multi-lignes pour éviter les faux positifs
    text_no_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    hardcoded_colors = 0
    for line in text_no_comments.splitlines():
        if ":" not in line:
            continue

        # On ne scanne que la valeur (après le ':') pour éviter les #id dans les sélecteurs
        _, value = line.split(":", 1)

        if HARDCODED_COLOR_RE.search(":" + value):
            hardcoded_colors += 1

    mentions_data_theme = bool(DATA_THEME_IN_HTML_RE.search(text))  # rare in css; kept for completeness
    return used, defined, v2_selectors, hardcoded_colors, mentions_data_theme


def scan_js(text: str) -> Tuple[bool, bool, bool]:
    suspect_v2_body_classlist = bool(BODY_CLASSLIST_HSE_RE.search(text))
    sets_data_theme = bool(SET_DATA_THEME_RE.search(text))
    mentions_data_theme = "data-theme" in text
    return suspect_v2_body_classlist, sets_data_theme, mentions_data_theme


def extract_index_links(index_html: str) -> Tuple[List[str], List[str]]:
    css_links: List[str] = []
    js_links: List[str] = []

    # CSS
    for m in HTML_CSS_LINK_RE.finditer(index_html):
        tag = m.group(0)
        href_m = HREF_RE.search(tag)
        if href_m:
            css_links.append(href_m.group(1))

    # JS (simple)
    for m in re.finditer(r'(?i)<script[^>]+src=["\']([^"\']+)["\']', index_html):
        js_links.append(m.group(1))

    return css_links, js_links


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit UI (web_static only): CSS vars, theme patterns, index links.")
    parser.add_argument(
        "root",
        nargs="?",
        default=str(ALLOWED_ROOT),
        help=f"Root directory to scan (default: {ALLOWED_ROOT})",
    )
    parser.add_argument(
        "--mode",
        choices=["report", "gate"],
        default="gate",
        help="report: always exit 0; gate: exit 1 if failures",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default="",
        help="Write full report JSON to this path (optional)",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    allowed = ALLOWED_ROOT.resolve()

    # Safety: refuse scanning outside web_static
    if not is_under(root, allowed) and root != allowed:
        raise SystemExit(f"Refusing to scan outside web_static. Got: {root} Allowed under: {allowed}")

    if not root.exists():
        raise SystemExit(f"Root not found: {root}")

    file_reports: List[FileReport] = []
    all_used_vars: Set[str] = set()
    all_defined_vars: Set[str] = set()

    v2_css_hits: List[Dict[str, object]] = []
    v2_js_hits: List[Dict[str, object]] = []

    # Reporting: on liste TOUS les fichiers ayant des couleurs en dur (y compris thèmes)
    hardcoded_color_files: List[Dict[str, object]] = []

    css_count = js_count = html_count = 0

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue

        _rel = normalize_rel(p, root)
        suffix = p.suffix.lower()

        if suffix == ".css":
            css_count += 1
            text = read_text(p)
            used, defined, v2_selectors, hardcoded_colors, mentions_data_theme = scan_css(text)

            all_used_vars |= used
            all_defined_vars |= defined

            if v2_selectors:
                v2_css_hits.append({"path": str(p), "selectors": sorted(v2_selectors)})

            # IMPORTANT: report = on garde TOUT
            if hardcoded_colors > 0:
                hardcoded_color_files.append({"path": str(p), "count": hardcoded_colors})

            file_reports.append(
                FileReport(
                    path=str(p),
                    type="css",
                    used_vars=sorted(used),
                    defined_vars=sorted(defined),
                    v2_body_theme_selectors=sorted(v2_selectors),
                    hardcoded_colors_count=hardcoded_colors,
                    mentions_data_theme=mentions_data_theme,
                    suspect_v2_body_classlist=False,
                    sets_data_theme=False,
                )
            )

        elif suffix == ".js":
            js_count += 1
            text = read_text(p)
            suspect_v2_body_classlist, sets_data_theme, mentions_data_theme = scan_js(text)

            if suspect_v2_body_classlist:
                v2_js_hits.append({"path": str(p), "suspect_v2_body_classlist": True})

            file_reports.append(
                FileReport(
                    path=str(p),
                    type="js",
                    used_vars=[],
                    defined_vars=[],
                    v2_body_theme_selectors=[],
                    hardcoded_colors_count=0,
                    mentions_data_theme=mentions_data_theme,
                    suspect_v2_body_classlist=suspect_v2_body_classlist,
                    sets_data_theme=sets_data_theme,
                )
            )

        elif suffix == ".html":
            html_count += 1
            text = read_text(p)
            mentions_data_theme = bool(DATA_THEME_IN_HTML_RE.search(text))
            file_reports.append(
                FileReport(
                    path=str(p),
                    type="html",
                    used_vars=[],
                    defined_vars=[],
                    v2_body_theme_selectors=[],
                    hardcoded_colors_count=0,
                    mentions_data_theme=mentions_data_theme,
                    suspect_v2_body_classlist=False,
                    sets_data_theme=False,
                )
            )

    undefined_vars = sorted(all_used_vars - all_defined_vars)

    # index.html checks
    index_path = root / "index.html"
    index_css_links: List[str] = []
    index_js_links: List[str] = []
    index_has_legacy_style_css = False

    if index_path.exists():
        index_html = read_text(index_path)
        index_css_links, index_js_links = extract_index_links(index_html)
        index_has_legacy_style_css = any(link.strip().endswith("style.css") for link in index_css_links)

    failures: List[Dict[str, object]] = []

    if undefined_vars:
        failures.append(
            {
                "rule": "undefined_css_variables",
                "count": len(undefined_vars),
                "vars": undefined_vars,
            }
        )

    if index_has_legacy_style_css:
        failures.append(
            {
                "rule": "index_links_legacy_style_css",
                "hint": "Remove style.css from index.html (keep style.hse.* and feature styles).",
                "links": index_css_links,
            }
        )

    # --- Règle B: hardcoded colors autorisés uniquement dans style.hse.themes*.css
    hardcoded_non_theme = [
        item for item in hardcoded_color_files
        if not is_theme_css_file(Path(item["path"]))
    ]
    if hardcoded_non_theme:
        failures.append(
            {
                "rule": "hardcoded_colors_present",
                "count": len(hardcoded_non_theme),
                "files": hardcoded_non_theme,
                "hint": "Hardcoded colors are allowed only in style.hse.themes*.css",
            }
        )

    report: Dict[str, object] = {
        "root": str(root),
        "mode": args.mode,
        "summary": {
            "counts": {"css": css_count, "js": js_count, "html": html_count},
            "theme": {
                "used_vars_total": len(all_used_vars),
                "defined_vars_total": len(all_defined_vars),
                "undefined_vars": undefined_vars,
            },
        },
        "index": {
            "path": str(index_path) if index_path.exists() else None,
            "css_links": index_css_links,
            "js_links": index_js_links,
            "legacy_style_css_linked": index_has_legacy_style_css,
        },
        "v2_hits": {
            "css": v2_css_hits,
            "js": v2_js_hits,
        },
        "hardcoded_color_files": hardcoded_color_files,
        "files": [fr.__dict__ for fr in file_reports],
        "gate": {
            "pass": len(failures) == 0,
            "failures": failures,
        },
    }

    if args.json_path:
        outp = Path(args.json_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sortie console courte (lisible)
    print(f"[web_static audit] root={root}")
    print(f"- files: css={css_count}, js={js_count}, html={html_count}")
    print(f"- css vars: used={len(all_used_vars)} defined={len(all_defined_vars)} undefined={len(undefined_vars)}")
    if undefined_vars:
        print("  undefined vars:")
        for v in undefined_vars:
            print(f"   - {v}")
    if index_path.exists():
        print(f"- index.html: legacy style.css linked = {index_has_legacy_style_css}")
    if hardcoded_color_files:
        print(f"- hardcoded colors (report): {len(hardcoded_color_files)} file(s)")
    if failures:
        print("- failures:")
        for f in failures:
            print(f"  - {f.get('rule')}")

    if args.mode == "gate" and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
