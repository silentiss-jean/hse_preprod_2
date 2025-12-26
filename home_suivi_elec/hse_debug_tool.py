#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Home Suivi Élec - Outil d'audit/debug anticipatif (hse_debug_tool.py)

Objectifs :

- Faire une sauvegarde complète du backend Home Suivi Élec (avec web_static).
- Analyser backend + frontend pour extraire des invariants structurés.
- Générer des JSON "LLM-ready" pour debugger les exports YAML, la migration,
  et préparer des refactors d'architecture sans reconsommer d'IA.

Usage typique :

python3 hse_debug_tool.py

Options :

python3 hse_debug_tool.py \
  --backend custom_components/home_suivi_elec \
  --frontend custom_components/home_suivi_elec/web_static \
  --output-dir custom_components/home_suivi_elec/debug_reports

python3 hse_debug_tool.py --no-backup # si tu ne veux pas de tar.gz
"""

import argparse
import ast
import json
import os
import re
import sys
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from typing import Tuple

# ============================================================================
# CONFIG
# ============================================================================


@dataclass
class DebugConfig:
    backend_path: Path
    frontend_path: Path
    output_dir: Path
    ha_config_path: Optional[Path] = None
    ha_domain: str = "homesuivielec"
    do_backup: bool = True
    backup_dir: Path = field(default_factory=lambda: Path("backups"))
    # patterns pour ignorer certains fichiers
    exclude_patterns: List[str] = field(
        default_factory=lambda: [
            "*.backup*",
            "*.old",
            "*.save",
            "*.migrated",
            "*before_*",
            "*.pyc",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            ".git",
            "*.tar.gz",
            "*backup_*",
            "*backups*",
            "*.json.migrated",
        ]
    )


# modules backend/JS que l’on considère comme critiques pour ton problème
BACKEND_CRITICAL_FILES = [
    "api/unified_api.py",
    "api/unified_api_extensions.py",
    "manage_selection.py",
    "manage_selection_views.py",
    "manage_selection_views_entity_registry.py",
    "energy_export.py",
    "export.py",
    "storage_manager.py",
    "const.py",
]

FRONTEND_CRITICAL_FILES = [
    "core/app.js",
    "core/router.js",
    "features/generation/generation.js",
    "features/generation/generation.api.js",
    "features/generation/generation.view.js",
    "features/generation/logic/yamlComposer.js",
    "features/generation/logic/templates/overviewCard.js",
    "features/migration/migration.js",
    "features/migration/migration.api.js",
    "features/migration/migration.state.js",
    "features/migration/migration.view.js",
    "features/migration/exporters/utilityMeter.js",
    "features/migration/exporters/templateSensor.js",
    "features/migration/exporters/autoHelper.js",
    "shared/components/DownloadButton.js",
    "shared/views/commonViews.js",
]

# ============================================================================
# CAMELCASE AUDIT (refactor snake_case)
# ============================================================================

# Clés legacy typiques observées dans core.config_entries/options (ex: runtime_snapshot)
LEGACY_CAMELCASE_KEYS = [
    "typeContrat",
    "useExternal",
    "externalCapteur",
    "consommationExterne",
    "abonnementHT",
    "abonnementTTC",
    "enableCostSensorsRuntime",
]

# Pattern générique camelCase: au moins une minuscule suivie d'une Majuscule
CAMELCASE_RE = re.compile(r"^[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*$")


def _is_camelcase_key(k: str) -> bool:
    return bool(CAMELCASE_RE.match(k))


def _walk_json(obj: Any, path: str = "$") -> List[Dict[str, Any]]:
    """
    Retourne une liste d'occurrences de clés camelCase.
    Chaque entrée = {path, key, kind}
    """
    hits: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                if k in LEGACY_CAMELCASE_KEYS:
                    hits.append({"path": path, "key": k, "kind": "legacy_known_key"})
                elif _is_camelcase_key(k):
                    hits.append({"path": path, "key": k, "kind": "camelcase_pattern"})
            hits.extend(_walk_json(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_walk_json(v, f"{path}[{i}]"))
    return hits


def _scan_text_for_legacy_keys(content: str) -> List[str]:
    found = []
    for k in LEGACY_CAMELCASE_KEYS:
        if k in content:
            found.append(k)
    return sorted(set(found))


def scan_code_for_camelcase(
    backend_root: Path,
    frontend_root: Path,
    backend_files: List[str],
    frontend_files: List[str],
) -> Dict[str, Any]:
    report: Dict[str, Any] = {"backend": {}, "frontend": {}}
    for rel in backend_files:
        p = backend_root / rel
        if not p.exists():
            continue
        c = p.read_text(encoding="utf-8", errors="ignore")
        keys = _scan_text_for_legacy_keys(c)
        if keys:
            report["backend"][rel] = {"legacy_keys_found": keys}
    for rel in frontend_files:
        p = frontend_root / rel
        if not p.exists():
            continue
        c = p.read_text(encoding="utf-8", errors="ignore")
        keys = _scan_text_for_legacy_keys(c)
        if keys:
            report["frontend"][rel] = {"legacy_keys_found": keys}
    return report


def scan_ha_storage_for_camelcase(ha_config_path: Path, domain: str) -> Dict[str, Any]:
    """
    - Scan core config entries: <config>/.storage/core.config_entries
    - Scan integration stores: <config>/.storage/<domain>* (best effort)
    """
    storage_dir = ha_config_path / ".storage"
    report: Dict[str, Any] = {
        "ha_config_path": str(ha_config_path),
        "storage_dir": str(storage_dir),
        "core_config_entries": None,
        "integration_store_hits": [],
        "errors": [],
    }

    core = storage_dir / "core.config_entries"
    if core.exists():
        try:
            core_json = json.loads(core.read_text(encoding="utf-8"))
            hits = _walk_json(core_json, "$")
            # Filtrage utile: ne garder que ce qui concerne le domain (si possible)
            report["core_config_entries"] = {
                "path": str(core),
                "hits_total": len(hits),
                "hits": hits[:200],  # limiter pour ne pas exploser la taille du report
            }
        except Exception as e:  # noqa: BLE001
            report["errors"].append(f"core.config_entries read/parse error: {e}")
    else:
        report["core_config_entries"] = {"path": str(core), "missing": True}

    # stores d'intégration (best effort)
    if storage_dir.exists():
        for p in sorted(storage_dir.glob(f"{domain}*")):
            if p.is_dir():
                continue
            try:
                if p.suffix != "" and p.suffix != ".json":
                    continue
                raw = p.read_text(encoding="utf-8", errors="ignore")
                # certains stores HA sont JSON sans extension
                store_json = json.loads(raw)
                hits = _walk_json(store_json, "$")
                if hits:
                    report["integration_store_hits"].append(
                        {"path": str(p), "hits_total": len(hits), "hits": hits[:200]}
                    )
            except Exception:
                # ignore silencieux: certains fichiers non-JSON peuvent matcher le glob
                continue

    return report


# ============================================================================
# UTILITAIRES GÉNÉRAUX
# ============================================================================


def debug_print(msg: str) -> None:
    """Affichage simple, mais centralisé."""
    print(msg)


def should_exclude(path: Path, patterns: List[str]) -> bool:
    for pattern in patterns:
        if path.match(pattern):
            return True
    return False


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_write_json(path: Path, data: Any) -> None:
    safe_mkdir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def make_backup(config: DebugConfig) -> Optional[Path]:
    """Crée un tar.gz du backend (y compris web_static)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_mkdir(config.backup_dir)
    backup_path = config.backup_dir / f"hse_debug_{timestamp}.tar.gz"
    root = config.backend_path
    if not root.exists():
        debug_print(f"[backup] Backend introuvable: {root}")
        return None
    debug_print(f"[backup] Création de la sauvegarde: {backup_path}")
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(str(root), arcname=root.name)
    debug_print("[backup] OK")
    return backup_path


