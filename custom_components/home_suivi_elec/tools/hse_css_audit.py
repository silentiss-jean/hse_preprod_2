#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# ----------------------------
# Config
# ----------------------------
TEXT_EXTS = {".html", ".htm", ".js", ".mjs", ".ts", ".jsx", ".tsx"}
CSS_EXTS = {".css"}

DEFAULT_EXCLUDE_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__", ".pytest_cache",
    "node_modules", "dist", "build", ".mypy_cache", ".ruff_cache",
}

# ----------------------------
# IO
# ----------------------------
def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def iter_files(root: Path, exts: set[str], exclude_dirs: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded dirs
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.is_file() and p.suffix.lower() in exts:
                yield p


# ----------------------------
# Token validation / cleaning
# ----------------------------
RE_TEMPLATE_EXPR = re.compile(r"\$\{[^}]*\}")

# Very permissive but still “identifier-ish”
RE_VALID_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
RE_VALID_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

def _strip_templates(s: str) -> str:
    # remove ${...} parts from template literals
    return RE_TEMPLATE_EXPR.sub(" ", s)

def _split_ws(s: str) -> list[str]:
    return [t for t in re.split(r"\s+", s.strip()) if t]

def _add_class_token(out: set[str], token: str):
    t = token.strip()
    if not t:
        return
    if "${" in t:
        return
    if RE_VALID_CLASS.match(t):
        out.add(t)

def _add_id_token(out: set[str], token: str):
    t = token.strip()
    if not t:
        return
    if "${" in t:
        return
    if RE_VALID_ID.match(t):
        out.add(t)


# ----------------------------
# HTML token extraction (strict)
# ----------------------------
RE_HTML_CLASS_ATTR = re.compile(r"<[^>]+\bclass\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.S)
RE_HTML_ID_ATTR = re.compile(r"<[^>]+\bid\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.S)

def extract_tokens_from_htmlish(text: str) -> tuple[set[str], set[str]]:
    classes: set[str] = set()
    ids: set[str] = set()

    for m in RE_HTML_CLASS_ATTR.finditer(text):
        raw = _strip_templates(m.group(2))
        for t in _split_ws(raw):
            _add_class_token(classes, t)

    for m in RE_HTML_ID_ATTR.finditer(text):
        raw = _strip_templates(m.group(2)).strip()
        _add_id_token(ids, raw)

    return classes, ids


# ----------------------------
# JS token extraction (targeted)
# ----------------------------
RE_QUOTED_STRING = re.compile(r'["\']([^"\']*)["\']')
RE_BACKTICK = re.compile(r"`([^`]*)`", re.S)

# classList.add/remove/toggle("a", "b")
RE_CLASSLIST_CALL = re.compile(r"\.classList\.(?:add|remove|toggle)\(([^)]*)\)")
# element.className = "a b" / element.className += " x"
RE_CLASSNAME_ASSIGN = re.compile(r"\.className\s*(?:=|\+=)\s*([\"'`])(.+?)\1", re.S)
# setAttribute("class", "a b") / setAttribute('id', 'x')
RE_SETATTR = re.compile(r"\.setAttribute\(\s*([\"'])(class|id)\1\s*,\s*([\"'`])(.+?)\3\s*\)", re.IGNORECASE | re.S)

# selectors: querySelector(All)(".x #y")
RE_QUERY_SELECTOR = re.compile(r"\.(?:querySelector|querySelectorAll)\(\s*([\"'`])(.+?)\1\s*\)", re.S)
RE_GET_BY_ID = re.compile(r"\.getElementById\(\s*([\"'`])(.+?)\1\s*\)", re.S)
RE_GET_BY_CLASS = re.compile(r"\.getElementsByClassName\(\s*([\"'`])(.+?)\1\s*\)", re.S)

RE_SEL_CLASS = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
RE_SEL_ID = re.compile(r"#([A-Za-z_][A-Za-z0-9_-]*)")

def _extract_quoted_args(arg_blob: str) -> list[str]:
    # Pull "..." and '...' inside a function args blob
    out: list[str] = []
    for s in RE_QUOTED_STRING.findall(arg_blob):
        out.append(s)
    # Also pull `...` template literal bodies (strip ${...})
    for s in RE_BACKTICK.findall(arg_blob):
        out.append(s)
    return out

def extract_tokens_from_js(text: str) -> tuple[set[str], set[str]]:
    classes: set[str] = set()
    ids: set[str] = set()

    # classList.*
    for m in RE_CLASSLIST_CALL.finditer(text):
        for s in _extract_quoted_args(m.group(1)):
            raw = _strip_templates(s)
            for t in _split_ws(raw):
                _add_class_token(classes, t)

    # className = / +=
    for m in RE_CLASSNAME_ASSIGN.finditer(text):
        raw = _strip_templates(m.group(2))
        for t in _split_ws(raw):
            _add_class_token(classes, t)

    # setAttribute("class"/"id", ...)
    for m in RE_SETATTR.finditer(text):
        kind = m.group(2).lower()
        raw = _strip_templates(m.group(4)).strip()
        if kind == "class":
            for t in _split_ws(raw):
                _add_class_token(classes, t)
        else:
            _add_id_token(ids, raw)

    # getElementById("x")
    for m in RE_GET_BY_ID.finditer(text):
        raw = _strip_templates(m.group(2)).strip()
        _add_id_token(ids, raw)

    # getElementsByClassName("a b")
    for m in RE_GET_BY_CLASS.finditer(text):
        raw = _strip_templates(m.group(2))
        for t in _split_ws(raw):
            _add_class_token(classes, t)

    # querySelector(All)(".a #b")
    for m in RE_QUERY_SELECTOR.finditer(text):
        raw = _strip_templates(m.group(2))
        for c in RE_SEL_CLASS.findall(raw):
            _add_class_token(classes, c)
        for i in RE_SEL_ID.findall(raw):
            _add_id_token(ids, i)

    return classes, ids


def extract_tokens_from_text(path: Path, text: str) -> tuple[set[str], set[str]]:
    # Apply both: strict HTMLish + JS patterns (works for .html and .js)
    c1, i1 = extract_tokens_from_htmlish(text)
    c2, i2 = extract_tokens_from_js(text)
    return (c1 | c2), (i1 | i2)


# ----------------------------
# CSS parsing (with @media walk)
# ----------------------------
RE_COMMENT = re.compile(r"/\*.*?\*/", re.S)
RE_PSEUDO = re.compile(r":{1,2}[A-Za-z0-9_-]+(\([^)]*\))?")
RE_ATTR = re.compile(r"\[[^\]]+\]")
RE_STRINGS = re.compile(r'(["\']).*?\1', re.S)

def strip_css_noise(css: str) -> str:
    return RE_COMMENT.sub("", css)

def parse_declarations(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in block.split(";"):
        if ":" not in part:
            continue
        prop, val = part.split(":", 1)
        prop = prop.strip().lower()
        val = val.strip()
        if prop:
            out[prop] = val
    return out

def compute_specificity(selector: str) -> tuple[int, int, int]:
    s = selector
    s = RE_STRINGS.sub("", s)
    s = RE_PSEUDO.sub("", s)
    s = RE_ATTR.sub("", s)

    ids = len(re.findall(r"#[A-Za-z_][\w-]*", s))
    classes = len(re.findall(r"\.[A-Za-z_][\w-]*", s))

    s2 = re.sub(r"[#.][A-Za-z_][\w-]*", " ", s)
    elements = len(re.findall(r"(^|[\s>+~,(])([A-Za-z][A-Za-z0-9_-]*)", s2))
    return (ids, classes, elements)

def _extract_blocks(css: str):
    n = len(css)
    i = 0
    while i < n:
        while i < n and css[i].isspace():
            i += 1
        if i >= n:
            return

        brace = css.find("{", i)
        if brace == -1:
            return

        header = css[i:brace].strip()
        depth = 0
        j = brace
        while j < n:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    body = css[brace + 1:j]
                    yield header, body
                    i = j + 1
                    break
            j += 1
        else:
            return

RE_CLASS_TOKEN = re.compile(r"\.([A-Za-z_][\w-]*)")
RE_ID_TOKEN = re.compile(r"#([A-Za-z_][\w-]*)")

def extract_selector_tokens(selector: str):
    s = RE_PSEUDO.sub("", selector)
    classes = set(RE_CLASS_TOKEN.findall(s))
    ids = set(RE_ID_TOKEN.findall(s))
    return classes, ids

def parse_css_rules(css_text: str, file: str, order_index: int):
    css = strip_css_noise(css_text)
    rules: list[CssRule] = []

    def walk(block_text: str):
        for header, body in _extract_blocks(block_text):
            h = header.strip()
            if not h:
                continue
            hl = h.lstrip().lower()
            if hl.startswith("@"):
                if hl.startswith("@keyframes"):
                    continue
                walk(body)
                continue

            selectors = [s.strip() for s in h.split(",") if s.strip()]
            decls = parse_declarations(body)
            for sel in selectors:
                rules.append(CssRule(
                    selector=sel,
                    declarations=decls,
                    file=file,
                    order_index=order_index,
                    specificity=compute_specificity(sel),
                ))

    walk(css)
    return rules


@dataclass(slots=True)
class CssRule:
    selector: str
    declarations: dict[str, str]
    file: str
    order_index: int
    specificity: tuple[int, int, int]


# ----------------------------
# Harmonization heuristics
# ----------------------------
def is_module_path(path_str: str) -> bool:
    return "/features/" in path_str.replace("\\", "/")

def module_of_path(rel_path: str) -> str | None:
    parts = rel_path.split("/")
    if "features" in parts:
        idx = parts.index("features")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


# ----------------------------
# Categorization (UI types)
# ----------------------------
def categorize_selector(selector: str) -> str:
    s = selector.lower()
    if ".btn" in s or "button" in s:
        return "button"
    if "table" in s or ".table" in s:
        return "table"
    if ".card" in s or "panel" in s or "modal" in s:
        return "container/card/modal"
    if "input" in s or "select" in s or "textarea" in s or ".form" in s:
        return "form"
    if "h1" in s or "h2" in s or "h3" in s or "p" in s or "small" in s or "text" in s:
        return "text"
    return "misc"


# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Path to web_static root")
    ap.add_argument("--audit-json", default=None, help="Path to _audit/audit_fix_current.json (optional)")
    ap.add_argument("--outdir", default="out_css_audit", help="Output directory")
    ap.add_argument("--exclude-dirs", default=",".join(sorted(DEFAULT_EXCLUDE_DIRS)),
                    help="Comma-separated directory names to skip")
    ap.add_argument("--max-workers", type=int, default=0,
                    help="Thread workers for IO (0 = auto)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    exclude_dirs = {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}
    max_workers = args.max_workers if args.max_workers > 0 else None

    # CSS order: from audit json, else alphabetical
    css_order: list[str] = []
    if args.audit_json:
        audit_path = Path(args.audit_json).resolve()
        if audit_path.exists():
            audit = json.loads(read_text(audit_path))
            for item in audit.get("index", {}).get("css_links", []):
                href = item.get("href")
                if href:
                    css_order.append(str((root / href).resolve()))

    if not css_order:
        css_order = [str(p.resolve()) for p in sorted(iter_files(root, CSS_EXTS, exclude_dirs), key=lambda x: str(x))]

    css_index = {p: idx for idx, p in enumerate(css_order)}

    # 1) Scan tokens in text files
    class_usage: dict[str, set[str]] = defaultdict(set)
    id_usage: dict[str, set[str]] = defaultdict(set)

    text_files = list(iter_files(root, TEXT_EXTS, exclude_dirs))

    def scan_text_file(p: Path):
        txt = read_text(p)
        classes, ids = extract_tokens_from_text(p, txt)
        rel = str(p.relative_to(root)).replace("\\", "/")
        return rel, classes, ids

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(scan_text_file, p) for p in text_files]
        for fut in as_completed(futures):
            rel, classes, ids = fut.result()
            for c in classes:
                class_usage[c].add(rel)
            for i in ids:
                id_usage[i].add(rel)

    # 2) Parse CSS rules
    def parse_css_file(abs_path_str: str):
        p = Path(abs_path_str)
        if not p.exists():
            return []
        rel = str(p.relative_to(root)).replace("\\", "/")
        txt = read_text(p)
        return parse_css_rules(txt, rel, css_index.get(abs_path_str, 10_000))

    rules: list[CssRule] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(parse_css_file, css_path_str) for css_path_str in css_order]
        for fut in as_completed(futures):
            rules.extend(fut.result())

    selector_defs: dict[str, list[CssRule]] = defaultdict(list)
    for r in rules:
        selector_defs[r.selector].append(r)

    # A) selector_inventory.csv
    inv_path = outdir / "selector_inventory.csv"
    with inv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "category", "selector", "css_file", "css_order",
            "specificity_id", "specificity_class", "specificity_element",
            "reachable_guess", "matched_classes", "matched_ids",
            "unmatched_classes", "unmatched_ids",
            "decl_count"
        ])

        for r in rules:
            classes, ids = extract_selector_tokens(r.selector)

            matched_c = sorted([c for c in classes if c in class_usage])
            matched_i = sorted([i for i in ids if i in id_usage])
            unmatched_c = sorted([c for c in classes if c not in class_usage])
            unmatched_i = sorted([i for i in ids if i not in id_usage])

            if not classes and not ids:
                reachable = "yes"
            else:
                total = len(classes) + len(ids)
                matched = len(matched_c) + len(matched_i)
                if matched == 0:
                    reachable = "no"
                elif matched == total:
                    reachable = "yes"
                else:
                    reachable = "maybe"

            w.writerow([
                categorize_selector(r.selector),
                r.selector,
                r.file,
                r.order_index,
                r.specificity[0], r.specificity[1], r.specificity[2],
                reachable,
                " ".join(matched_c[:10]),
                " ".join(matched_i[:10]),
                " ".join(unmatched_c[:10]),
                " ".join(unmatched_i[:10]),
                len(r.declarations),
            ])

    # B) token_usage.csv
    tok_path = outdir / "token_usage.csv"
    with tok_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["token_type", "token", "used_in_files_count", "sample_files"])
        for c, files in sorted(class_usage.items(), key=lambda x: (-len(x[1]), x[0])):
            w.writerow(["class", c, len(files), ", ".join(sorted(files)[:5])])
        for i, files in sorted(id_usage.items(), key=lambda x: (-len(x[1]), x[0])):
            w.writerow(["id", i, len(files), ", ".join(sorted(files)[:5])])

    # C) contradictions_same_selector.csv
    contra_path = outdir / "contradictions_same_selector.csv"
    with contra_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["selector", "definitions", "properties_overridden", "files_in_order"])
        for sel, defs in selector_defs.items():
            if len(defs) < 2:
                continue
            defs_sorted = sorted(defs, key=lambda r: r.order_index)
            props: dict[str, list[str]] = defaultdict(list)
            for d in defs_sorted:
                for k, v in d.declarations.items():
                    props[k].append(v)
            overridden = sorted([k for k, vs in props.items() if len(set(vs)) > 1])
            files_order = " -> ".join([d.file for d in defs_sorted])
            w.writerow([sel, len(defs), " ".join(overridden[:30]), files_order])

    # D) harmonization_suggestions.csv
    sugg_path = outdir / "harmonization_suggestions.csv"
    with sugg_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["suggestion_type", "selector", "reason", "current_css_files"])
        for sel, defs in selector_defs.items():
            classes, _ = extract_selector_tokens(sel)
            if not classes:
                continue

            involved_css_files = sorted({d.file for d in defs})
            used_in_files = set()
            for c in classes:
                used_in_files |= class_usage.get(c, set())

            modules = set(filter(None, (module_of_path(u) for u in used_in_files)))

            if len(modules) >= 2 and any(is_module_path(x) for x in involved_css_files):
                w.writerow([
                    "promote_to_base",
                    sel,
                    f"class(es) used in multiple modules: {sorted(modules)[:6]}",
                    ", ".join(involved_css_files),
                ])

            if len(modules) == 1 and any(not is_module_path(x) for x in involved_css_files):
                w.writerow([
                    "move_to_module",
                    sel,
                    f"class(es) appear used only by module: {next(iter(modules))}",
                    ", ".join(involved_css_files),
                ])

    summary = {
        "root": str(root),
        "text_files_count": len(text_files),
        "css_files_count": len(css_order),
        "rules_count": len(rules),
        "unique_selectors": len(selector_defs),
        "unique_classes_seen": len(class_usage),
        "unique_ids_seen": len(id_usage),
        "outdir": str(outdir),
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"OK - reports written to: {outdir}")


if __name__ == "__main__":
    main()
