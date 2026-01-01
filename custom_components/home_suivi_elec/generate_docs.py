#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Générateur de Documentation Automatique

Home Suivi Élec - Phase 3

Génère documentation backend.md, frontend.md et architecture.md
Format LLM-ready + Human-readable

Usage:

python generate_docs.py
python generate_docs.py --backend custom_components/home_suivi_elec
python generate_docs.py --frontend www/home_suivi_elec/web_static
python generate_docs.py --output-dir docs --no-llm
"""

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================
# CONFIGURATION
# ============================================================

@dataclass
class Config:
    """Configuration du générateur"""

    backend_path: Path
    frontend_path: Path
    output_dir: Path

    include_diagrams: bool = True
    llm_format: bool = True
    human_readable: bool = True

    # Patterns exclus de l'analyse ET de l'arborescence
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
            "*.backup2",
            # artefacts / caches / backups
            "*.tar.gz",
            "*backup_*",
            "*backups*",
            "*.json.migrated",
        ]
    )

# ============================================================
# MAPPINGS METIERS (INDEX PRINCIPAL)
# ============================================================

# Section, libellé métier, chemin relatif (par rapport au backend_path)
BACKEND_MAIN_MODULES = [
    ("3.1", "Orchestration backend", "__init__.py"),
    ("3.2", "Détection capteurs", "detect_local.py"),
    ("3.3", "Sélection/mapping", "manage_selection.py"),
    ("3.4", "Scoring qualité", "sensor_quality_scorer.py"),
    ("3.5", "Création sensors HSE", "sensor.py"),
    ("3.6", "Energy tracking cycles", "energy_tracking.py"),
    ("3.7", "Génération Lovelace/YAML", "generator.py"),
    ("3.8", "Validation données", "helpers/validation.py"),
    ("3.9", "Analytics énergétique", "energy_analytics.py"),
    ("3.10", "Export/backup énergie", "energy_export.py"),
    ("3.11", "Panel UI (sidebar)", "panel_selection.py"),
    ("3.12", "Correction noms sensors", "sensor_name_fixer.py"),
    ("3.13", "Synchronisation sensors", "sensor_sync_manager.py"),
    ("3.14", "Monitoring puissance", "power_monitoring.py"),
    ("3.15", "Debug JSON backend", "debug_json_sets.py"),
    ("3.16", "Constantes globales", "const.py"),
    ("3.17", "Config UI initiale", "config_flow.py"),
    ("3.18", "Options UI avancées", "options_flow.py"),
    ("3.19", "Proxy API frontend", "proxy_api.py"),
    ("3.20", "Registry noms universel", "entity_name_registry.py"),
    ("3.21", "API Unifiée GET", "api/unified_api.py"),
    ("3.22", "API Configuration POST", "api/unified_api_extensions.py"),
    ("3.23", "Endpoints REST sélection", "manage_selection_views.py"),
    ("3.24", "API Registry noms (vue)", "manage_selection_views_entity_registry.py"),
    ("3.25", "Diagnostic groupes (vue)", "manage_selection_views_diagnostic_groups.py"),
]

# ============================================================
# ANALYSEURS
# ============================================================

@dataclass
class FileAnalysis:
    """Résultat d'analyse d'un fichier"""

    path: Path
    relative_path: str
    size: int
    lines: int
    language: str

    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)

    docstring: Optional[str] = None
    is_async: bool = False
    patterns: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


class PythonAnalyzer:
    """Analyseur de fichiers Python"""

    @staticmethod
    def analyze(file_path: Path) -> FileAnalysis:
        """Analyse un fichier Python"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        analysis = FileAnalysis(
            path=file_path,
            relative_path=str(file_path),
            size=len(content),
            lines=len(lines),
            language="python",
        )

        try:
            tree = ast.parse(content)

            # Docstring du module
            if (
                tree.body
                and isinstance(tree.body, ast.Expr)
                and isinstance(tree.body.value, ast.Constant)
                and isinstance(tree.body.value.value, str)
            ):
                analysis.docstring = tree.body.value.value

            # Parcours AST
            for node in ast.walk(tree):
                # Fonctions
                if isinstance(node, ast.FunctionDef):
                    analysis.functions.append(node.name)
                    if any(
                        isinstance(d, ast.Name) and d.id == "async"
                        for d in node.decorator_list
                    ):
                        analysis.is_async = True

                # Classes
                elif isinstance(node, ast.ClassDef):
                    analysis.classes.append(node.name)

                # Imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis.imports.append(node.module)

            # Détection patterns heuristiques
            if "async def" in content:
                analysis.is_async = True
                analysis.patterns.append("Async/Await")

            if "HomeAssistantView" in content or "async_register" in content:
                analysis.patterns.append("REST API View")

            if "Store(" in content or "StorageManager" in content:
                analysis.patterns.append("Storage API")

            if "@callback" in content or "async_track_" in content:
                analysis.patterns.append("Event Listener")

            if "SensorEntity" in content or "CoordinatorEntity" in content:
                analysis.patterns.append("Home Assistant Entity")

            # Issues basiques
            if "TODO" in content or "FIXME" in content:
                analysis.issues.append("Contains TODO/FIXME")

        except SyntaxError as e:
            analysis.issues.append(f"Syntax Error: {e}")

        return analysis


