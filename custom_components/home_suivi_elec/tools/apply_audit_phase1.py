#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALIAS_MARKER_START = "/* HSE_AUDIT_PHASE1_ALIASES_START */"
ALIAS_MARKER_END = "/* HSE_AUDIT_PHASE1_ALIASES_END */"


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write_text(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def load_json(p: Path) -> Any:
    return json.loads(read_text(p))


def ensure_file(path: Path, content: str, dry_run: bool) -> bool:
    if path.exists():
        return False
    if dry_run:
        return True
    write_text(path, content)
    return True


def ensure_link_in_index(index_path: Path, href: str, insert_after_href: str | None, dry_run: bool) -> bool:
    html = read_text(index_path)

    # Already present -> do nothing
    if f'href="{href}"' in html or f"href='{href}'" in html:
        return False

    link_line = f'  <link rel="stylesheet" href="{href}">\n'

    if insert_after_href and (f'href="{insert_after_href}"' in html or f"href='{insert_after_href}'" in html):
        # Insert right after the anchor link occurrence (first match)
        needle1 = f'href="{insert_after_href}"'
        needle2 = f"href='{insert_after_href}'"
        pos = html.find(needle1)
        if pos == -1:
            pos = html.find(needle2)

        # Find end of the <link ...> tag line containing the anchor
        line_end = html.find("\n", pos)
        if line_end == -1:
            line_end = pos
        insert_pos = line_end + 1
        new_html = html[:insert_pos] + link_line + html[insert_pos:]
    else:
        # Fallback: insert before </head>
        head_close = html.lower().rfind("</head>")
        if head_close == -1:
            raise RuntimeError(f"Cannot find </head> in {index_path}")
        new_html = html[:head_close] + link_line + html[head_close:]

    if dry_run:
        return True
    write_text(index_path, new_html)
    return True


def upsert_alias_block(theme_file: Path, alias_map: dict[str, str], dry_run: bool) -> bool:
    txt = read_text(theme_file)

    block_lines = [ALIAS_MARKER_START, ":root {"]
    for k in sorted(alias_map.keys()):
        block_lines.append(f"  {k}: {alias_map[k]};")
    block_lines.append("}")
    block_lines.append(ALIAS_MARKER_END)
    block = "\n".join(block_lines) + "\n"

    if ALIAS_MARKER_START in txt and ALIAS_MARKER_END in txt:
        # Replace existing block
        start = txt.find(ALIAS_MARKER_START)
        end = txt.find(ALIAS_MARKER_END, start)
        end = end + len(ALIAS_MARKER_END)
        new_txt = txt[:start] + block + txt[end:]
    else:
        # Append block at end
        if not txt.endswith("\n"):
            txt += "\n"
        new_txt = txt + "\n" + block

    if new_txt == txt:
        return False
    if dry_run:
        return True
    write_text(theme_file, new_txt)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Path to web_static/")
    ap.add_argument("--actions", required=True, help="Path to audit_fix_current_actions.json")
    ap.add_argument("--theme-file", default="style.hse.themes.css", help="Theme tokens file to patch")
    ap.add_argument("--index", default="index.html", help="Index HTML file")
    ap.add_argument("--dry-run", action="store_true", help="No write, just report")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    actions_path = Path(args.actions).resolve()
    index_path = (root / args.index).resolve()
    theme_path = (root / args.theme_file).resolve()

    plan = load_json(actions_path)
    actions = plan.get("actions", [])

    if not index_path.exists():
        raise SystemExit(f"index.html not found: {index_path}")
    if not theme_path.exists():
        raise SystemExit(f"theme file not found: {theme_path}")

    created_files = []
    updated_index = []
    updated_theme = False

    # Apply CREATE_FILE actions
    for a in actions:
        if a.get("type") != "CREATE_FILE":
            continue
        rel = a["target_path"]
        payload = a.get("payload", {})
        content = payload.get("content", "")
        p = (root / rel).resolve()
        changed = ensure_file(p, content, args.dry_run)
        if changed:
            created_files.append(rel)

    # Apply ENSURE_INDEX_LINK actions
    for a in actions:
        if a.get("type") != "ENSURE_INDEX_LINK":
            continue
        payload = a.get("payload", {})
        href = payload.get("href")
        insertion = payload.get("insertion", {})
        anchor_href = insertion.get("href") if insertion.get("strategy") == "insert_after_href" else None
        changed = ensure_link_in_index(index_path, href, anchor_href, args.dry_run)
        if changed:
            updated_index.append(href)

    # Apply "alias safe OK" block (this corresponds to your choice for unresolved strict vars) [file:139]
    alias_safe = {
        "--hse-accent-alt": "var(--hse-accent)",
        "--hse-error-dark": "var(--hse-error)",
        "--hse-grad-header-from": "var(--hse-accent)",
        "--hse-grad-header-to": "var(--hse-accent-hover)",
    }
    updated_theme = upsert_alias_block(theme_path, alias_safe, args.dry_run)

    # Report
    print("== apply_audit_phase1 ==")
    print(f"root: {root}")
    print(f"dry_run: {args.dry_run}")
    print(f"created_files: {len(created_files)}")
    for x in created_files:
        print(f"  - {x}")
    print(f"index_links_added: {len(updated_index)}")
    for x in updated_index:
        print(f"  - {x}")
    print(f"theme_alias_block_updated: {updated_theme}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
