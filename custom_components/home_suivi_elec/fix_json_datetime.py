#!/usr/bin/env python3
"""
Script d'audit et correction automatique pour gérer datetime dans les réponses JSON
Usage:
  python fix_json_datetime.py --audit          # Audit seulement
  python fix_json_datetime.py --dry-run        # Simulation sans modification
  python fix_json_datetime.py --fix            # Correction réelle
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# Configuration
API_DIR = "/config/custom_components/home_suivi_elec/api"
BACKUP_SUFFIX = ".bak"

# Code à injecter
JSON_DEFAULT_FUNCTION = '''
# Fonction helper globale pour serializer JSON
def _json_default(obj):
    """Serializer JSON custom pour datetime/date"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")
'''

IMPORT_DATETIME = "from datetime import datetime, date\n"
IMPORT_JSON = "import json\n"


class JSONDatetimeFixer:
    """Auditeur et correcteur automatique pour web.json_response()"""
    
    def __init__(self, api_dir: str, dry_run: bool = False):
        self.api_dir = Path(api_dir)
        self.dry_run = dry_run
        self.issues_found = []
        
    def audit(self) -> Dict[str, List[Dict]]:
        """Audit tous les fichiers Python dans le dossier API"""
        results = {}
        
        print(f"🔍 Audit du dossier: {self.api_dir}\n")
        
        for py_file in self.api_dir.glob("*.py"):
            if py_file.name.startswith("__"):
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
        
        # Cherche web.json_response()
        json_response_pattern = r'web\.json_response\s*\('
        for i, line in enumerate(lines, 1):
            if re.search(json_response_pattern, line):
                issues.append({
                    'line': i,
                    'content': line.strip(),
                    'type': 'web.json_response'
                })
        
        # Cherche les méthodes _success/_error qui utilisent web.json_response
        success_error_pattern = r'def\s+_(success|error)\s*\([^)]*\).*?return\s+web\.json_response'
        for match in re.finditer(success_error_pattern, content, re.DOTALL):
            line_num = content[:match.start()].count('\n') + 1
            issues.append({
                'line': line_num,
                'content': match.group(0)[:80] + "...",
                'type': f'method_{match.group(1)}'
            })
        
        # Vérifie si _json_default existe déjà
        has_json_default = '_json_default' in content
        
        # Vérifie les imports
        has_datetime_import = re.search(r'from datetime import.*datetime', content)
        has_json_import = re.search(r'^import json', content, re.MULTILINE)
        
        if issues:
            print(f"\n📄 {filepath.name}")
            print(f"  ❌ {len(issues)} problème(s) détecté(s)")
            print(f"  📦 _json_default: {'✅ Présent' if has_json_default else '❌ Manquant'}")
            print(f"  📦 import datetime: {'✅' if has_datetime_import else '❌'}")
            print(f"  📦 import json: {'✅' if has_json_import else '❌'}")
            
            for issue in issues[:5]:  # Limite à 5 exemples
                print(f"    L{issue['line']}: {issue['type']} - {issue['content'][:60]}...")
                
            if len(issues) > 5:
                print(f"    ... et {len(issues) - 5} autre(s)")
        
        return issues
    
    def fix_all(self, audit_results: Dict[str, List[Dict]]):
        """Applique les corrections sur tous les fichiers"""
        
        if not audit_results:
            print("\n✅ Aucun problème détecté, rien à corriger!")
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
        print(f"\n📝 {filepath.name}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 1. Ajoute les imports manquants
        content = self._ensure_imports(content)
        
        # 2. Ajoute _json_default si manquant
        content = self._ensure_json_default(content)
        
        # 3. Remplace web.json_response par web.Response
        content = self._replace_json_responses(content)
        
        # 4. Corrige les méthodes _success et _error
        content = self._fix_helper_methods(content)
        
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
                print(f"  ✅ Corrigé")
            else:
                print(f"  🧪 [DRY-RUN] Modifications simulées")
                changes = len(issues)
                print(f"     → {changes} changement(s) seraient appliqués")
        else:
            print(f"  ℹ️  Aucune modification nécessaire")
    
    def _ensure_imports(self, content: str) -> str:
        """Ajoute les imports manquants"""
        lines = content.split('\n')
        
        # Trouve la position après les imports existants
        import_end = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_end = i + 1
        
        # Vérifie et ajoute datetime
        if not re.search(r'from datetime import.*datetime', content):
            lines.insert(import_end, 'from datetime import datetime, date')
            import_end += 1
        
        # Vérifie et ajoute json
        if not re.search(r'^import json', content, re.MULTILINE):
            lines.insert(import_end, 'import json')
        
        return '\n'.join(lines)
    
    def _ensure_json_default(self, content: str) -> str:
        """Ajoute _json_default si manquant"""
        if '_json_default' in content:
            return content
        
        lines = content.split('\n')
        
        # Trouve la première classe
        class_line = -1
        for i, line in enumerate(lines):
            if line.startswith('class '):
                class_line = i
                break
        
        if class_line > 0:
            # Insère avant la première classe
            lines.insert(class_line, '')
            lines.insert(class_line, JSON_DEFAULT_FUNCTION)
        
        return '\n'.join(lines)
    
    def _replace_json_responses(self, content: str) -> str:
        """Remplace web.json_response() par web.Response()"""
        
        # Pattern pour capturer web.json_response avec ses arguments
        pattern = r'web\.json_response\s*\(\s*(\{[^}]+\})\s*(?:,\s*status\s*=\s*(\d+))?\s*\)'
        
        def replace_func(match):
            data = match.group(1)
            status = match.group(2)
            
            if status:
                return (f'web.Response(\n'
                       f'        text=json.dumps({data}, default=_json_default),\n'
                       f'        content_type="application/json",\n'
                       f'        status={status}\n'
                       f'    )')
            else:
                return (f'web.Response(\n'
                       f'        text=json.dumps({data}, default=_json_default),\n'
                       f'        content_type="application/json"\n'
                       f'    )')
        
        return re.sub(pattern, replace_func, content)
    
    def _fix_helper_methods(self, content: str) -> str:
        """Corrige les méthodes _success et _error"""
        
        # Pattern pour _success
        success_pattern = r'def _success\(self, data[^)]*\)[^:]*:\s*return web\.json_response\([^)]+\)'
        success_replacement = '''def _success(self, data, status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps({"error": False, "data": data}, default=_json_default),
            content_type="application/json",
            status=status
        )'''
        
        content = re.sub(success_pattern, success_replacement, content, flags=re.DOTALL)
        
        # Pattern pour _error
        error_pattern = r'def _error\(self, status[^)]*\)[^:]*:\s*return web\.json_response\([^)]+\)'
        error_replacement = '''def _error(self, status: int, message: str) -> web.Response:
        return web.Response(
            text=json.dumps({"error": True, "message": message}, default=_json_default),
            content_type="application/json",
            status=status
        )'''
        
        content = re.sub(error_pattern, error_replacement, content, flags=re.DOTALL)
        
        return content


def main():
    parser = argparse.ArgumentParser(description="Audit et correction des web.json_response() pour datetime")
    parser.add_argument('--audit', action='store_true', help="Audit seulement (pas de correction)")
    parser.add_argument('--dry-run', action='store_true', help="Simulation sans modification")
    parser.add_argument('--fix', action='store_true', help="Applique les corrections")
    parser.add_argument('--api-dir', default=API_DIR, help="Chemin du dossier API")
    
    args = parser.parse_args()
    
    if not any([args.audit, args.dry_run, args.fix]):
        parser.print_help()
        sys.exit(1)
    
    fixer = JSONDatetimeFixer(args.api_dir, dry_run=args.dry_run)
    
    # Audit
    print("=" * 60)
    print("🔍 AUDIT - Détection des problèmes web.json_response()")
    print("=" * 60)
    
    audit_results = fixer.audit()
    
    if not audit_results:
        print("\n✅ Aucun problème détecté!")
        return
    
    # Résumé
    total_issues = sum(len(issues) for issues in audit_results.values())
    print(f"\n📊 RÉSUMÉ:")
    print(f"  • Fichiers concernés: {len(audit_results)}")
    print(f"  • Total de problèmes: {total_issues}")
    
    # Correction si demandée
    if args.fix or args.dry_run:
        fixer.fix_all(audit_results)


if __name__ == "__main__":
    main()