class JavaScriptAnalyzer:
    """Analyseur de fichiers JavaScript"""

    @staticmethod
    def analyze(file_path: Path) -> FileAnalysis:
        """Analyse un fichier JavaScript"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        analysis = FileAnalysis(
            path=file_path,
            relative_path=str(file_path),
            size=len(content),
            lines=len(lines),
            language="javascript",
        )

        # Fonctions
        func_pattern = r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("
        analysis.functions = re.findall(func_pattern, content)

        # Classes
        class_pattern = r"(?:export\s+)?class\s+(\w+)"
        analysis.classes = re.findall(class_pattern, content)

        # Imports ES6
        import_pattern = r'import\s+.*?\s+from\s+["\'](.+?)["\']'
        analysis.imports = re.findall(import_pattern, content)

        # Exports
        export_pattern = (
            r"export\s+(?:default\s+)?(?:async\s+)?"
            r"(?:function|class|const|let|var)\s+(\w+)"
        )
        analysis.exports = re.findall(export_pattern, content)

        # Patterns
        if "async function" in content or "async (" in content:
            analysis.is_async = True
            analysis.patterns.append("Async/Await")

        if "fetch(" in content:
            analysis.patterns.append("Fetch API")

        if "addEventListener" in content:
            analysis.patterns.append("Event Listeners")

        if "createElement" in content or "appendChild" in content:
            analysis.patterns.append("DOM Manipulation")

        return analysis


class ProjectAnalyzer:
    """Analyseur de projet complet"""

    def __init__(self, config: Config):
        self.config = config
        self.backend_files: List[FileAnalysis] = []
        self.frontend_files: List[FileAnalysis] = []

    def should_exclude(self, path: Path) -> bool:
        """Vérifie si un fichier doit être exclu"""
        for pattern in self.config.exclude_patterns:
            if path.match(pattern):
                return True
        return False

    def analyze_backend(self) -> None:
        """Analyse le backend Python"""
        print("🔍 Analyse backend Python...")
        for py_file in self.config.backend_path.rglob("*.py"):
            if self.should_exclude(py_file):
                continue
            try:
                analysis = PythonAnalyzer.analyze(py_file)
                analysis.relative_path = str(
                    py_file.relative_to(self.config.backend_path)
                )
                self.backend_files.append(analysis)
                print(f" ✓ {analysis.relative_path}")
            except Exception as e:  # noqa: BLE001
                print(f" ✗ {py_file.name}: {e}")

    def analyze_frontend(self) -> None:
        """Analyse le frontend JavaScript"""
        print("🔍 Analyse frontend JavaScript...")
        for js_file in self.config.frontend_path.rglob("*.js"):
            if self.should_exclude(js_file):
                continue
            try:
                analysis = JavaScriptAnalyzer.analyze(js_file)
                analysis.relative_path = str(
                    js_file.relative_to(self.config.frontend_path)
                )
                self.frontend_files.append(analysis)
                print(f" ✓ {analysis.relative_path}")
            except Exception as e:  # noqa: BLE001
                print(f" ✗ {js_file.name}: {e}")

# ============================================================
# GÉNÉRATEURS MARKDOWN
# ============================================================

class MarkdownGenerator:
    """Générateur de documentation Markdown"""

    def __init__(self, config: Config, analyzer: ProjectAnalyzer):
        self.config = config
        self.analyzer = analyzer

    # ------------------ Entrée principale ------------------

    def generate_all(self) -> None:
        """Génère toutes les documentations"""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        print("\n📝 Génération documentation...")
        self.generate_backend_doc()
        self.generate_frontend_doc()
        self.generate_architecture_doc()
        self.generate_index()
        print(f"\n✅ Documentation générée dans {self.config.output_dir}/")

    # ------------------ Backend ------------------

    def generate_backend_doc(self) -> None:
        """Génère backend.md"""
        output_file = self.config.output_dir / "backend.md"
        with open(output_file, "w", encoding="utf-8") as f:
            self._write_backend_header(f)
            self._write_backend_toc(f)
            self._write_backend_index_metier(f)
            self._write_backend_overview(f)
            self._write_backend_main_modules(f)
            self._write_backend_files(f)
            self._write_backend_api(f)
            self._write_backend_services(f)
        print(f" ✓ {output_file.name}")

    def _write_backend_header(self, f) -> None:
        """En-tête backend.md"""
        f.write("# 🐍 Documentation Backend — Home Suivi Élec\n\n")
        f.write(
            f"**Généré automatiquement le "
            f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}**\n\n"
        )
        if self.config.llm_format:
            f.write("\n\n")

        f.write("\n\n")
        f.write("## 🎯 Vue d'Ensemble\n\n")
        f.write("Intégration Home Assistant pour suivi énergétique avancé.\n\n")
        f.write("**Philosophie** :\n")
        f.write("- ✅ Détection automatique capteurs power/energy\n")
        f.write("- ✅ Scoring qualité pour sélection optimale\n")
        f.write("- ✅ Tracking cycles : hourly, daily, weekly, monthly, yearly\n")
        f.write("- ✅ API REST unifiée\n")
        f.write("- ✅ Storage persistant via Home Assistant Storage API\n\n")

    def _write_backend_toc(self, f) -> None:
        """Table des matières backend"""
        f.write("## 📋 Table des Matières\n\n")
        f.write("1. [Index recherche rapide](#🗂️-index-recherche-rapide)\n")
        f.write("2. [Arborescence](#🗂️-arborescence)\n")
        f.write("3. [Modules principaux](#3-modules-principaux)\n")
        f.write("4. [Modules détaillés](#📦-modules-détaillés)\n")
        f.write("5. [API REST](#🌐-api-rest)\n")
        f.write("6. [Services Home Assistant](#🛠️-services-home-assistant)\n\n")
        f.write("---\n\n")

    def _write_backend_index_metier(self, f) -> None:
        """Tableau 'Index recherche rapide' des modules principaux."""
        f.write("## 🗂️ Index recherche rapide\n\n")
        f.write("| Besoin Métier / Fonction | Section | Fichier (chemin) |\n")
        f.write("|-------------------------|---------|------------------|\n")

        backend_root = self.config.backend_path
        for section, label, rel_path in BACKEND_MAIN_MODULES:
            try:
                display_path = str(
                    (backend_root / rel_path).relative_to(backend_root.parent)
                )
            except ValueError:
                display_path = rel_path
            f.write(f"| {label} | {section} | {display_path} |\n")

        f.write("\n\n")

    def _write_backend_overview(self, f) -> None:
        """Vue d'ensemble backend (arborescence)"""
        f.write("## 🗂️ Arborescence\n\n")
        f.write("```\n")
        root = self.config.backend_path

        for path in sorted(self.config.backend_path.rglob("*")):
            if self.analyzer.should_exclude(path):
                continue
            rel = path.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            indent = " " * (len(rel.parts) - 1)
            name = rel.name + ("/" if path.is_dir() else "")
            f.write(f"{indent}{name}\n")

        f.write("```\n")

    def _write_backend_main_modules(self, f) -> None:
        """Section 3.x 'Modules principaux' basée sur l'analyse automatique."""
        f.write("## 3. Modules principaux\n\n")
        files_by_path = {fa.relative_path: fa for fa in self.analyzer.backend_files}

        for section, label, rel_path in BACKEND_MAIN_MODULES:
            fa = files_by_path.get(rel_path)
            f.write(f"#### {section} {rel_path} — {label}\n\n")

            if fa is None:
                f.write("_Module non trouvé dans l'analyse backend._\n\n")
                continue

            f.write(f"**Fichier Python :** {fa.relative_path}\n\n")

            if fa.classes:
                f.write(
                    "**Classe(s) principale(s) :** "
                    + ", ".join(sorted(set(fa.classes)))
                    + "\n\n"
                )
            else:
                f.write("**Classe(s) principale(s) :** N/A\n\n")

            if fa.functions:
                f.write(
                    "**Fonctions détectées :** "
                    + ", ".join(sorted(set(fa.functions)))
                    + "\n\n"
                )
            else:
                f.write("**Fonctions détectées :** N/A\n\n")

            if fa.imports:
                f.write(
                    "**Imports clés :** "
                    + ", ".join(sorted(set(fa.imports)))
                    + "\n\n"
                )

            if fa.patterns:
                f.write(
                    "**Patterns détectés :** "
                    + ", ".join(fa.patterns)
                    + "\n\n"
                )

            if fa.docstring:
                f.write("**Docstring module (résumé auto) :**\n\n")
                f.write("```\n")
                f.write(fa.docstring.strip() + "\n")
                f.write("```\n")

    def _write_backend_files(self, f) -> None:
        """Détail des fichiers backend"""
        f.write("## 📦 Modules Détaillés\n\n")

        for fa in sorted(self.analyzer.backend_files, key=lambda x: x.relative_path):
            f.write(f"### `{fa.relative_path}`\n\n")
            f.write(f"- **Lignes** : {fa.lines}\n")
            f.write(f"- **Taille** : {fa.size} bytes\n")
            f.write(
                "- **Fonctions** : "
                + (", ".join(fa.functions) if fa.functions else "Aucune")
                + "\n"
            )
            f.write(
                "- **Classes** : "
                + (", ".join(fa.classes) if fa.classes else "Aucune")
                + "\n"
            )

            if fa.imports:
                f.write(
                    "- **Imports** : "
                    + ", ".join(sorted(set(fa.imports)))
                    + "\n"
                )

            if fa.is_async:
                f.write("- **Async** : Oui\n")

            if fa.patterns:
                f.write(
                    "- **Patterns** : "
                    + ", ".join(fa.patterns)
                    + "\n"
                )

            if fa.issues:
                f.write(
                    "- **Issues** : "
                    + ", ".join(fa.issues)
                    + "\n"
                )

            f.write("\n")

            if fa.docstring:
                f.write("#### 📝 Docstring module\n\n")
                f.write("```\n")
                f.write(fa.docstring.strip() + "\n")
                f.write("```\n")

            if self.config.llm_format:
                f.write("\n")
                f.write(f"Module : {fa.relative_path}\n")
                f.write(
                    "Rôle probable : backend Python ("
                    + ("async" if fa.is_async else "sync")
                    + ")\n"
                )
                if fa.patterns:
                    f.write("Patterns : " + ", ".join(fa.patterns) + "\n")
                f.write("\n\n")

    def _write_backend_api(self, f) -> None:
        """Section API REST backend (vue synthétique)"""
        f.write("## 🌐 API REST\n\n")
        f.write(
            "Cette section ne recense pas tous les endpoints, "
            "mais donne une vision générale.\n\n"
        )

        api_files = [
            fa
            for fa in self.analyzer.backend_files
            if "api/" in fa.relative_path or fa.relative_path.endswith("_views.py")
        ]

        if not api_files:
            f.write("_Aucun module d'API détecté automatiquement._\n\n")
            return

        for fa in sorted(api_files, key=lambda x: x.relative_path):
            f.write(f"### `{fa.relative_path}`\n\n")
            f.write(
                "- **Fonctions** : "
                + (", ".join(fa.functions) if fa.functions else "Aucune")
                + "\n"
            )

            if fa.imports:
                f.write(
                    "- **Imports** : "
                    + ", ".join(sorted(set(fa.imports)))
                    + "\n"
                )

            if fa.docstring:
                f.write("\n#### 📝 Docstring\n\n")
                f.write("```\n")
                f.write(fa.docstring.strip() + "\n")
                f.write("```\n")

    def _write_backend_services(self, f) -> None:
        """Section services Home Assistant (vue heuristique)"""
        f.write("## 🛠️ Services Home Assistant\n\n")
        f.write(
            "Cette section liste les fichiers susceptibles de déclarer des services.\n\n"
        )

        service_like = [
            fa
            for fa in self.analyzer.backend_files
            if "services" in fa.relative_path
            or "services.yaml" in fa.relative_path
            or "async_register" in (fa.docstring or "")
        ]

        if not service_like:
            f.write("_Aucun module de services détecté automatiquement._\n\n")
            return

        for fa in sorted(service_like, key=lambda x: x.relative_path):
            f.write(f"### `{fa.relative_path}`\n\n")
            if fa.docstring:
                f.write("```\n")
                f.write(fa.docstring.strip() + "\n")
                f.write("```\n")

    # ------------------ Frontend ------------------

    def generate_frontend_doc(self) -> None:
        """Génère frontend.md"""
        output_file = self.config.output_dir / "frontend.md"
        with open(output_file, "w", encoding="utf-8") as f:
            self._write_frontend_header(f)
            self._write_frontend_toc(f)
            self._write_frontend_overview(f)
            self._write_frontend_structure(f)
            self._write_frontend_modules(f)
            self._write_frontend_shared(f)
        print(f" ✓ {output_file.name}")

    def _write_frontend_header(self, f) -> None:
        """En-tête frontend.md"""
        f.write("# 🎨 Documentation Frontend — Home Suivi Élec\n\n")
        f.write(
            f"**Généré automatiquement le "
            f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}**\n\n"
        )
        if self.config.llm_format:
            f.write("\n\n")

    def _write_frontend_toc(self, f) -> None:
        """Table des matières frontend"""
        f.write("## 📋 Table des Matières\n\n")
        f.write("1. [Vue d'ensemble](#vue-densemble)\n")
        f.write("2. [Structure des dossiers](#structure-des-dossiers)\n")
        f.write("3. [Modules par fonctionnalité](#modules-par-fonctionnalité)\n")
        f.write("4. [Composants partagés](#composants-partagés)\n\n")
        f.write("---\n\n")

    def _write_frontend_overview(self, f) -> None:
        """Vue d'ensemble frontend"""
        f.write("## Vue d'ensemble\n\n")
        f.write("Frontend modulaire basé sur `web_static/` avec :\n")
        f.write("- `core/` : bootstrap, auth, router\n")
        f.write(
            "- `features/` : modules fonctionnels "
            "(summary, configuration, diagnostics, detection, generation, customisation)\n"
        )
        f.write("- `shared/` : composants, utilitaires, vues communes\n\n")

    def _write_frontend_structure(self, f) -> None:
        """Arborescence web_static/"""
        f.write("## Structure des dossiers\n\n")
        f.write("```\n")
        root = self.config.frontend_path

        for path in sorted(root.rglob("*")):
            if self.analyzer.should_exclude(path):
                continue
            rel = path.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            indent = " " * (len(rel.parts) - 1)
            name = rel.name + ("/" if path.is_dir() else "")
            f.write(f"{indent}{name}\n")

        f.write("```\n")

    def _write_frontend_modules(self, f) -> None:
        """Modules par feature (features/...)"""
        f.write("## Modules par fonctionnalité\n\n")

        grouped: Dict[str, List[FileAnalysis]] = defaultdict(list)
        for fa in self.analyzer.frontend_files:
            parts = fa.relative_path.split("/")
            if len(parts) >= 2 and parts == "features":
                key = f"features/{parts[1]}"
                grouped[key].append(fa)

        for feature, files in sorted(grouped.items()):
            f.write(f"### `{feature}/`\n\n")
            total_lines = sum(ff.lines for ff in files)
            f.write(f"- **Fichiers** : {len(files)}\n")
            f.write(f"- **Lignes totales** : {total_lines}\n\n")

            for fa in sorted(files, key=lambda x: x.relative_path):
                f.write(f"#### `{fa.relative_path}`\n\n")
                f.write(f"- **Lignes** : {fa.lines}\n")
                f.write(
                    "- **Fonctions** : "
                    + (", ".join(fa.functions) if fa.functions else "Aucune")
                    + "\n"
                )
                f.write(
                    "- **Classes** : "
                    + (", ".join(fa.classes) if fa.classes else "Aucune")
                    + "\n"
                )

                if fa.imports:
                    f.write(
                        "- **Imports** : "
                        + ", ".join(sorted(set(fa.imports)))
                        + "\n"
                    )

                if fa.patterns:
                    f.write(
                        "- **Patterns** : "
                        + ", ".join(fa.patterns)
                        + "\n"
                    )

                if fa.issues:
                    f.write(
                        "- **Issues** : "
                        + ", ".join(fa.issues)
                        + "\n"
                    )

                f.write("\n")

                if self.config.llm_format:
                    f.write("\n")
                    f.write(f"Module frontend : {fa.relative_path}\n")
                    if "view" in fa.relative_path:
                        f.write("Rôle : vue / rendu DOM\n")
                    elif "state" in fa.relative_path:
                        f.write("Rôle : état local frontend\n")
                    elif "api" in fa.relative_path:
                        f.write("Rôle : appels API REST backend\n")
                    f.write("\n\n")

    def _write_frontend_shared(self, f) -> None:
        """Section shared (composants & utils)"""
        f.write("## Composants partagés\n\n")

        shared_files = [
            fa
            for fa in self.analyzer.frontend_files
            if fa.relative_path.startswith("shared/")
        ]

        if not shared_files:
            f.write("_Aucun fichier dans `shared/` détecté._\n\n")
            return

        for fa in sorted(shared_files, key=lambda x: x.relative_path):
            f.write(f"### `{fa.relative_path}`\n\n")
            f.write(f"- **Lignes** : {fa.lines}\n")
            f.write(
                "- **Fonctions** : "
                + (", ".join(fa.functions) if fa.functions else "Aucune")
                + "\n"
            )
            f.write(
                "- **Classes** : "
                + (", ".join(fa.classes) if fa.classes else "Aucune")
                + "\n"
            )

            if fa.imports:
                f.write(
                    "- **Imports** : "
                    + ", ".join(sorted(set(fa.imports)))
                    + "\n"
                )

            if fa.patterns:
                f.write(
                    "- **Patterns** : "
                    + ", ".join(fa.patterns)
                    + "\n"
                )

            if fa.issues:
                f.write(
                    "- **Issues** : "
                    + ", ".join(fa.issues)
                    + "\n"
                )

            f.write("\n")

    # ------------------ Architecture ------------------

    def generate_architecture_doc(self) -> None:
        """Génère architecture.md"""
        output_file = self.config.output_dir / "architecture.md"
        with open(output_file, "w", encoding="utf-8") as f:
            self._write_architecture_header(f)
            self._write_architecture_overview(f)
            self._write_architecture_diagrams(f)
            self._write_architecture_flows(f)
        print(f" ✓ {output_file.name}")

    def _write_architecture_header(self, f) -> None:
        f.write("# 🧩 Architecture Globale — Home Suivi Élec\n\n")
        f.write(
            f"**Généré automatiquement le "
            f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}**\n\n"
        )
        if self.config.llm_format:
            f.write("\n\n")

    def _write_architecture_overview(self, f) -> None:
        f.write("## Vue d'ensemble\n\n")
        f.write("- Backend Python (intégration Home Assistant)\n")
        f.write("- Frontend statique servit via `web_static/`\n")
        f.write("- Communication via API REST (`/api/home_suivi_elec/...`)\n")
        f.write("- Stockage via Home Assistant Storage API + JSON legacy\n\n")

    def _write_architecture_diagrams(self, f) -> None:
        """Diagrammes Mermaid (haut niveau)"""
        if not self.config.include_diagrams:
            return

        f.write("## Diagrammes (Mermaid)\n\n")
        f.write("### Flux global Backend ↔ Frontend\n\n")
        f.write("```\n")
        f.write("graph LR\n")
        f.write("  subgraph Backend\n")
        f.write("    B1[__init__.py]\n")
        f.write("    B2[StorageManager]\n")
        f.write("    B3[Energy Tracking]\n")
        f.write("    B4[REST API Views]\n")
        f.write("  end\n")
        f.write("  subgraph Frontend\n")
        f.write("    F1[index.html]\n")
        f.write("    F2[core/app.js]\n")
        f.write("    F3[features/*]\n")
        f.write("    F4[shared/*]\n")
        f.write("  end\n")
        f.write("  HA[Home Assistant Core]\n")
        f.write("  HA --> B1\n")
        f.write("  B1 --> B2\n")
        f.write("  B2 --> B3\n")
        f.write("  B1 --> B4\n")
        f.write("  F1 --> F2 --> F3\n")
        f.write("  F3 --> F4\n")
        f.write("  F3 -->|fetch()| B4\n")
        f.write("```\n")

    def _write_architecture_flows(self, f) -> None:
        """Section flux détaillés (texte)"""
        f.write("## Flux principaux\n\n")

        f.write("### Démarrage integration\n")
        f.write("1. Home Assistant appelle `async_setup_entry` dans `__init__.py`.\n")
        f.write("2. Initialisation du `StorageManager`.\n")
        f.write("3. Lancement de la détection, sélection, tracking énergie.\n")
        f.write("4. Exposition des endpoints API REST.\n\n")

        f.write("### Chargement UI Frontend\n")
        f.write("1. L'utilisateur ouvre le panel `⚡ Suivi Élec`.\n")
        f.write("2. `index.html` charge `core/app.js` et `core/router.js`.\n")
        f.write(
            "3. Le routeur charge le module `features/*.js` correspondant à l'onglet.\n"
        )
        f.write("4. Chaque module :\n")
        f.write("   - appelle ses APIs (`*.api.js`)\n")
        f.write("   - gère l'état local (`*.state.js`)\n")
        f.write("   - rend l'UI (`*.view.js` + `shared/components/*`)\n\n")

    # ------------------ Index global ------------------

    def generate_index(self) -> None:
        """Génère index.md"""
        output_file = self.config.output_dir / "index.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# 📚 Documentation Home Suivi Élec\n\n")
            f.write(
                f"**Généré automatiquement le "
                f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}**\n\n"
            )

            f.write("## 🎯 Navigation Rapide\n\n")
            f.write("| Document | Description |\n")
            f.write("|----------|-------------|\n")
            f.write(
                "| [Backend](backend.md) | "
                f"Documentation backend Python "
                f"({len(self.analyzer.backend_files)} fichiers) |\n"
            )
            f.write(
                "| [Frontend](frontend.md) | "
                f"Documentation frontend JavaScript "
                f"({len(self.analyzer.frontend_files)} fichiers) |\n"
            )
            f.write(
                "| [Architecture](architecture.md) | "
                "Vue d'ensemble + diagrammes |\n\n"
            )

            total_lines_backend = sum(fa.lines for fa in self.analyzer.backend_files)
            total_lines_frontend = sum(
                fa.lines for fa in self.analyzer.frontend_files
            )

            f.write("## 📊 Statistiques Projet\n\n")
            f.write("### Backend\n")
            f.write(f"- **Fichiers Python** : {len(self.analyzer.backend_files)}\n")
            f.write(f"- **Lignes totales** : {total_lines_backend}\n\n")

            f.write("### Frontend\n")
            f.write(f"- **Fichiers JavaScript** : {len(self.analyzer.frontend_files)}\n")
            f.write(f"- **Lignes totales** : {total_lines_frontend}\n\n")


