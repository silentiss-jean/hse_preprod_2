#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# -------------------------
# Regex extractors
# -------------------------
RE_CSS_VAR_DEF = re.compile(r"(--[a-zA-Z0-9\-_]+)\s*:")
RE_CSS_VAR_USE = re.compile(r"var\(\s*(--[a-zA-Z0-9\-_]+)\s*\)")

RE_LINK_STYLESHEET_HREF = re.compile(
    r'<link\b[^>]*\brel\s*=\s*["\']stylesheet["\'][^>]*\bhref\s*=\s*["\']([^"\']+)["\'][^>]*>',
    re.IGNORECASE,
)

RE_HTML_CLASS = re.compile(r'class\s*=\s*"([^"]+)"', re.IGNORECASE)
RE_HTML_ID = re.compile(r'id\s*=\s*"([^"]+)"', re.IGNORECASE)

RE_JS_QS = re.compile(r'querySelector(All)?\(\s*["\']([^"\']+)["\']\s*\)')
RE_JS_GETID = re.compile(r'getElementById\(\s*["\']([^"\']+)["\']\s*\)')
RE_JS_CLASSLIST = re.compile(r'classList\.(add|remove|toggle)\(\s*["\']([^"\']+)["\']\s*\)')

RE_CSS_CLASS = re.compile(r"\.([a-zA-Z0-9\-_]+)")
RE_CSS_ID = re.compile(r"#([a-zA-Z0-9\-_]+)")

# Very light CSS rule extractor (not a full parser)
RE_CSS_RULE = re.compile(r"([^{]+)\{([^}]*)\}", re.DOTALL)


