#!/usr/bin/env python3
"""
Script de nettoyage automatique des couleurs hardcodées dans les CSS
Remplace les couleurs en dur par des variables --hse-*
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# Mapping des couleurs hardcodées vers variables HSE
COLOR_MAPPING = {
    # === EXISTANT (garde tout ça) ===
    # Blancs
    r'#ffffff': 'var(--hse-surface)',
    r'#fff': 'var(--hse-surface)',
    r'rgb\(255,\s*255,\s*255\)': 'var(--hse-surface)',
    r'rgba\(255,\s*255,\s*255,\s*[\d.]+\)': 'var(--hse-surface)',
    
    # Noirs / Gris foncés (texte)
    r'#000000': 'var(--hse-text-main)',
    r'#000': 'var(--hse-text-main)',
    r'#0f172a': 'var(--hse-text-main)',
    
    # Gris moyens
    r'#64748b': 'var(--hse-text-muted)',
    r'#94a3b8': 'var(--hse-text-soft)',
    r'#e2e8f0': 'var(--hse-border)',
    r'#f1f5f9': 'var(--hse-border-soft)',
    
    # Bleus (accent)
    r'#3b82f6': 'var(--hse-accent)',
    r'#2563eb': 'var(--hse-accent-hover)',
    r'rgba\(59,\s*130,\s*246,\s*0\.1\)': 'rgba(var(--hse-accent))',
    
    # Verts (success)
    r'#10b981': 'var(--hse-success)',
    r'#059669': 'var(--hse-success)',
    r'#0b5f46': 'var(--hse-success)',
    r'rgba\(16,\s*185,\s*129,\s*0\.1\)': 'rgba(var(--hse-success))',
    
    # Oranges (warning)
    r'#f59e0b': 'var(--hse-warning)',
    r'#d97706': 'var(--hse-warning)',
    r'rgba\(245,\s*158,\s*11,\s*0\.1\)': 'rgba(var(--hse-warning))',
    
    # Rouges (error)
    r'#ef4444': 'var(--hse-error)',
    r'#dc2626': 'var(--hse-error)',
    r'rgba\(239,\s*68,\s*68,\s*0\.1\)': 'rgba(var(--hse-error))',
    
    # === NOUVEAUX AJOUTS ===
    
    # Couleurs pour thème dark
    r'#e0e0e0': 'var(--hse-text-main)',
    r'#2a2a2a': 'var(--hse-surface)',
    r'#64b5f6': 'var(--hse-accent)',
    r'#ff6b6b': 'var(--hse-error)',
    r'#1a1a1a': 'var(--hse-surface)',
    
    # Bleu marine foncé
    r'#1e293b': 'var(--hse-text-main)',
    r'#212121': 'var(--hse-text-main)',
    r'#757575': 'var(--hse-text-secondary)',
    
    # Brun/Orange foncé
    r'#92400e': 'var(--hse-warning-dark)',
    r'#e65100': 'var(--hse-warning-text)',
    
    # Badges - Info
    r'#e3f2fd': 'var(--hse-info-soft)',
    r'#1976d2': 'var(--hse-info)',
    r'#bbdefb': 'var(--hse-info-soft)',
    
    # Badges - Success
    r'#e8f5e9': 'var(--hse-success-soft)',
    r'#2e7d32': 'var(--hse-success)',
    r'#1b5e20': 'var(--hse-success-dark)',
    r'#c8e6c9': 'var(--hse-success-soft)',
    
    # Badges - Warning
    r'#fff3e0': 'var(--hse-warning-soft)',
    
    # Badges - Error
    r'#ffebee': 'var(--hse-error-soft)',
    r'#c62828': 'var(--hse-error)',
    r'#ef5350': 'var(--hse-error)',
    
    # Badges - Secondary
    r'#f5f5f5': 'var(--hse-surface-muted)',
    r'#616161': 'var(--hse-text-muted)',
    
    # Couleurs vives
    r'#00bfff': 'var(--hse-info)',
    r'#00ff7f': 'var(--hse-success)',
    
    # Gradients
    r'linear-gradient\(135deg,\s*#667eea\s+0%,\s*#764ba2\s+100%\)': 'var(--hse-gradient-header)',
    r'linear-gradient\(135deg,\s*#5b7cfa\s+0%,\s*#7c3aed\s+55%,\s*#a855f7\s+100%\)': 'var(--hse-gradient-primary)',
    r'linear-gradient\(135deg,\s*#e3f2fd\s+0%,\s*#bbdefb\s+100%\)': 'var(--hse-gradient-info)',
    r'linear-gradient\(135deg,\s*#e8f5e9\s+0%,\s*#c8e6c9\s+100%\)': 'var(--hse-gradient-success)',
    r'linear-gradient\(135deg,\s*#ff9800\s+0%,\s*#f57c00\s+100%\)': 'var(--hse-gradient-warning)',
}


class CSSColorCleaner:
    def __init__(self, css_file: Path):
        self.css_file = css_file
        self.original_content = ""
        self.cleaned_content = ""
        self.replacements: List[Tuple[str, str, int]] = []
    
    def load(self):
        """Charge le fichier CSS"""
        self.original_content = self.css_file.read_text(encoding='utf-8')
        self.cleaned_content = self.original_content
        print(f"✅ Chargé: {self.css_file.name}")
    
    def clean(self):
        """Remplace les couleurs hardcodées"""
        for pattern, replacement in COLOR_MAPPING.items():
            matches = list(re.finditer(pattern, self.cleaned_content, re.IGNORECASE))
            if matches:
                self.cleaned_content = re.sub(pattern, replacement, self.cleaned_content, flags=re.IGNORECASE)
                for match in matches:
                    self.replacements.append((match.group(), replacement, match.start()))
        
        print(f"🧹 {len(self.replacements)} remplacement(s) effectué(s)")
    
    def save(self, backup=True):
        """Sauvegarde le fichier nettoyé"""
        if backup:
            backup_file = self.css_file.with_suffix('.css.backup')
            backup_file.write_text(self.original_content, encoding='utf-8')
            print(f"💾 Backup: {backup_file.name}")
        
        self.css_file.write_text(self.cleaned_content, encoding='utf-8')
        print(f"✅ Sauvegardé: {self.css_file.name}")
    
    def report(self):
        """Génère un rapport des modifications"""
        if not self.replacements:
            print("   ℹ️  Aucune modification nécessaire")
            return
        
        print(f"\n📊 Rapport pour {self.css_file.name}:")
        print("─" * 70)
        
        # Groupe par type de remplacement
        by_replacement = {}
        for original, replacement, _ in self.replacements:
            if replacement not in by_replacement:
                by_replacement[replacement] = []
            by_replacement[replacement].append(original)
        
        for replacement, originals in by_replacement.items():
            unique_originals = set(originals)
            print(f"  {replacement}")
            for orig in unique_originals:
                count = originals.count(orig)
                print(f"    ← {orig} ({count}x)")
        print()

def main():
    print("=" * 70)
    print("🧹 NETTOYAGE AUTOMATIQUE DES COULEURS HARDCODÉES")
    print("=" * 70)
    print()
    
    # Fichiers à nettoyer
    base_path = Path("custom_components/home_suivi_elec/web_static/features")
    css_files = [
        base_path / "diagnostics" / "diagnostics.css",
        base_path / "history" / "history.css",
        base_path / "migration" / "migration.css",
        base_path / "summary" / "summary.css",
    ]
    
    total_replacements = 0
    
    for css_file in css_files:
        if not css_file.exists():
            print(f"⚠️  Fichier introuvable: {css_file}")
            continue
        
        print(f"\n{'='*70}")
        print(f"📄 Traitement: {css_file.name}")
        print(f"{'='*70}")
        
        cleaner = CSSColorCleaner(css_file)
        cleaner.load()
        cleaner.clean()
        cleaner.save(backup=True)
        cleaner.report()
        
        total_replacements += len(cleaner.replacements)
    
    print("=" * 70)
    print(f"✅ TERMINÉ : {total_replacements} remplacement(s) au total")
    print("=" * 70)
    print()
    print("💡 Les fichiers originaux ont été sauvegardés avec l'extension .backup")
    print("💡 Vérifie les modifications puis supprime les .backup si tout est OK")

if __name__ == "__main__":
    main()
