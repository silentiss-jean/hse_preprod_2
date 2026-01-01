#!/usr/bin/env python3
"""
Script v2 : Audit et correction automatique pour web.json_response() avec datetime
- Scan tout le composant
- Utilise un wrapper centralisé
- Gère tous les patterns de web.json_response()

Usage:
  python3 fix_json_datetime_v2.py --audit      # Audit seulement
  python3 fix_json_datetime_v2.py --dry-run    # Simulation
  python3 fix_json_datetime_v2.py --fix        # Correction réelle
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict

# Configuration
COMPONENT_DIR = "/config/custom_components/home_suivi_elec"
BACKUP_SUFFIX = ".bak"
EXCLUDED_FILES = ["fix_json_datetime.py", "fix_json_datetime_v2.py", "json_response.py"]

# Import à ajouter
IMPORT_JSON_RESPONSE = "from .utils.json_response import json_response"


class JSONDatetimeFixerV2:
    """Auditeur et correcteur v2 pour web.json_response()"""
    
    def __init__(self, component_dir: str, dry_run: bool = False):
        self.component_dir = Path(component_dir)
        self.dry_run = dry_run
        
    def audit(self) -> Dict[str, List[Dict]]:
        """Audit tous les fichiers Python du composant"""
        results = {}
        
        print(f"🔍 Audit du composant: {self.component_dir}\n")
        
        for py_file in self.component_dir.rglob("*.py"):
            # Exclusions
            if py_file.name in EXCLUDED_FILES or "__pycache__" in str(py_file):
                continue
                
            issues = self._audit_file(py_file)
            if issues:
                results[str(py_file)] = issues
                
        return results
    
    def _audit_file(self, filepath: Path) -> List[Dict]:
        """Audit un fichier spécifique"""
        issues = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Cherche web.json_response (ligne par ligne pour compter)
        for i, line in enumerate(lines, 1):
            if 'web.json_response' in line and not line.strip().startswith('#'):
                issues.append({
                    'line': i,
                    'content': line.strip()[:80],
                    'type': 'web.json_response'
                })
        
        # Vérifie si l'import existe déjà
        has_import = 'from .utils.json_response import json_response' in content or \
                     'from ..utils.json_response import json_response' in content
        
        if issues:
            rel_path = filepath.relative_to(self.component_dir)
            print(f"\n📄 {rel_path}")
            print(f"  ❌ {len(issues)} occurrence(s) de web.json_response")
            print(f"  📦 Import json_response: {'✅' if has_import else '❌ Manquant'}")
            
            for issue in issues[:5]:
                print(f"    L{issue['line']}: {issue['content']}")
                
            if len(issues) > 5:
                print(f"    ... et {len(issues) - 5} autre(s)")
        
        return issues
    
    def fix_all(self, audit_results: Dict[str, List[Dict]]):
        """Applique les corrections sur tous les fichiers"""
        
        if not audit_results:
            print("\n✅ Aucun problème détecté!")
            return
        
        print(f"\n{'🧪 DRY-RUN: Simulation' if self.dry_run else '🔧 CORRECTION EN COURS'}")
        print("=" * 60)
        
        for filepath, issues in audit_results.items():
            self._fix_file(Path(filepath), issues)
        
        if self.dry_run:
            print("\n✅ Dry-run terminé (aucune modification réelle)")
        else:
            print("\n✅ Corrections appliquées!")
            print("⚠️  Backup créé pour chaque fichier (.bak)")
            print("🔄 Redémarre Home Assistant: ha core restart")
    
    def _fix_file(self, filepath: Path, issues: List[Dict]):
        """Corrige un fichier spécifique"""
        rel_path = filepath.relative_to(self.component_dir)
        print(f"\n📝 {rel_path}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 1. Ajoute l'import si manquant
        content = self._ensure_import(content, filepath)
        
        # 2. Remplace web.json_response par json_response
        content = self._replace_json_responses(content)
        
        if content != original_content:
            if not self.dry_run:
                # Backup
                backup_path = filepath.with_suffix(filepath.suffix + BACKUP_SUFFIX)
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                print(f"  💾 Backup: {backup_path.name}")
                
                # Écrit le fichier corrigé
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✅ {len(issues)} remplacement(s) effectué(s)")
            else:
                print(f"  🧪 [DRY-RUN] {len(issues)} remplacement(s) seraient appliqués")
        else:
            print(f"  ℹ️  Aucune modification nécessaire")
    
    def _ensure_import(self, content: str, filepath: Path) -> str:
        """Ajoute l'import json_response si manquant"""
        
        # Détermine le niveau d'import relatif
        depth = len(filepath.relative_to(self.component_dir).parts) - 1
        if depth == 0:
            import_line = "from .utils.json_response import json_response"
        else:
            import_line = f"from {'.' * (depth + 1)}utils.json_response import json_response"
        
        # Vérifie si déjà présent
        if import_line in content or 'from .utils.json_response import json_response' in content:
            return content
        
        lines = content.split('\n')
        
        # Trouve la position après les imports existants
        import_end = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_end = i + 1
        
        # Insère l'import
        lines.insert(import_end, import_line)
        
        return '\n'.join(lines)
    
    def _replace_json_responses(self, content: str) -> str:
        """Remplace web.json_response par json_response (simple)"""
        # Remplacement simple et robuste
        return content.replace('web.json_response', 'json_response')


def main():
    parser = argparse.ArgumentParser(
        description="Audit et correction v2 des web.json_response() pour datetime"
    )
    parser.add_argument('--audit', action='store_true', help="Audit seulement")
    parser.add_argument('--dry-run', action='store_true', help="Simulation sans modification")
    parser.add_argument('--fix', action='store_true', help="Applique les corrections")
    parser.add_argument('--dir', default=COMPONENT_DIR, help="Chemin du composant")
    
    args = parser.parse_args()
    
    if not any([args.audit, args.dry_run, args.fix]):
        parser.print_help()
        sys.exit(1)
    
    fixer = JSONDatetimeFixerV2(args.dir, dry_run=args.dry_run)
    
    # Audit
    print("=" * 60)
    print("🔍 AUDIT v2 - Détection globale web.json_response()")
    print("=" * 60)
    
    audit_results = fixer.audit()
    
    if not audit_results:
        print("\n✅ Aucun problème détecté!")
        return
    
    # Résumé
    total_issues = sum(len(issues) for issues in audit_results.values())
    print(f"\n📊 RÉSUMÉ:")
    print(f"  • Fichiers concernés: {len(audit_results)}")
    print(f"  • Total d'occurrences: {total_issues}")
    
    # Correction si demandée
    if args.fix or args.dry_run:
        fixer.fix_all(audit_results)


if __name__ == "__main__":
    main()
