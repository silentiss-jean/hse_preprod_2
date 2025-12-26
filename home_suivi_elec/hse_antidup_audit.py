#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Home Suivi Élec - Audit anti-duplication (hse_antidup_audit.py)

Objectif:
- Scanner backend + frontend (statique) pour sortir une cartographie "read/write",
  les sources de vérité, et les candidats à déduplication.
- Générer des JSON "decision-ready" pour décider quoi centraliser/supprimer.

Usage:
python3 hse_antidup_audit.py

Options:
python3 hse_antidup_audit.py \
  --backend custom_components/home_suivi_elec \
  --frontend custom_components/home_suivi_elec/web_static \
  --output-dir debug_reports_antidup \
  --ha-config /config \
  --domain homesuivielec \
  --no-backup
"""

import argparse
import ast
import json
import os
import re
import sys
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class AuditConfig:
    backend_path: Path
    frontend_path: Path
    output_dir: Path
    ha_config_path: Optional[Path] = None
    ha_domain: str = "homesuivielec"
    do_backup: bool = True
    backup_dir: Path = field(default_factory=lambda: Path("backups"))
    max_file_bytes: int = 2_000_000  # 2 MB (évite les gros bundles)
    exclude_patterns: List[str] = field(
        default_factory=lambda: [
            "*.backup*",
            "*.old",
            "*.save",
            "*.migrated",
            "*.pyc",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            ".git",
            "*.tar.gz",
            "*backups*",
            "*.min.js",
            "*.map",
        ]
    )


# Heuristiques: "clés" runtime HSE typiques
HASS_DATA_KEYS = [
    "energysensors", "energysensorspending",
    "livepowersensors", "livepowersensorspending",
    "powerenergysensors", "powerenergysensorspending",
    "costsensors", "costsensorspending",
    "addeduids",
    "capteursindex",
    "storagemanager",
    "syncmanager",
]

EVENT_PREFIXES = ["hse"]
EVENT_HINTS = [
    "hseenergysensorsready",
    "hsepowersensorsready",
    "hsepowerenergysensorsready",
    "hsecostsensorsready",
    "hsestoragemigrated",
]

SERVICE_HINTS = [
    "generatelocaldata",
    "generatelovelaceauto",
    "generateselection",
    "copyuifiles",
    "resetintegrationsensor",
    "migratecleanup",
    "exportstoragebackup",
    "rollbacktolegacy",
    "getstoragestats",
]

REST_URL_PREFIX_HINTS = [
    "/api/",
    "apihomesuivielec",
    "api/homesuivielec",
]

FRONTEND_API_HINTS = [
    "ENDPOINTS.",
    "fetch(",
    "/api/",
    "apihomesuivielec",
    "preview",
    "download",
    "yaml",
]


# ============================================================================
# UTILS
# ============================================================================

def debug_print(msg: str) -> None:
    print(msg)

def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def safe_write_json(path: Path, data: Any) -> None:
    safe_mkdir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

def should_exclude(path: Path, patterns: List[str]) -> bool:
    # match() sur Path est "relatif" au path; on utilise aussi un fallback string
    s = str(path)
    for pattern in patterns:
        if path.match(pattern) or s.endswith(pattern.replace("*", "")):
            return True
    return False

def read_text_best_effort(path: Path, limit_bytes: int) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if len(data) > limit_bytes:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")

def make_backup(config: AuditConfig) -> Optional[Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_mkdir(config.backup_dir)
    backup_path = config.backup_dir / f"hse_antidup_audit_{timestamp}.tar.gz"
    root = config.backend_path
    if not root.exists():
        debug_print(f"[backup] Backend introuvable: {root}")
        return None
    debug_print(f"[backup] Création: {backup_path}")
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(str(root), arcname=root.name)
    debug_print("[backup] OK")
    return backup_path

def iter_files(root: Path, exts: Tuple[str, ...], config: AuditConfig) -> Iterable[Path]:
    if not root.exists():
        return []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if should_exclude(p, config.exclude_patterns):
            continue
        if p.suffix.lower() not in exts:
            continue
        try:
            if p.stat().st_size > config.max_file_bytes:
                continue
        except Exception:
            continue
        yield p


# ============================================================================
# BACKEND SCAN (PYTHON)
# ============================================================================

@dataclass
class BackendPyFacts:
    file: str
    size_bytes: int
    lines: int
    # extraction AST
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    ha_services: List[Dict[str, Any]] = field(default_factory=list)
    ha_events_fired: List[str] = field(default_factory=list)
    ha_events_listened: List[str] = field(default_factory=list)
    hass_data_keys_used: List[str] = field(default_factory=list)
    rest_views: List[Dict[str, Any]] = field(default_factory=list)
    json_literals: List[str] = field(default_factory=list)
    store_keys_literals: List[str] = field(default_factory=list)
    storage_manager_calls: List[str] = field(default_factory=list)
    dedup_markers: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

_JSON_RE = re.compile(r"""['"]([^'"]+\.json)['"]""")
_STORE_RE = re.compile(r"""Store\s*\(\s*[^,]+,\s*[^,]+,\s*['"]([^'"]+)['"]\s*\)""")
_HASSDATA_KEY_RE = re.compile(r"""hass\.data(?:\.get|\[).*?['"]([^'"]+)['"]""")
_EVENT_STR_RE = re.compile(r"""['"](hse[a-z0-9_]+)['"]""", re.IGNORECASE)

def _extract_str_constant(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def analyze_python_file(path: Path, root: Path) -> BackendPyFacts:
    content = read_text_best_effort(path, limit_bytes=2_000_000)
    rel = str(path.relative_to(root))
    facts = BackendPyFacts(
        file=rel,
        size_bytes=len(content.encode("utf-8", errors="ignore")),
        lines=len(content.splitlines()),
    )
    if not content.strip():
        facts.issues.append("EmptyOrTooLargeOrUnreadable")
        return facts

    # Cheap regex signals (robustes même si AST casse)
    facts.json_literals = sorted(set(_JSON_RE.findall(content)))
    facts.store_keys_literals = sorted(set(_STORE_RE.findall(content)))

    # hass.data key usage (heuristique)
    hass_keys = set()
    for m in _HASSDATA_KEY_RE.findall(content):
        if m in HASS_DATA_KEYS or m.lower() in HASS_DATA_KEYS:
            hass_keys.add(m)
    # Ajout heuristique: si un mot clé apparait tel quel
    for k in HASS_DATA_KEYS:
        if k in content:
            hass_keys.add(k)
    facts.hass_data_keys_used = sorted(hass_keys)

    # events hints
    events = set()
    for ev in _EVENT_STR_RE.findall(content):
        if any(ev.startswith(p) for p in EVENT_PREFIXES):
            events.add(ev)
    for ev in EVENT_HINTS:
        if ev in content:
            events.add(ev)
    facts.dedup_markers = sorted(set([m for m in ["unique_id", "uniqueid", "dedup", "seedaddeduids"] if m in content]))

    # AST parse
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        facts.issues.append(f"SyntaxError: {e}")
        return facts

    # imports / defs
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            facts.functions.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            facts.functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            facts.classes.append(node.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                facts.imports.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                facts.imports.append(node.module)

    facts.functions = sorted(set(facts.functions))
    facts.classes = sorted(set(facts.classes))
    facts.imports = sorted(set(facts.imports))

    # REST views: classes avec attribut "url" et/ou usage HomeAssistantView dans bases/imports
    # Heuristique: si la classe définit url/name/requires_auth/cors_allowed
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            attrs = {}
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    key = stmt.targets[0].id
                    val = _extract_str_constant(stmt.value)
                    if key in {"url", "name"} and val:
                        attrs[key] = val
            if "url" in attrs or "name" in attrs:
                facts.rest_views.append({"class": node.name, **attrs})

    # Calls: services/events/storage_manager
    # - services: hass.services.async_register(DOMAIN, "xxx", ...)
    # - events fired: hass.bus.async_fire("event", ...)
    # - events listened: hass.bus.async_listen("event", ...)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func

            # hass.services.async_register(...)
            if isinstance(fn, ast.Attribute) and fn.attr == "async_register":
                # best effort: récup arguments str
                args = node.args
                if len(args) >= 2:
                    domain = _extract_str_constant(args[0]) or (args[0].id if isinstance(args[0], ast.Name) else None)
                    service = _extract_str_constant(args[1])
                    if service:
                        facts.ha_services.append({"domain": domain, "service": service, "file": rel})
            # hass.bus.async_fire(...)
            if isinstance(fn, ast.Attribute) and fn.attr in {"async_fire", "async_fire_event"}:
                if node.args:
                    ev = _extract_str_constant(node.args[0])
                    if ev:
                        facts.ha_events_fired.append(ev)
            # hass.bus.async_listen(...)
            if isinstance(fn, ast.Attribute) and fn.attr in {"async_listen", "async_listen_once"}:
                if node.args:
                    ev = _extract_str_constant(node.args[0])
                    if ev:
                        facts.ha_events_listened.append(ev)

            # StorageManager calls: storagemanager.xxx(...)
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                if fn.value.id in {"storagemanager", "storage_manager"}:
                    facts.storage_manager_calls.append(fn.attr)

    facts.ha_events_fired = sorted(set(facts.ha_events_fired + list(events)))
    facts.ha_events_listened = sorted(set(facts.ha_events_listened))
    facts.storage_manager_calls = sorted(set(facts.storage_manager_calls))

    return facts

def scan_backend(config: AuditConfig) -> Dict[str, BackendPyFacts]:
    debug_print("[backend] Scan .py ...")
    out: Dict[str, BackendPyFacts] = {}
    for p in iter_files(config.backend_path, (".py",), config):
        rel = str(p.relative_to(config.backend_path))
        try:
            out[rel] = analyze_python_file(p, config.backend_path)
        except Exception as e:
            out[rel] = BackendPyFacts(file=rel, size_bytes=0, lines=0, issues=[f"Exception: {e}"])
    debug_print(f"[backend] OK ({len(out)} fichiers)")
    return out


# ============================================================================
# FRONTEND SCAN (JS)
# ============================================================================

@dataclass
class FrontendJsFacts:
    file: str
    size_bytes: int
    lines: int
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)          # strings "/api/..." ou "apihomesuivielec..."
    endpoint_constants: List[str] = field(default_factory=list) # "ENDPOINTS.X"
    yaml_markers: List[str] = field(default_factory=list)       # indices génération YAML côté JS
    issues: List[str] = field(default_factory=list)

_IMPORT_RE = re.compile(r"""import\s+(?:{[^}]+}|\w+)\s+from\s+['"]([^'"]+)['"]""")
_EXPORT_RE = re.compile(r"""export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+(\w+)""")
_CLASS_RE = re.compile(r"""class\s+(\w+)""")
_FUNC_RE = re.compile(r"""(?:function\s+(\w+)\s*\(|export\s+function\s+(\w+)\s*\(|const\s+(\w+)\s*=\s*(?:async\s+)?function|const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>)""")
_ENDPOINT_STR_RE = re.compile(r"""['"]((?:/api/|apihomesuivielec)[^'"]+)['"]""")
_ENDPOINTS_CONST_RE = re.compile(r"""\bENDPOINTS\.[A-Z0-9_]+\b""")
_YAML_MARKER_RE = re.compile(r"""\b(yaml|utilitymeter|template\s*sensors|templatesensors)\b""", re.IGNORECASE)

def analyze_js_file(path: Path, root: Path, config: AuditConfig) -> FrontendJsFacts:
    content = read_text_best_effort(path, limit_bytes=config.max_file_bytes)
    rel = str(path.relative_to(root))
    facts = FrontendJsFacts(
        file=rel,
        size_bytes=len(content.encode("utf-8", errors="ignore")),
        lines=len(content.splitlines()),
    )
    if not content.strip():
        facts.issues.append("EmptyOrTooLargeOrUnreadable")
        return facts

    facts.imports = sorted(set(_IMPORT_RE.findall(content)))
    facts.exports = sorted(set(_EXPORT_RE.findall(content)))
    facts.classes = sorted(set(_CLASS_RE.findall(content)))

    # functions: on récupère les groupes non vides
    fn_names = set()
    for m in _FUNC_RE.findall(content):
        for g in m:
            if g:
                fn_names.add(g)
    facts.functions = sorted(fn_names)

    # endpoints / constants
    facts.endpoints = sorted(set(_ENDPOINT_STR_RE.findall(content)))
    facts.endpoint_constants = sorted(set(_ENDPOINTS_CONST_RE.findall(content)))

    # markers YAML (si le JS semble assembler un yaml localement)
    markers = set()
    for m in _YAML_MARKER_RE.findall(content):
        markers.add(m.lower())
    # indices plus concrets: join('\n'), ":\n", "sensor:" etc.
    if "\\n" in content or "join('\\n')" in content or "join(\"\\n\")" in content:
        markers.add("string_join_newline")
    if "download" in content.lower():
        markers.add("download")
    if "preview" in content.lower():
        markers.add("preview")
    facts.yaml_markers = sorted(markers)

    if '"use strict"' not in content[:120]:
        facts.issues.append('Missing "use strict" (heuristique)')

    return facts

def scan_frontend(config: AuditConfig) -> Dict[str, FrontendJsFacts]:
    debug_print("[frontend] Scan .js ...")
    out: Dict[str, FrontendJsFacts] = {}
    for p in iter_files(config.frontend_path, (".js",), config):
        rel = str(p.relative_to(config.frontend_path))
        # filtre: si aucun hint dans le fichier, on peut ignorer pour accélérer
        raw = read_text_best_effort(p, limit_bytes=config.max_file_bytes)
        if raw and not any(h in raw for h in FRONTEND_API_HINTS):
            continue
        try:
            out[rel] = analyze_js_file(p, config.frontend_path, config)
        except Exception as e:
            out[rel] = FrontendJsFacts(file=rel, size_bytes=0, lines=0, issues=[f"Exception: {e}"])
    debug_print(f"[frontend] OK ({len(out)} fichiers)")
    return out


# ============================================================================
# HA STORAGE SCAN (OPTIONAL)
# ============================================================================

_CAMELCASE_RE = re.compile(r"^[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*$")

def _walk_json(obj: Any, path: str = "$") -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _CAMELCASE_RE.match(k):
                hits.append({"path": path, "key": k, "kind": "camelcase_pattern"})
            hits.extend(_walk_json(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_walk_json(v, f"{path}[{i}]"))
    return hits

def scan_ha_storage(config: AuditConfig) -> Dict[str, Any]:
    if not config.ha_config_path:
        return {"enabled": False}

    storage_dir = config.ha_config_path / ".storage"
    report: Dict[str, Any] = {
        "enabled": True,
        "ha_config_path": str(config.ha_config_path),
        "storage_dir": str(storage_dir),
        "files_scanned": 0,
        "core_config_entries": None,
        "integration_store_hits": [],
        "errors": [],
    }

    if not storage_dir.exists():
        report["errors"].append("Missing .storage directory")
        return report

    core = storage_dir / "core.config_entries"
    if core.exists():
        try:
            core_json = json.loads(core.read_text(encoding="utf-8", errors="ignore"))
            hits = _walk_json(core_json, "$")
            report["core_config_entries"] = {
                "path": str(core),
                "hits_total": len(hits),
                "hits_sample": hits[:250],
            }
        except Exception as e:
            report["errors"].append(f"core.config_entries parse error: {e}")
    else:
        report["core_config_entries"] = {"path": str(core), "missing": True}

    # integration stores: best effort
    for p in sorted(storage_dir.glob(f"{config.ha_domain}*")):
        if p.is_dir():
            continue
        report["files_scanned"] += 1
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore").strip()
            if not raw or raw[0] not in "{[":
                continue
            obj = json.loads(raw)
            hits = _walk_json(obj, "$")
            if hits:
                report["integration_store_hits"].append(
                    {"path": str(p), "hits_total": len(hits), "hits_sample": hits[:250]}
                )
        except Exception:
            continue

    return report


# ============================================================================
# BUILD REPORTS (DECISION-READY)
# ============================================================================

def build_backend_index(backend: Dict[str, BackendPyFacts]) -> Dict[str, Any]:
    json_usage = defaultdict(list)
    store_keys = defaultdict(list)
    events_fired = defaultdict(list)
    events_listened = defaultdict(list)
    services = defaultdict(list)
    rest_views = []

    hass_data_usage = defaultdict(list)
    storage_calls = defaultdict(list)

    for rel, f in backend.items():
        for j in f.json_literals:
            json_usage[j].append(rel)
        for k in f.store_keys_literals:
            store_keys[k].append(rel)
        for ev in f.ha_events_fired:
            events_fired[ev].append(rel)
        for ev in f.ha_events_listened:
            events_listened[ev].append(rel)
        for s in f.ha_services:
            services[s.get("service")].append(rel)
        for key in f.hass_data_keys_used:
            hass_data_usage[key].append(rel)
        for c in f.storage_manager_calls:
            storage_calls[c].append(rel)
        for rv in f.rest_views:
            rest_views.append({"file": rel, **rv})

    # normalize & sort
    def pack_map(m: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        out = []
        for k, files in m.items():
            out.append({"key": k, "count_files": len(set(files)), "files": sorted(set(files))})
        out.sort(key=lambda x: (-x["count_files"], x["key"]))
        return out

    return {
        "generated_at": datetime.now().isoformat(),
        "files_scanned": len(backend),
        "json_literals": pack_map(json_usage),
        "store_keys": pack_map(store_keys),
        "events_fired": pack_map(events_fired),
        "events_listened": pack_map(events_listened),
        "services": pack_map(services),
        "hass_data_keys": pack_map(hass_data_usage),
        "storage_manager_calls": pack_map(storage_calls),
        "rest_views": sorted(rest_views, key=lambda x: (x.get("url") or "", x.get("class") or "", x.get("file") or "")),
    }

def build_frontend_index(frontend: Dict[str, FrontendJsFacts]) -> Dict[str, Any]:
    endpoint_strings = defaultdict(list)
    endpoint_consts = defaultdict(list)
    yaml_markers = defaultdict(list)

    for rel, f in frontend.items():
        for e in f.endpoints:
            endpoint_strings[e].append(rel)
        for c in f.endpoint_constants:
            endpoint_consts[c].append(rel)
        for m in f.yaml_markers:
            yaml_markers[m].append(rel)

    def pack_map(m: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        out = []
        for k, files in m.items():
            out.append({"key": k, "count_files": len(set(files)), "files": sorted(set(files))})
        out.sort(key=lambda x: (-x["count_files"], x["key"]))
        return out

    return {
        "generated_at": datetime.now().isoformat(),
        "files_scanned": len(frontend),
        "endpoint_strings": pack_map(endpoint_strings),
        "endpoint_constants": pack_map(endpoint_consts),
        "yaml_markers": pack_map(yaml_markers),
    }

def build_antidup_findings(
    backend_index: Dict[str, Any],
    frontend_index: Dict[str, Any],
    backend: Dict[str, BackendPyFacts],
    frontend: Dict[str, FrontendJsFacts],
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    # 1) JSON files referenced by many backend modules => possible duplicated state
    for item in backend_index.get("json_literals", []):
        if item["count_files"] >= 2:
            findings.append({
                "severity": "MEDIUM",
                "type": "duplicate_data_source_reference",
                "title": f"Fichier JSON référencé par plusieurs modules: {item['key']}",
                "why_it_matters": "Risque de divergence (lecture/écriture non centralisées) et de cache fantôme.",
                "evidence": item,
                "suggested_decision": "Choisir une source de vérité unique + wrapper d'accès (read/write) centralisé.",
            })

    # 2) hass.data keys used in many modules => signal de pipeline dispersé
    for item in backend_index.get("hass_data_keys", []):
        if item["count_files"] >= 3:
            findings.append({
                "severity": "MEDIUM",
                "type": "runtime_state_scattered",
                "title": f"Clé hass.data utilisée dans plusieurs fichiers: {item['key']}",
                "why_it_matters": "Plus il y a d'écrivains/lecteurs, plus le risque de doublons et de comportements non déterministes augmente.",
                "evidence": item,
                "suggested_decision": "Définir un seul module propriétaire de la clé (API interne), les autres consomment via fonctions.",
            })

    # 3) REST endpoints définis en plusieurs classes => vérifier collision / duplication de routes
    rest_views = backend_index.get("rest_views", [])
    url_to_views = defaultdict(list)
    for rv in rest_views:
        url = rv.get("url")
        if url:
            url_to_views[url].append(rv)
    for url, views in url_to_views.items():
        if len(views) >= 2:
            findings.append({
                "severity": "HIGH",
                "type": "duplicate_rest_url",
                "title": f"URL REST définie plusieurs fois: {url}",
                "why_it_matters": "Collision potentielle ou comportement dépendant de l'ordre d'enregistrement.",
                "evidence": {"url": url, "views": views},
                "suggested_decision": "Fusionner / supprimer l'un des endpoints, ou renommer pour éviter collision.",
            })

    # 4) Frontend endpoints/constants éparpillés => source de vérité d'API dispersée
    for item in frontend_index.get("endpoint_constants", []):
        if item["count_files"] >= 4:
            findings.append({
                "severity": "MEDIUM",
                "type": "frontend_api_scattered",
                "title": f"Constante ENDPOINTS utilisée dans beaucoup de fichiers: {item['key']}",
                "why_it_matters": "Risque de versions divergentes (migration vs génération vs debug).",
                "evidence": item,
                "suggested_decision": "Centraliser les appels dans un module API unique par feature + tests.",
            })

    # 5) YAML markers côté frontend => suspicion génération YAML côté client (à confirmer)
    yaml_markers = {i["key"]: i for i in frontend_index.get("yaml_markers", [])}
    if "string_join_newline" in yaml_markers and yaml_markers["string_join_newline"]["count_files"] >= 2:
        findings.append({
            "severity": "MEDIUM",
            "type": "yaml_generated_in_frontend",
            "title": "Indices de génération YAML côté frontend (join('\\n') multiple)",
            "why_it_matters": "Risque preview != export si une partie du YAML est assemblée côté client et une autre côté serveur.",
            "evidence": yaml_markers["string_join_newline"],
            "suggested_decision": "Décider: YAML 100% backend (recommandé) ou 100% frontend, mais pas mixte.",
        })

    # 6) Dédup markers backend => confirmer standard unique_id partout
    # On note où apparaît "dedup" / "uniqueid"
    dedup_files = []
    for rel, f in backend.items():
        if f.dedup_markers:
            dedup_files.append({"file": rel, "markers": f.dedup_markers})
    if dedup_files:
        findings.append({
            "severity": "INFO",
            "type": "dedup_markers",
            "title": "Fichiers impliqués dans la déduplication (unique_id/dedup markers)",
            "why_it_matters": "Permet de vérifier que la règle unique_id est appliquée partout (et pas contournée).",
            "evidence": {"files": dedup_files[:80], "total_files": len(dedup_files)},
            "suggested_decision": "Imposer une fonction utilitaire unique: get_unique_id() + dédup centrale.",
        })

    # Tri global
    sev_rank = {"HIGH": 0, "MEDIUM": 1, "INFO": 2, "LOW": 3}
    findings.sort(key=lambda x: (sev_rank.get(x["severity"], 9), x.get("type", ""), x.get("title", "")))

    return {
        "generated_at": datetime.now().isoformat(),
        "findings": findings,
    }

def build_decision_queue(antidup_findings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforme les findings en une 'file de décisions' ultra simple à valider:
    - id stable
    - question à trancher
    - options proposées
    """
    queue = []
    for i, f in enumerate(antidup_findings.get("findings", []), start=1):
        q = {
            "id": f"DEC-{i:03d}",
            "severity": f.get("severity"),
            "title": f.get("title"),
            "question": None,
            "recommended_default": None,
            "options": [],
            "evidence": f.get("evidence"),
        }

        t = f.get("type")
        if t in {"duplicate_data_source_reference"}:
            q["question"] = "Quelle est la source de vérité pour ce dataset (et qui a le droit d'écrire) ?"
            q["recommended_default"] = "Une seule source persistante + dérivés/caches en lecture seule."
            q["options"] = [
                "Garder JSON comme source de vérité + wrapper unique read/write",
                "Migrer vers StorageManager/Store HA comme source de vérité + générer JSON seulement en export",
                "Supprimer l'artefact si legacy et reconstituer depuis HA runtime",
            ]
        elif t in {"runtime_state_scattered"}:
            q["question"] = "Quel module est propriétaire de cette clé hass.data ?"
            q["recommended_default"] = "Un seul propriétaire; les autres consomment via fonctions."
            q["options"] = [
                "Créer un module 'state_registry.py' propriétaire des clés",
                "Créer une classe manager (ex: SelectionManager/DetectionManager) propriétaire",
            ]
        elif t in {"duplicate_rest_url"}:
            q["question"] = "Faut-il fusionner/renommer ces endpoints pour supprimer la collision ?"
            q["recommended_default"] = "Fusionner si même finalité; sinon renommer route/handler."
            q["options"] = [
                "Fusionner en un endpoint unique",
                "Conserver les 2 mais renommer l'un des URL",
            ]
        elif t in {"yaml_generated_in_frontend"}:
            q["question"] = "Où doit vivre la génération YAML (frontend vs backend) ?"
            q["recommended_default"] = "Backend unique (preview + export identiques)."
            q["options"] = [
                "Backend 100% (recommandé)",
                "Frontend 100% (rarement recommandé)",
            ]
        else:
            q["question"] = "Décision requise ? (sinon ignorer)"
            q["recommended_default"] = "Ignorer si non pertinent."
            q["options"] = ["Ignorer", "Transformer en tâche de refactor"]

        queue.append(q)

    return {
        "generated_at": datetime.now().isoformat(),
        "decisions": queue,
    }


# ============================================================================
# MAIN
# ============================================================================

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Home Suivi Élec - Audit anti-duplication")
    p.add_argument("--backend", type=str, default="custom_components/home_suivi_elec")
    p.add_argument("--frontend", type=str, default="custom_components/home_suivi_elec/web_static")
    p.add_argument("--output-dir", type=str, default="debug_reports_antidup")
    p.add_argument("--ha-config", type=str, default=None, help="Chemin vers /config (Home Assistant)")
    p.add_argument("--domain", type=str, default="homesuivielec", help="Domain HA: homesuivielec / home_suivi_elec")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--max-file-bytes", type=int, default=2_000_000)
    return p.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    config = AuditConfig(
        backend_path=Path(args.backend).resolve(),
        frontend_path=Path(args.frontend).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        ha_config_path=Path(args.ha_config).resolve() if args.ha_config else None,
        ha_domain=args.domain,
        do_backup=not args.no_backup,
        max_file_bytes=int(args.max_file_bytes),
    )

    debug_print("=== HSE Anti-dup Audit ===")
    debug_print(f"Backend : {config.backend_path}")
    debug_print(f"Frontend: {config.frontend_path}")
    debug_print(f"Reports : {config.output_dir}")
    debug_print(f"Backup  : {'oui' if config.do_backup else 'non'}")
    if config.ha_config_path:
        debug_print(f"HA cfg  : {config.ha_config_path} (domain={config.ha_domain})")
    debug_print("==========================")

    if not config.backend_path.exists():
        debug_print(f"[error] Backend introuvable: {config.backend_path}")
        return 1
    if not config.frontend_path.exists():
        debug_print(f"[error] Frontend introuvable: {config.frontend_path}")
        return 1

    if config.do_backup:
        make_backup(config)

    backend = scan_backend(config)
    frontend = scan_frontend(config)

    backend_index = build_backend_index(backend)
    frontend_index = build_frontend_index(frontend)
    ha_storage = scan_ha_storage(config)

    antidup_findings = build_antidup_findings(backend_index, frontend_index, backend, frontend)
    decision_queue = build_decision_queue(antidup_findings)

    safe_write_json(config.output_dir / "backend_index.json", backend_index)
    safe_write_json(config.output_dir / "frontend_index.json", frontend_index)
    safe_write_json(config.output_dir / "ha_storage_scan.json", ha_storage)
    safe_write_json(config.output_dir / "antidup_findings.json", antidup_findings)
    safe_write_json(config.output_dir / "decision_queue.json", decision_queue)

    # Impression courte
    debug_print("")
    debug_print("[done] Rapports générés:")
    debug_print(f" - {config.output_dir / 'backend_index.json'}")
    debug_print(f" - {config.output_dir / 'frontend_index.json'}")
    debug_print(f" - {config.output_dir / 'ha_storage_scan.json'}")
    debug_print(f" - {config.output_dir / 'antidup_findings.json'}")
    debug_print(f" - {config.output_dir / 'decision_queue.json'}")

    # Résumé actionnable: top findings
    top = antidup_findings.get("findings", [])[:10]
    debug_print("")
    debug_print("[top] Findings (max 10):")
    for f in top:
        debug_print(f" - {f.get('severity')}: {f.get('title')}")

    debug_print("")
    debug_print("Ensuite: ouvre decision_queue.json et tranche DEC-001..")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