# ============================================================================
# ANALYSEURS BACKEND
# ============================================================================


@dataclass
class PyFileAnalysis:
    path: Path
    relative_path: str
    size: int
    lines: int
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


def analyze_python_file(path: Path, root: Path) -> PyFileAnalysis:
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    rel = str(path.relative_to(root))
    analysis = PyFileAnalysis(
        path=path,
        relative_path=rel,
        size=len(content),
        lines=len(lines),
    )

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        analysis.issues.append(f"SyntaxError: {e}")
        return analysis

    # docstring module
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        analysis.docstring = tree.body[0].value.value

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            analysis.functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            analysis.classes.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                analysis.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                analysis.imports.append(node.module)

    content_lower = content.lower()
    if "async def" in content:
        analysis.patterns.append("Async/Await")
    if "homeassistant.components.http" in content_lower or "HomeAssistantView" in content:
        analysis.patterns.append("REST API View")
    if "StorageManager" in content or "Store(" in content:
        analysis.patterns.append("Storage API")
    if "@callback" in content or "async_track_" in content:
        analysis.patterns.append("Event Listener")
    if "SensorEntity" in content or "CoordinatorEntity" in content:
        analysis.patterns.append("Home Assistant Entity")
    if "TODO" in content or "FIXME" in content:
        analysis.issues.append("Contains TODO/FIXME")

    return analysis