# -------------------------
# Helpers
# -------------------------
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write_text(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def write_json(p: Path, obj: Any) -> None:
    write_text(p, json.dumps(obj, indent=2, ensure_ascii=False))


def relpath(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except Exception:
        return str(p)


def should_exclude_path(p: Path, outdir_name: str) -> bool:
    # Exclude the audit output directory from scans to avoid feedback loops.
    # Also exclude typical backup/trash dirs.
    parts = set(p.parts)
    if outdir_name in parts:
        return True
    for bad in (".git", "__pycache__", "node_modules", "dist", "build", "backup", "backups"):
        if bad in parts:
            return True
    return False


def list_files(root: Path, outdir_name: str):
    css = sorted([p for p in root.rglob("*.css") if p.is_file() and not should_exclude_path(p, outdir_name)])
    js = sorted([p for p in root.rglob("*.js") if p.is_file() and not should_exclude_path(p, outdir_name)])
    html = sorted([p for p in root.rglob("*.html") if p.is_file() and not should_exclude_path(p, outdir_name)])
    return css, js, html


def is_feature_css_href(href: str) -> bool:
    return href.replace("\\", "/").startswith("features/") and href.lower().endswith(".css")


def normalize_selector_preview(sel: str, limit: int = 140) -> str:
    s = " ".join(sel.replace("\n", " ").replace("\r", " ").split())
    if len(s) > limit:
        s = s[: limit - 3] + "..."
    return s


# -------------------------
# Index HTML parsing & insertion plan
# -------------------------
@dataclass(frozen=True)
class IndexLink:
    index: int
    href: str
    resolved: str
    exists: bool
    duplicate_of: int | None


def parse_index_links(index_html: str, index_dir: Path) -> tuple[list[IndexLink], list[dict], list[dict]]:
    hrefs = RE_LINK_STYLESHEET_HREF.findall(index_html)
    seen: dict[str, int] = {}
    links: list[IndexLink] = []
    duplicate_links: list[dict] = []
    broken_links: list[dict] = []

    for i, href in enumerate(hrefs):
        resolved = (index_dir / href).resolve()
        exists = resolved.exists()
        dup_of = seen.get(href)
        if dup_of is not None:
            duplicate_links.append({"href": href, "first_index": dup_of, "dup_index": i})
        else:
            seen[href] = i
        if not exists:
            broken_links.append({"href": href, "resolved": str(resolved)})
        links.append(IndexLink(i, href, str(resolved), exists, dup_of))

    return links, duplicate_links, broken_links


def compute_index_insert_anchor(index_html: str) -> dict:
    """
    Returns a deterministic insertion strategy:
    - If at least one <link ... href="features/..."> exists: anchor = last such href.
    - Else: anchor = last stylesheet href (any).
    - Else: anchor = insert before </head>.
    """
    hrefs = RE_LINK_STYLESHEET_HREF.findall(index_html)
    feature_hrefs = [h for h in hrefs if is_feature_css_href(h)]
    if feature_hrefs:
        return {"strategy": "insert_after_href", "href": feature_hrefs[-1]}
    if hrefs:
        return {"strategy": "insert_after_href", "href": hrefs[-1]}
    return {"strategy": "insert_before", "needle": "</head>"}


def ensure_index_link_action(root: Path, index_path: Path, href: str, anchor: dict, action_id: str) -> dict:
    return {
        "id": action_id,
        "type": "ENSURE_INDEX_LINK",
        "target_path": relpath(index_path, root),
        "reason": f"Ajouter la feuille de style manquante dans index.html: {href}",
        "risk": "low",
        "depends_on": [],
        "preconditions": [
            {"type": "FILE_EXISTS", "path": relpath(index_path, root)},
            {"type": "NOT_CONTAINS", "path": relpath(index_path, root), "text": f'href="{href}"'},
            {"type": "CONTAINS", "path": relpath(index_path, root), "text": "<head"},
        ],
        "payload": {
            "href": href,
            "html_to_insert": f'  <link rel="stylesheet" href="{href}">\n',
            "insertion": anchor,
        },
    }


# -------------------------
# Feature modules scan
# -------------------------
def scan_modules(root: Path, features_dir: Path) -> tuple[dict[str, Any], list[str]]:
    modules: dict[str, Any] = {}
    missing_css: list[str] = []

    if not features_dir.exists():
        return modules, missing_css

    for d in sorted([p for p in features_dir.iterdir() if p.is_dir()]):
        name = d.name
        has_js = any(d.glob("*.js"))
        expected_css = d / f"{name}.css"
        has_css_expected = expected_css.exists()

        modules[name] = {
            "path": relpath(d, root),
            "has_js": bool(has_js),
            "expected_css": relpath(expected_css, root),
            "has_expected_css": bool(has_css_expected),
        }
        if has_js and not has_css_expected:
            missing_css.append(name)

    return modules, missing_css


# -------------------------
# CSS variables / theme (improved)
# -------------------------
def extract_defined_vars(css_files: list[Path]) -> set[str]:
    defined: set[str] = set()
    for p in css_files:
        txt = read_text(p)
        defined.update(RE_CSS_VAR_DEF.findall(txt))
    return defined


def extract_css_var_usage_with_context(
    css_files: list[Path],
    root: Path,
    used_classes: set[str],
    used_ids: set[str],
) -> dict[str, Any]:
    """
    Returns:
      {
        "used_variables": set(),
        "evidence": { "--var": [ {file, selector, selector_preview, reachable, reasons}, ... ] }
      }
    """
    used_vars: set[str] = set()
    evidence: dict[str, list[dict[str, Any]]] = {}

    for p in css_files:
        txt = read_text(p)

        for m in RE_CSS_RULE.finditer(txt):
            selector_raw = m.group(1).strip()
            body = m.group(2)

            # Ignore keyframes blocks and similar at-rules (cheap filter)
            if selector_raw.startswith("@"):
                continue

            vars_in_rule = RE_CSS_VAR_USE.findall(body)
            if not vars_in_rule:
                continue

            # Extract tokens from selector(s)
            sel_classes = set(RE_CSS_CLASS.findall(selector_raw))
            sel_ids = set(RE_CSS_ID.findall(selector_raw))

            # Determine reachability
            hit_classes = sorted(sel_classes & used_classes)
            hit_ids = sorted(sel_ids & used_ids)
            reachable = bool(hit_classes or hit_ids)

            reasons: list[str] = []
            if hit_classes:
                reasons.append(f"selector_classes_in_html_or_js={hit_classes[:6]}")
            if hit_ids:
                reasons.append(f"selector_ids_in_html_or_js={hit_ids[:6]}")
            if not reasons:
                reasons.append("no_selector_tokens_found_in_html_or_js")

            preview = normalize_selector_preview(selector_raw)

            for v in vars_in_rule:
                used_vars.add(v)
                evidence.setdefault(v, []).append(
                    {
                        "file": relpath(p, root),
                        "selector_preview": preview,
                        "reachable": reachable,
                        "reasons": reasons,
                    }
                )

    # Deduplicate evidence entries a bit (same file+selector)
    for v, evs in evidence.items():
        seen = set()
        deduped = []
        for e in evs:
            key = (e["file"], e["selector_preview"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(e)
        evidence[v] = deduped[:50]  # cap per var

    return {
        "used_variables": sorted(used_vars),
        "evidence": evidence,
    }


def pick_theme_file(root: Path) -> Path | None:
    candidates = [
        root / "style.hse.themes.css",
        root / "style.hse.core.css",
        root / "style.hse.components.css",
    ]
    for c in candidates:
        if c.exists():
            return c
    css = sorted(root.glob("*.css"))
    return css[0] if css else None


def propose_aliases(undefined_vars: list[str], defined_vars: set[str]) -> tuple[dict[str, str], list[str]]:
    """
    Returns:
    - alias_map: { "--x": "var(--y)" } only when --y exists (low risk)
    - unresolved: vars we couldn't safely map (would be medium risk)
    """
    candidates = {
        "--shadow-md": ["--hse-shadow-md"],
        "--shadow-lg": ["--hse-shadow-lg"],
        "--transition-base": ["--hse-transition-base", "--hse-transition-fast"],
        "--border-radius-sm": ["--hse-radius-sm", "--hse-radius-md"],
        "--bg-secondary": ["--hse-surface-muted", "--hse-bg-secondary", "--hse-surface"],
        "--surface-hover": ["--hse-surface-elevated", "--hse-surface-muted"],
        "--bg-hover": ["--hse-surface-elevated", "--hse-surface-muted"],
        "--warning-bg": ["--hse-warning-soft", "--hse-warning"],
        "--warning-text": ["--hse-warning-text", "--hse-warning", "--hse-text-main"],
        "--danger-bg": ["--hse-danger-soft", "--hse-error-soft", "--hse-danger"],
    }

    alias_map: dict[str, str] = {}
    unresolved: list[str] = []

    for v in undefined_vars:
        opts = candidates.get(v, [])
        target = next((o for o in opts if o in defined_vars), None)
        if target:
            alias_map[v] = f"var({target})"
        else:
            unresolved.append(v)

    return alias_map, unresolved


def theme_alias_action(root: Path, theme_file: Path, alias_map: dict[str, str]) -> dict:
    """
    Adds a marker block to the chosen theme file with aliases.
    Idempotent by marker.
    """
    marker_start = "/* HSE_AUDIT_PHASE1_ALIASES_START */"
    marker_end = "/* HSE_AUDIT_PHASE1_ALIASES_END */"

    lines = [marker_start, ":root {"]
    for k in sorted(alias_map.keys()):
        lines.append(f"  {k}: {alias_map[k]};")
    lines.append("}")
    lines.append(marker_end)
    block = "\n".join(lines) + "\n"

    return {
        "id": "phase1-theme-aliases",
        "type": "ENSURE_THEME_TOKEN_ALIAS",
        "target_path": relpath(theme_file, root),
        "reason": "Définir les variables CSS utilisées mais non définies via alias vers des tokens existants (sans surprise visuelle).",
        "risk": "low",
        "depends_on": [],
        "preconditions": [
            {"type": "FILE_EXISTS", "path": relpath(theme_file, root)},
        ],
        "payload": {
            "marker_start": marker_start,
            "marker_end": marker_end,
            "block": block,
            "strategy": "upsert_marker_block_append",
        },
    }


# -------------------------
# Selectors/token usage (improved: return sets + summary)
# -------------------------
def extract_tokens(html_files: list[Path], js_files: list[Path], css_files: list[Path]) -> dict[str, Any]:
    html_classes, html_ids = set(), set()
    for p in html_files:
        t = read_text(p)
        for m in RE_HTML_CLASS.findall(t):
            html_classes.update([c.strip() for c in m.split() if c.strip()])
        html_ids.update([x.strip() for x in RE_HTML_ID.findall(t) if x.strip()])

    js_classes, js_ids = set(), set()
    for p in js_files:
        t = read_text(p)

        for _, selector in RE_JS_QS.findall(t):
            js_classes.update([m.group(1) for m in re.finditer(r"\.([a-zA-Z0-9\-_]+)", selector)])
            js_ids.update([m.group(1) for m in re.finditer(r"#([a-zA-Z0-9\-_]+)", selector)])

        js_ids.update([x.strip() for x in RE_JS_GETID.findall(t) if x.strip()])
        js_classes.update([m[1].strip() for m in RE_JS_CLASSLIST.findall(t) if m[1].strip()])

    css_classes, css_ids = set(), set()
    for p in css_files:
        t = read_text(p)
        css_classes.update(RE_CSS_CLASS.findall(t))
        css_ids.update(RE_CSS_ID.findall(t))

    used_classes = html_classes | js_classes
    used_ids = html_ids | js_ids

    missing_selectors = sorted({f".{c}" for c in (used_classes - css_classes)} | {f"#{i}" for i in (used_ids - css_ids)})
    dead_selectors = sorted({f".{c}" for c in (css_classes - used_classes)} | {f"#{i}" for i in (css_ids - used_ids)})

    return {
        "html_classes_count": len(html_classes),
        "html_ids_count": len(html_ids),
        "js_classes_count": len(js_classes),
        "js_ids_count": len(js_ids),
        "css_classes_count": len(css_classes),
        "css_ids_count": len(css_ids),
        "missing_selectors_candidates": missing_selectors[:200],
        "dead_css_candidates": dead_selectors[:200],
        "truncated": {
            "missing_selectors_candidates": len(missing_selectors) > 200,
            "dead_css_candidates": len(dead_selectors) > 200,
        },
        # Provide sets for downstream scoring (trim in JSON if you want)
        "sets": {
            "used_classes": sorted(list(used_classes))[:2000],
            "used_ids": sorted(list(used_ids))[:2000],
        },
    }


# -------------------------
# Report generation
# -------------------------
def render_fix_current_md(report: dict[str, Any]) -> str:
    lines = []
    lines.append("# Audit Phase 1 — Fix current\n\n")
    lines.append(f"- Generated at: {report['generated_at']}\n\n")

    lines.append("## Bloquants\n\n")
    lines.append(f"- missing_css_modules: {len(report['missing_css'])}\n")
    if report["missing_css"]:
        lines.append("  - " + ", ".join(report["missing_css"]) + "\n")

    ta = report["theme_analysis"]
    strict_undef = ta.get("undefined_variables_strict", [])
    loose_undef = ta.get("undefined_variables_loose", [])

    lines.append(f"- undefined_css_variables_strict: {len(strict_undef)}\n")
    if strict_undef:
        lines.append("  - " + ", ".join(strict_undef) + "\n")

    lines.append(f"- undefined_css_variables_loose: {len(loose_undef)}\n")
    if loose_undef:
        lines.append("  - " + ", ".join(loose_undef) + "\n")

    broken = report["index"]["broken_links"]
    lines.append(f"- broken_index_links: {len(broken)}\n")
    for b in broken[:20]:
        lines.append(f"  - {b}\n")
    if len(broken) > 20:
        lines.append("  - (truncated)\n")

    lines.append("\n## Warnings\n\n")
    lines.append(f"- duplicate_index_links: {len(report['index']['duplicate_links'])}\n")
    lines.append(f"- unused_css_variables: {len(ta.get('unused_variables', []))}\n")

    lines.append("\n## Notes\n\n")
    lines.append("- Phase 1 ne propose que des actions low-risk (créations vides + alias neutres + liens CSS manquants).\n")
    lines.append("- Les variables undefined “loose” sont des candidats faux-positifs (règles CSS potentiellement inatteignables).\n")
    return "".join(lines)


def render_evolution_md(report: dict[str, Any]) -> str:
    lines = []
    lines.append("# Audit Phase 2 — Evolution plan\n\n")
    lines.append(f"- Generated at: {report['generated_at']}\n\n")
    lines.append("## Opportunités (non bloquantes)\n\n")
    lines.append("- Refactor complet theming (tokens + composants + manifest themes) piloté par customisation.\n")
    lines.append("- Ajout d'effets UI (progress, badges, loaders) via variables.\n")

    lines.append("\n## Contraintes\n\n")
    lines.append("- Max 10 thèmes (existants inclus).\n")
    lines.append("- Ne pas modifier la logique de calcul des coûts (UI seulement).\n")

    lines.append("\n## Questions\n\n")
    for q in report.get("questions", []):
        lines.append(f"- [{q['id']}] {q['text']} (blocking={q['blocking']})\n")
    return "".join(lines)


def build_questions_phase2() -> list[dict]:
    return [
        {
            "id": "theme-mechanism",
            "text": "Phase 2: mécanisme unique de thème (data-theme vs body class) ?",
            "options": ["data-theme", "body-class"],
            "default": "data-theme",
            "blocking": False,
        },
        {
            "id": "theme-count",
            "text": "Phase 2: confirmer le nombre max de thèmes = 10 (existants inclus).",
            "options": ["10"],
            "default": "10",
            "blocking": False,
        },
        {
            "id": "no-cost-mutation",
            "text": "Phase 2: confirmer que tous les changements restent dans web_static (aucun Python/calcul).",
            "options": ["confirm"],
            "default": "confirm",
            "blocking": False,
        },
    ]


# -------------------------
# Plans (actions)
# -------------------------
def build_phase1_actions(
    root: Path,
    index_path: Path,
    missing_css_modules: list[str],
    defined_vars: set[str],
    undefined_vars_strict: list[str],
) -> tuple[list[dict], list[dict]]:
    actions: list[dict] = []
    questions: list[dict] = []

    # 1) Create missing feature CSS files
    for m in missing_css_modules:
        css_rel = f"features/{m}/{m}.css"
        actions.append(
            {
                "id": f"phase1-create-css-{m}",
                "type": "CREATE_FILE",
                "target_path": css_rel,
                "reason": "Convention: chaque module feature doit avoir features/<module>/<module>.css",
                "risk": "low",
                "depends_on": [],
                "preconditions": [
                    {"type": "NOT_EXISTS", "path": css_rel},
                ],
                "payload": {
                    "content": f"/* auto-created by audit phase1: {m} */\n",
                },
            }
        )

    # 2) Ensure links in index.html
    index_html = read_text(index_path) if index_path.exists() else ""
    anchor = compute_index_insert_anchor(index_html)
    for m in missing_css_modules:
        href = f"features/{m}/{m}.css"
        actions.append(ensure_index_link_action(root, index_path, href, anchor, f"phase1-index-link-{m}"))

    # 3) Theme aliases (low-risk only) based on STRICT undefined vars
    theme_file = pick_theme_file(root)
    if not theme_file:
        questions.append(
            {
                "id": "theme-file-missing",
                "text": "Phase 1: aucun fichier de thème détecté pour y ajouter des alias de variables. Où centraliser les variables (style.hse.themes.css) ?",
                "blocking": True,
            }
        )
    else:
        alias_map, unresolved = propose_aliases(undefined_vars_strict, defined_vars)
        if alias_map:
            actions.append(theme_alias_action(root, theme_file, alias_map))
        if unresolved:
            questions.append(
                {
                    "id": "undefined-vars-unresolved",
                    "text": f"Phase 1: variables utilisées mais non définies (strict) non mappées automatiquement: {', '.join(unresolved)}. Souhaites-tu des valeurs par défaut neutres (risque medium) ?",
                    "blocking": True,
                    "vars": unresolved,
                }
            )

    return actions, questions


def build_phase2_actions_stub(root: Path) -> list[dict]:
    return [
        {
            "id": "phase2-create-theme-manifest",
            "type": "CREATE_FILE",
            "target_path": "themes/themes.manifest.json",
            "reason": "Centraliser la liste des thèmes (max 10) + metadata + effets signature.",
            "risk": "high",
            "depends_on": [],
            "preconditions": [{"type": "NOT_EXISTS", "path": "themes/themes.manifest.json"}],
            "payload": {
                "content": json.dumps(
                    {"max_themes": 10, "themes": [], "notes": "Auto-generated stub by audit. Fill in during Phase 2."},
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n"
            },
        }
    ]


# -------------------------
# Main
# -------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Path to web_static/")
    ap.add_argument("--outdir", default="_audit", help="Output dir inside root (excluded from scans)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    outdir = root / args.outdir
    index_path = root / "index.html"
    features_dir = root / "features"

    css_files, js_files, html_files = list_files(root, args.outdir)

    # Index scan
    index_html = read_text(index_path) if index_path.exists() else ""
    links, dup_links, broken_links = (
        parse_index_links(index_html, index_path.parent) if index_html else ([], [], [{"error": "index.html not found"}])
    )

    # Modules scan
    modules, missing_css = scan_modules(root, features_dir)

    # Token scan (needed for reachability scoring)
    selectors_analysis = extract_tokens(html_files, js_files, css_files)
    used_classes = set(selectors_analysis.get("sets", {}).get("used_classes", []))
    used_ids = set(selectors_analysis.get("sets", {}).get("used_ids", []))

    # Vars scan (defined)
    defined_vars = extract_defined_vars(css_files)

    # Vars scan (used with context + evidence)
    usage_ctx = extract_css_var_usage_with_context(css_files, root, used_classes, used_ids)
    used_vars = set(usage_ctx["used_variables"])
    undefined_all = sorted(list(used_vars - defined_vars))
    unused_vars = sorted(list(defined_vars - used_vars))

    # Split strict vs loose undefined based on evidence reachability
    evidence = usage_ctx["evidence"]
    undefined_strict: list[str] = []
    undefined_loose: list[str] = []
    for v in undefined_all:
        evs = evidence.get(v, [])
        if any(e.get("reachable") for e in evs):
            undefined_strict.append(v)
        else:
            undefined_loose.append(v)

    # Build reports objects
    fix_current_report = {
        "version": "1.1",
        "phase": "fix_current",
        "generated_at": now_utc_iso(),
        "root": str(root),
        "index": {
            "css_links": [link.__dict__ for link in links],
            "duplicate_links": dup_links,
            "broken_links": broken_links,
        },
        "modules": modules,
        "missing_css": missing_css,
        "theme_analysis": {
            "defined_variables_count": len(defined_vars),
            "used_variables_count": len(used_vars),
            "undefined_variables_strict": undefined_strict,
            "undefined_variables_loose": undefined_loose,
            "undefined_variables_all": undefined_all,
            "unused_variables": unused_vars,
            "evidence": evidence,  # keyed by var
        },
        "selectors_analysis": selectors_analysis,
    }

    # Phase 1 actions: based on STRICT undefined vars only
    phase1_actions, phase1_questions = build_phase1_actions(root, index_path, missing_css, defined_vars, undefined_strict)
    fix_current_actions = {
        "version": "1.1",
        "phase": "fix_current",
        "generated_at": now_utc_iso(),
        "root": str(root),
        "actions": phase1_actions,
        "questions": phase1_questions,
    }

    # Phase 2 reports (open bar)
    evolution_report = {
        "version": "1.1",
        "phase": "evolution_plan",
        "generated_at": now_utc_iso(),
        "root": str(root),
        "constraints": {
            "max_themes": 10,
            "must_not_affect_costs": True,
            "centralized_by_module": "customisation",
        },
        "facts": {
            "missing_css_modules": missing_css,
            "undefined_css_variables_strict": undefined_strict,
            "undefined_css_variables_loose": undefined_loose,
        },
        "questions": build_questions_phase2(),
    }
    evolution_actions = {
        "version": "1.1",
        "phase": "evolution_plan",
        "generated_at": now_utc_iso(),
        "root": str(root),
        "actions": build_phase2_actions_stub(root),
        "questions": evolution_report["questions"],
    }

    # Write files
    write_json(outdir / "audit_fix_current.json", fix_current_report)
    write_text(outdir / "audit_fix_current.md", render_fix_current_md(fix_current_report))
    write_json(outdir / "audit_fix_current_actions.json", fix_current_actions)

    write_json(outdir / "audit_evolution_plan.json", evolution_report)
    write_text(outdir / "audit_evolution_plan.md", render_evolution_md(evolution_report))
    write_json(outdir / "audit_evolution_plan_actions.json", evolution_actions)

    # Exit codes (strict)
    fail_reasons = []
    if missing_css:
        fail_reasons.append("missing_css")
    if undefined_strict:
        fail_reasons.append("undefined_variables_strict")
    if broken_links and not (len(broken_links) == 1 and "error" in broken_links[0]):
        fail_reasons.append("broken_links")

    # Phase 1 should be green before prod
    if fail_reasons:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
