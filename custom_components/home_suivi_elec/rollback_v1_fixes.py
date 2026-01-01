#!/usr/bin/env python3
"""
Script de rollback des modifications du premier script (fix_json_datetime.py)
Détecte et restaure automatiquement les fichiers modifiés par le script v1

Usage:
  python3 rollback_v1_fixes.py --check      # Vérifie quels fichiers ont été modifiés
  python3 rollback_v1_fixes.py --rollback   # Restaure depuis les .bak
"""

import argparse
import shutil
from pathlib import Path
from typing import List, Tuple

# Configuration
COMPONENT_DIR = "/config/custom_components/home_suivi_elec"
BACKUP_SUFFIX = ".bak"


class RollbackV1Fixer:
    """Rollback automatique des modifications du script v1"""
    
    def __init__(self, component_dir: str):
        self.component_dir = Path(component_dir)
        
    def find_backups(self) -> List[Tuple[Path, Path]]:
        """Trouve tous les fichiers .bak créés par le script v1"""
        backups = []
        
        for backup_file in self.component_dir.rglob(f"*{BACKUP_SUFFIX}"):
            original_file = backup_file.with_suffix("")
            
            if original_file.exists():
                backups.append((original_file, backup_file))
        
        return backups
    
    def check_v1_signatures(self, filepath: Path) -> dict:
        """Détecte les signatures du script v1 dans un fichier"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {"error": str(e)}
        
        signatures = {
            "has_web_response": "web.Response(" in content and "json.dumps(" in content,
            "has_json_default_standalone": "def _json_default(obj):" in content and \
                                          "def _json_default(self, obj):" not in content,
            "has_json_dumps_default": "json.dumps(" in content and "default=_json_default" in content,
            "uses_json_response_wrapper": "from .utils.json_response import json_response" in content or \
                                         "from ..utils.json_response import json_response" in content,
        }
        
        # Le fichier a été modifié par v1 s'il a les patterns spécifiques
        signatures["is_v1_modified"] = (
            signatures["has_web_response"] and 
            signatures["has_json_dumps_default"] and
            not signatures["uses_json_response_wrapper"]
        )
        
        return signatures
    
    def analyze(self):
        """Analyse les fichiers et affiche le rapport"""
        print("=" * 60)
        print("🔍 ANALYSE - Détection des modifications du script v1")
        print("=" * 60)
        print()
        
        backups = self.find_backups()
        
        if not backups:
            print("✅ Aucun fichier .bak trouvé")
            print("   Soit le script v1 n'a jamais été exécuté,")
            print("   soit les backups ont été supprimés.")
            return []
        
        print(f"📦 {len(backups)} fichier(s) avec backup détecté(s)\n")
        
        files_to_rollback = []
        
        for original, backup in backups:
            rel_path = original.relative_to(self.component_dir)
            print(f"📄 {rel_path}")
            
            # Analyse le fichier actuel
            current_sigs = self.check_v1_signatures(original)
            
            if "error" in current_sigs:
                print(f"  ⚠️  Erreur lecture: {current_sigs['error']}")
                continue
            
            # Analyse le backup
            backup_sigs = self.check_v1_signatures(backup)
            
            print(f"  📊 Fichier actuel:")
            print(f"     • web.Response() + json.dumps(): {'✅' if current_sigs['has_web_response'] else '❌'}")
            print(f"     • _json_default standalone: {'✅' if current_sigs['has_json_default_standalone'] else '❌'}")
            print(f"     • Wrapper json_response: {'✅' if current_sigs['uses_json_response_wrapper'] else '❌'}")
            
            if current_sigs["is_v1_modified"]:
                print(f"  🔴 Modifié par script v1 → À restaurer")
                files_to_rollback.append((original, backup))
            else:
                print(f"  ✅ Pas de signature v1 détectée")
            
            # Info sur le backup
            backup_size = backup.stat().st_size
            current_size = original.stat().st_size
            diff = current_size - backup_size
            print(f"  💾 Backup: {backup.name} ({backup_size} bytes, diff: {diff:+d})")
            print()
        
        return files_to_rollback
    
    def rollback(self, files_to_rollback: List[Tuple[Path, Path]], dry_run: bool = False):
        """Restaure les fichiers depuis les backups"""
        
        if not files_to_rollback:
            print("\n✅ Aucun fichier à restaurer!")
            return
        
        print("\n" + "=" * 60)
        print(f"{'🧪 DRY-RUN: Simulation de rollback' if dry_run else '🔄 ROLLBACK EN COURS'}")
        print("=" * 60)
        print()
        
        for original, backup in files_to_rollback:
            rel_path = original.relative_to(self.component_dir)
            
            if dry_run:
                print(f"🧪 [DRY-RUN] Restaurerait: {rel_path}")
                print(f"   Depuis: {backup.name}")
            else:
                try:
                    # Copie le backup vers l'original
                    shutil.copy2(backup, original)
                    print(f"✅ Restauré: {rel_path}")
                    print(f"   Depuis: {backup.name}")
                except Exception as e:
                    print(f"❌ Erreur: {rel_path}")
                    print(f"   {str(e)}")
        
        print()
        
        if dry_run:
            print("✅ Dry-run terminé (aucune modification réelle)")
        else:
            print("✅ Rollback terminé!")
            print("\n📋 Prochaines étapes:")
            print("   1. Vérifie que les fichiers sont corrects")
            print("   2. Lance le script v2 pour tout harmoniser:")
            print("      python3 fix_json_datetime_v2.py --audit")
            print("      python3 fix_json_datetime_v2.py --fix")
            print("   3. Redémarre HA: ha core restart")


def main():
    parser = argparse.ArgumentParser(
        description="Rollback des modifications du script v1 (fix_json_datetime.py)"
    )
    parser.add_argument('--check', action='store_true', 
                       help="Vérifie quels fichiers ont été modifiés par v1")
    parser.add_argument('--dry-run', action='store_true', 
                       help="Simulation du rollback sans modification")
    parser.add_argument('--rollback', action='store_true', 
                       help="Restaure les fichiers depuis les backups")
    parser.add_argument('--dir', default=COMPONENT_DIR, 
                       help="Chemin du composant")
    
    args = parser.parse_args()
    
    if not any([args.check, args.dry_run, args.rollback]):
        parser.print_help()
        return
    
    rollbacker = RollbackV1Fixer(args.dir)
    
    # Analyse
    files_to_rollback = rollbacker.analyze()
    
    # Rollback si demandé
    if args.rollback or args.dry_run:
        rollbacker.rollback(files_to_rollback, dry_run=args.dry_run)


if __name__ == "__main__":
    main()