def scan_backend(config: DebugConfig) -> Dict[str, PyFileAnalysis]:
    debug_print("[backend] Analyse des fichiers Python critiques...")
    results: Dict[str, PyFileAnalysis] = {}
    root = config.backend_path

    for rel in BACKEND_CRITICAL_FILES:
        path = root / rel
        if not path.exists():
            continue
        if should_exclude(path, config.exclude_patterns):
            continue
        try:
            analysis = analyze_python_file(path, root)
            results[analysis.relative_path] = analysis
            debug_print(f"[backend] ✓ {analysis.relative_path}")
        except Exception as e:  # noqa: BLE001
            debug_print(f"[backend] ✗ {rel}: {e}")

    return results


def extract_storage_files(backend_analysis: Dict[str, PyFileAnalysis]) -> List[Dict[str, Any]]:
    """Heuristique: cherche les chemins de JSON de sélection/capteurs dans les fichiers."""
    storage_files: Dict[str, Dict[str, Any]] = {}

    for fa in backend_analysis.values():
        content = fa.path.read_text(encoding="utf-8")
        # simples patterns pour détecter des chemins .json
        for match in re.findall(r"['\"]([^'\"]+\.json)['\"]", content):
            # ignore manifest.json
            if "manifest.json" in match:
                continue
            key = match
            if key not in storage_files:
                storage_files[key] = {"path_literal": match, "occurrences": []}
            storage_files[key]["occurrences"].append(fa.relative_path)

    # enrichir avec taille/mtime si chemins absolus/relatifs existants
    enriched = []
    for literal, info in storage_files.items():
        file_path = None

        # on essaie deux choses : chemin relatif au backend, ou sous-dossier data
        candidates = [backend_root / literal for backend_root in [Path(".")]]

        for fa in backend_analysis.values():
            backend_root = fa.path.parents[len(fa.relative_path.split(os.sep)) - 1]
            candidates.append(backend_root / literal)

        for candidate in candidates:
            if candidate.exists():
                file_path = candidate
                break

        entry = {
            "literal": literal,
            "occurrences_in_files": sorted(info["occurrences"]),
            "exists_on_disk": file_path is not None,
        }

        if file_path is not None:
            stat = file_path.stat()
            entry["resolved_path"] = str(file_path)
            entry["size_bytes"] = stat.st_size
            entry["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

        enriched.append(entry)

    return enriched


# ============================================================================
# ANALYSEURS FRONTEND (JS)
# ============================================================================


@dataclass
class JsFileAnalysis:
    path: Path
    relative_path: str
    size: int
    lines: int
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


def analyze_js_file(path: Path, root: Path) -> JsFileAnalysis:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return JsFileAnalysis(
            path=path,
            relative_path=str(path.relative_to(root)),
            size=0,
            lines=0,
            issues=[f"ReadError: {e}"],
        )

    rel = str(path.relative_to(root))
    analysis = JsFileAnalysis(
        path=path,
        relative_path=rel,
        size=len(content),
        lines=len(content.split("\n")),
    )

    # Fonctions (simple, suffisant pour nos besoins)
    func_patterns = [
        r"function\s+(\w+)\s*\(",
        r"const\s+(\w+)\s*=\s*(?:async\s+)?function",
        r"const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
        r"export\s+function\s+(\w+)\s*\(",
    ]
    for pattern in func_patterns:
        try:
            analysis.functions.extend(re.findall(pattern, content))
        except re.error as e:
            analysis.issues.append(f"RegexError(functions): {e}")
    analysis.functions = sorted(set(analysis.functions))

    # Classes
    try:
        analysis.classes = sorted(set(re.findall(r"class\s+(\w+)", content)))
    except re.error:
        pass

    # Imports ES6
    try:
        analysis.imports = re.findall(
            r"import\s+(?:{[^}]+}|\w+)\s+from\s+['\"]([^'\"]+)['\"]", content
        )
    except re.error:
        pass

    # Exports (heuristique)
    try:
        analysis.exports = re.findall(
            r"export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+(\w+)",
            content,
        )
    except re.error:
        pass

    # Quelques issues simples
    if "console.log(" in content:
        analysis.issues.append("Contains console.log")
    if '"use strict"' not in content[:100]:
        analysis.issues.append('Missing "use strict"')

    return analysis


def scan_frontend(config: DebugConfig) -> Dict[str, JsFileAnalysis]:
    debug_print("[frontend] Analyse des fichiers JS critiques...")
    results: Dict[str, JsFileAnalysis] = {}
    root = config.frontend_path

    for rel in FRONTEND_CRITICAL_FILES:
        path = root / rel
        if not path.exists():
            continue
        if should_exclude(path, config.exclude_patterns):
            continue
        try:
            analysis = analyze_js_file(path, root)
            results[analysis.relative_path] = analysis
            debug_print(f"[frontend] ✓ {analysis.relative_path}")
        except Exception as e:  # noqa: BLE001
            debug_print(f"[frontend] ✗ {rel}: {e}")

    return results


def extract_download_flow(frontend_analysis: Dict[str, JsFileAnalysis]) -> Dict[str, Any]:
    """
    Essaie de résumer comment l'export/preview est géré.
    On ne fait que de l'analyse statique simple, mais ça suffit
    pour donner du contexte à l'IA ensuite.
    """
    flow: Dict[str, Any] = {
        "exporters": [],
        "download_button": None,
        "potential_issues": [],
    }

    # Exporters migration
    for rel, fa in frontend_analysis.items():
        if "features/migration/exporters" in rel:
            content = fa.path.read_text(encoding="utf-8", errors="ignore")
            uses_selected = "selectedSensors" in content or "selection" in content
            uses_blob = "new Blob" in content or "URL.createObjectURL" in content
            flow["exporters"].append(
                {
                    "file": rel,
                    "functions": fa.functions,
                    "exports": fa.exports,
                    "uses_selection_words": uses_selected,
                    "uses_blob_or_url": uses_blob,
                }
            )

    # DownloadButton
    for rel, fa in frontend_analysis.items():
        if rel.endswith("shared/components/DownloadButton.js"):
            content = fa.path.read_text(encoding="utf-8", errors="ignore")
            flow["download_button"] = {
                "file": rel,
                "functions": fa.functions,
                "exports": fa.exports,
                "uses_blob": "new Blob" in content,
                "uses_link_href": ".href" in content or "a.href" in content,
            }

    # heuristique preview vs export
    # si on trouve "Preview" dans migration/generation mais aucun exporter qui prend des paramètres,
    # on note une hypothèse potentielle
    preview_in_migration = False
    for rel, fa in frontend_analysis.items():
        if "features/migration" in rel:
            content = fa.path.read_text(encoding="utf-8", errors="ignore")
            if "Preview" in content or "preview" in content:
                preview_in_migration = True
                break

    exporters_take_params = False
    for exp in flow["exporters"]:
        for fn in exp["functions"]:
            # heuristique grossière : si le nom contient "export" ou "build" on suppose que c'est important
            if "export" in fn.lower() or "build" in fn.lower():
                exporters_take_params = True
                break

    if preview_in_migration and not exporters_take_params:
        flow["potential_issues"].append(
            "Preview présent dans migration mais aucun exporter ne semble prendre de paramètres explicites."
        )

    return flow


# ============================================================================
# GÉNÉRATION DES RAPPORTS JSON
# ============================================================================


def build_backend_invariants(backend_analysis: Dict[str, PyFileAnalysis]) -> Dict[str, Any]:
    storage_files = extract_storage_files(backend_analysis)

    rest_endpoints = []
    for rel, fa in backend_analysis.items():
        if "api/" in rel or rel.endswith("views.py"):
            rest_endpoints.append(
                {
                    "file": rel,
                    "functions": fa.functions,
                    "classes": fa.classes,
                    "patterns": fa.patterns,
                    "issues": fa.issues,
                }
            )

    selection_pipeline = []
    for rel, fa in backend_analysis.items():
        if "manage_selection" in rel:
            selection_pipeline.append(
                {
                    "file": rel,
                    "functions": fa.functions,
                    "patterns": fa.patterns,
                    "issues": fa.issues,
                }
            )

    return {
        "generated_at": datetime.now().isoformat(),
        "backend_files_analyzed": sorted(backend_analysis.keys()),
        "storage_files": storage_files,
        "rest_endpoints": rest_endpoints,
        "selection_pipeline": selection_pipeline,
    }


def build_frontend_invariants(frontend_analysis: Dict[str, JsFileAnalysis]) -> Dict[str, Any]:
    modules = []
    for rel, fa in frontend_analysis.items():
        modules.append(
            {
                "file": rel,
                "lines": fa.lines,
                "functions": fa.functions,
                "classes": fa.classes,
                "exports": fa.exports,
                "issues": fa.issues,
            }
        )

    download_flow = extract_download_flow(frontend_analysis)

    return {
        "generated_at": datetime.now().isoformat(),
        "frontend_files_analyzed": sorted(frontend_analysis.keys()),
        "modules": modules,
        "download_flow": download_flow,
    }


def build_export_issue_hypotheses(
    backend_invariants: Dict[str, Any],
    frontend_invariants: Dict[str, Any],
) -> Dict[str, Any]:
    hypotheses: List[Dict[str, Any]] = []

    # Hypothèse 1 : incohérence preview/export
    download_flow = frontend_invariants.get("download_flow", {})
    exporters = download_flow.get("exporters", [])
    potential_issues = download_flow.get("potential_issues", [])
    hypotheses.append(
        {
            "id": "preview_export_inconsistency",
            "description": (
                "Vérifier si la fonction utilisée pour la preview YAML est la même "
                "que celle utilisée pour l'export (fichier téléchargé)."
            ),
            "evidence": {
                "exporters_files": [e["file"] for e in exporters],
                "download_button": download_flow.get("download_button"),
                "potential_issues": potential_issues,
            },
        }
    )

    # Hypothèse 2 : mauvais fichier JSON de sélection
    storage_files = backend_invariants.get("storage_files", [])
    selection_candidates = [
        sf for sf in storage_files if "selection" in sf["literal"].lower()
    ]
    hypotheses.append(
        {
            "id": "selection_json_mismatch",
            "description": (
                "Vérifier que le fichier JSON de sélection utilisé pour la migration "
                "et pour la génération YAML est bien le même, et qu'il contient les capteurs attendus."
            ),
            "evidence": selection_candidates,
        }
    )

    # Hypothèse 3 : endpoints REST non alignés
    rest_endpoints = backend_invariants.get("rest_endpoints", [])
    hypotheses.append(
        {
            "id": "rest_endpoint_alignment",
            "description": (
                "Contrôler l'alignement entre les endpoints REST (GET/POST) utilisés "
                "par les features 'génération' et 'migration', pour éviter que l'une "
                "des deux lise un format ou fichier différent."
            ),
            "evidence": rest_endpoints,
        }
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "hypotheses": hypotheses,
    }


def build_refactor_plan(
    backend_invariants: Dict[str, Any],
    frontend_invariants: Dict[str, Any],
) -> Dict[str, Any]:
    recommendations: List[Dict[str, Any]] = []

    # Backend – centraliser la sélection
    if backend_invariants.get("selection_pipeline"):
        recommendations.append(
            {
                "area": "backend",
                "priority": "HIGH",
                "issue": "Pipeline de sélection dispersé sur plusieurs fichiers.",
                "action": (
                    "Introduire un service ou module unique responsable de la sélection "
                    "et du chargement/sauvegarde de la sélection, utilisé à la fois par "
                    "l'API unifiée et les endpoints de migration/export."
                ),
            }
        )

    # Frontend – source unique de sélection
    recommendations.append(
        {
            "area": "frontend",
            "priority": "HIGH",
            "issue": "La sélection de capteurs peut être lue différemment par génération et migration.",
            "action": (
                "Créer un helper ou module partagé (par exemple un 'selectionSelector' "
                "dans shared/) que tous les flows (génération, migration, summary) "
                "utilisent pour récupérer la sélection active."
            ),
        }
    )

    # Frontend – exporter API
    download_flow = frontend_invariants.get("download_flow", {})
    if not download_flow.get("download_button"):
        recommendations.append(
            {
                "area": "frontend",
                "priority": "MEDIUM",
                "issue": "DownloadButton.js introuvable dans l'analyse.",
                "action": (
                    "Vérifier la présence et l'utilisation de shared/components/DownloadButton.js "
                    "pour standardiser tous les téléchargements (YAML, JSON, CSV, etc.)."
                ),
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "recommendations": recommendations,
    }


# ============================================================================
# PARSING ARGUMENTS + MAIN
# ============================================================================


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Outil d'audit/debug Home Suivi Élec (hse_debug_tool.py)"
    )

    parser.add_argument(
        "--backend",
        type=str,
        default="custom_components/home_suivi_elec",
        help="Chemin vers le backend Home Suivi Élec",
    )

    parser.add_argument(
        "--frontend",
        type=str,
        default="custom_components/home_suivi_elec/web_static",
        help="Chemin vers le frontend web_static",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="debug_reports",
        help="Répertoire de sortie pour les JSON",
    )

    parser.add_argument(
        "--ha-config",
        type=str,
        default=None,
        help="Chemin vers /config (Home Assistant). Ex: /config",
    )

    parser.add_argument(
        "--domain",
        type=str,
        default="homesuivielec",
        help="Domain HA à filtrer/scanner. Ex: homesuivielec ou home_suivi_elec",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Ne pas créer de sauvegarde tar.gz du backend",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    backend_path = Path(args.backend).resolve()
    frontend_path = Path(args.frontend).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not backend_path.exists():
        debug_print(f"[error] Backend introuvable: {backend_path}")
        return 1

    if not frontend_path.exists():
        debug_print(f"[error] Frontend introuvable: {frontend_path}")
        return 1

    config = DebugConfig(
        backend_path=backend_path,
        frontend_path=frontend_path,
        output_dir=output_dir,
        ha_config_path=Path(args.ha_config).resolve() if args.ha_config else None,
        ha_domain=args.domain,
        do_backup=not args.no_backup,
    )

    debug_print("=== Home Suivi Élec - hse_debug_tool ===")
    debug_print(f"Backend : {config.backend_path}")
    debug_print(f"Frontend: {config.frontend_path}")
    debug_print(f"Reports : {config.output_dir}")
    debug_print(f"Backup : {'oui' if config.do_backup else 'non'}")
    if config.ha_config_path:
        debug_print(f"HA config : {config.ha_config_path} (domain={config.ha_domain})")
    debug_print("========================================")

    # Sauvegarde
    if config.do_backup:
        make_backup(config)

    # Analyse backend
    backend_analysis = scan_backend(config)

    # Analyse frontend
    frontend_analysis = scan_frontend(config)

    # Construction des invariants
    backend_invariants = build_backend_invariants(backend_analysis)
    frontend_invariants = build_frontend_invariants(frontend_analysis)
    export_hypotheses = build_export_issue_hypotheses(
        backend_invariants, frontend_invariants
    )
    refactor_plan = build_refactor_plan(backend_invariants, frontend_invariants)

    # ===== CamelCase audit (code + HA storage)
    camelcase_report: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "legacy_keys": LEGACY_CAMELCASE_KEYS,
        "code_scan": scan_code_for_camelcase(
            config.backend_path,
            config.frontend_path,
            BACKEND_CRITICAL_FILES,
            FRONTEND_CRITICAL_FILES,
        ),
        "ha_storage_scan": None,
    }
    if config.ha_config_path:
        camelcase_report["ha_storage_scan"] = scan_ha_storage_for_camelcase(
            config.ha_config_path,
            config.ha_domain,
        )

    # Écriture des JSON
    safe_write_json(config.output_dir / "backend_invariants.json", backend_invariants)
    safe_write_json(config.output_dir / "frontend_invariants.json", frontend_invariants)
    safe_write_json(
        config.output_dir / "export_issue_hypotheses.json", export_hypotheses
    )
    safe_write_json(config.output_dir / "refactor_plan.json", refactor_plan)
    safe_write_json(config.output_dir / "camelcase_audit.json", camelcase_report)

    debug_print("")
    debug_print("[done] Rapports générés dans :")
    debug_print(f" - {config.output_dir / 'backend_invariants.json'}")
    debug_print(f" - {config.output_dir / 'frontend_invariants.json'}")
    debug_print(f" - {config.output_dir / 'export_issue_hypotheses.json'}")
    debug_print(f" - {config.output_dir / 'refactor_plan.json'}")
    debug_print(f" - {config.output_dir / 'camelcase_audit.json'}")
    debug_print("")
    debug_print(
        "Ces fichiers peuvent être fournis à l'IA pour du debug/refactor ciblé,"
    )
    debug_print("sans avoir à rescanner tout le projet à chaque fois.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