# ============================================================
# CLI / MAIN
# ============================================================

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Générateur automatique de documentation Home Suivi Élec"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="custom_components/home_suivi_elec",
        help="Chemin vers le backend (intégration Home Assistant)",
    )
    parser.add_argument(
        "--frontend",
        type=str,
        default="custom_components/home_suivi_elec/web_static",
        help="Chemin vers le frontend (web_static)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="docs",
        help="Répertoire de sortie pour la documentation",
    )
    parser.add_argument(
        "--no-diagrams",
        action="store_true",
        help="Désactiver la génération des diagrammes Mermaid",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Désactiver le format LLM (blocs résumés supplémentaires)",
    )
    parser.add_argument(
        "--human-only",
        action="store_true",
        help="Forcer un format purement humain (désactive options LLM)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    backend_path = Path(args.backend).resolve()
    frontend_path = Path(args.frontend).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not backend_path.exists():
        print(f"❌ Backend introuvable : {backend_path}")
        return 1

    if not frontend_path.exists():
        print(f"❌ Frontend introuvable : {frontend_path}")
        return 1

    include_diagrams = not args.no_diagrams
    llm_format = not args.no_llm and not args.human_only
    human_readable = True  # on garde toujours le format humain

    config = Config(
        backend_path=backend_path,
        frontend_path=frontend_path,
        output_dir=output_dir,
        include_diagrams=include_diagrams,
        llm_format=llm_format,
        human_readable=human_readable,
    )

    print(f"Backend :  {config.backend_path}")
    print(f"Frontend : {config.frontend_path}")
    print(f"Output   : {config.output_dir}")
    print(f"Diagrams : {'oui' if config.include_diagrams else 'non'}")
    print(f"LLM fmt  : {'oui' if config.llm_format else 'non'}")

    analyzer = ProjectAnalyzer(config)
    analyzer.analyze_backend()
    analyzer.analyze_frontend()

    generator = MarkdownGenerator(config, analyzer)
    generator.generate_all()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
