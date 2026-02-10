#!/usr/bin/env python3
"""
Script de correction automatique des couleurs codées en dur dans les fichiers JavaScript
Corrige les couleurs RGB problématiques pour respecter WCAG AA (ratio 4.5:1)
"""

import os
import re
import json
from pathlib import Path

# Couleurs problématiques identifiées dans l'audit
PROBLEMATIC_COLORS = {
    # Couleurs très sombres sur fond sombre (rgb(33, 33, 33), rgb(34, 34, 34))
    r'rgb\(\s*3[34]\s*,\s*3[34]\s*,\s*3[34]\s*\)': 'var(--hse-text-accessible)',
    r'rgba\(\s*3[34]\s*,\s*3[34]\s*,\s*3[34]\s*,\s*[\d.]+\s*\)': 'var(--hse-text-accessible)',
    
    # Autres couleurs sombres problématiques
    r'rgb\(\s*4[0-9]\s*,\s*4[0-9]\s*,\s*4[0-9]\s*\)': 'var(--hse-text-main)',
    r'#212121': 'var(--hse-text-accessible)',
    r'#222222': 'var(--hse-text-accessible)',
    
    # Couleurs grises claires sur fond clair (faible contraste)
    r'rgb\(\s*20[0-9]\s*,\s*20[0-9]\s*,\s*20[0-9]\s*\)': 'var(--hse-text-muted-accessible)',
    r'#cccccc': 'var(--hse-text-muted-accessible)',
    r'#d3d3d3': 'var(--hse-text-muted-accessible)',
}

# Classes CSS à ajouter au fichier style.hse.themes.css
CSS_CLASSES_TO_ADD = """
/* ===== CLASSES POUR ÉLÉMENTS DYNAMIQUES (JavaScript) ===== */

/* Classes pour les top consumers */
.hse-top-consumers-line {
    color: var(--hse-text-accessible) !important;
}

.hse-top-consumers-bar {
    background-color: var(--hse-primary) !important;
}

/* Classes pour les coûts */
.hse-costs-entity-name {
    color: var(--hse-text-accessible) !important;
}

.hse-costs-amount {
    color: var(--hse-text-main) !important;
    font-weight: 600;
}

/* Classes pour les tableaux */
td.summary-period,
th.hse-costs-th {
    color: var(--hse-text-accessible) !important;
}

.hse-table-row {
    color: var(--hse-text-accessible) !important;
}

.hse-table-header {
    color: var(--hse-text-main) !important;
    background-color: var(--hse-table-header-bg) !important;
}

/* Classes pour les graphiques */
.hse-chart-label {
    color: var(--hse-text-accessible) !important;
}

.hse-chart-value {
    color: var(--hse-text-main) !important;
    font-weight: 600;
}

/* Classes pour les badges et alertes accessibles */
.hse-badge-success {
    background-color: var(--hse-success-bg);
    color: var(--hse-success-text-accessible);
}

.hse-badge-warning {
    background-color: var(--hse-warning-bg);
    color: var(--hse-warning-text-accessible);
}

.hse-badge-error {
    background-color: var(--hse-error-bg);
    color: var(--hse-error-text-accessible);
}

.hse-badge-info {
    background-color: var(--hse-info-bg);
    color: var(--hse-info-text-accessible);
}
"""

def find_js_files(web_static_dir):
    """
    Trouve tous les fichiers JavaScript dans web_static
    """
    js_files = []
    for root, dirs, files in os.walk(web_static_dir):
        for file in files:
            if file.endswith('.js') and not file.endswith('.min.js'):
                js_files.append(os.path.join(root, file))
    return js_files

def fix_hardcoded_colors(content):
    """
    Remplace les couleurs codées en dur par des variables CSS
    """
    original_content = content
    
    for pattern, replacement in PROBLEMATIC_COLORS.items():
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    
    # Compter les remplacements
    changes_count = len(re.findall('|'.join(PROBLEMATIC_COLORS.keys()), original_content, re.IGNORECASE))
    
    return content, changes_count

def add_css_classes(css_file):
    """
    Ajoute les classes CSS nécessaires au fichier de thèmes
    """
    if not os.path.exists(css_file):
        print(f"❌ Erreur: Le fichier {css_file} n'existe pas")
        return False
    
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Vérifier si les classes sont déjà présentes
    if 'CLASSES POUR ÉLÉMENTS DYNAMIQUES' in css_content:
        print(f"ℹ️  Les classes CSS sont déjà présentes dans {css_file}")
        return True
    
    # Ajouter les classes à la fin du fichier
    css_content += '\n' + CSS_CLASSES_TO_ADD
    
    # Sauvegarder
    backup_file = f"{css_file}.js_fixes_backup"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(css_content)
    print(f"💾 Backup créé: {backup_file}")
    
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    print(f"✅ Classes CSS ajoutées à {css_file}")
    return True

def main():
    # Chemins
    web_static_dir = 'web_static'
    css_file = 'web_static/style.hse.themes.css'
    
    if not os.path.exists(web_static_dir):
        print(f"❌ Erreur: Le dossier {web_static_dir} n'existe pas")
        print("Assurez-vous d'exécuter ce script depuis le dossier home_suivi_elec")
        return
    
    print("🔍 Recherche des fichiers JavaScript...")
    js_files = find_js_files(web_static_dir)
    print(f"📁 {len(js_files)} fichiers JavaScript trouvés\n")
    
    # Statistiques
    total_changes = 0
    files_modified = []
    
    # Traiter chaque fichier
    for js_file in js_files:
        print(f"📝 Traitement de {js_file}...")
        
        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        fixed_content, changes = fix_hardcoded_colors(content)
        
        if changes > 0:
            # Créer un backup
            backup_file = f"{js_file}.backup"
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Écrire le fichier corrigé
            with open(js_file, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            files_modified.append(js_file)
            total_changes += changes
            print(f"  ✅ {changes} couleur(s) corrigée(s)")
        else:
            print(f"  ✓ Aucune couleur problématique trouvée")
    
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DES CORRECTIONS")
    print("="*60)
    print(f"✅ Fichiers modifiés: {len(files_modified)}")
    print(f"🎨 Total de couleurs corrigées: {total_changes}\n")
    
    if files_modified:
        print("Fichiers modifiés:")
        for file in files_modified:
            print(f"  - {file}")
    
    # Ajouter les classes CSS
    print("\n" + "="*60)
    print("🎨 AJOUT DES CLASSES CSS")
    print("="*60)
    add_css_classes(css_file)
    
    print("\n" + "="*60)
    print("🎉 CORRECTIONS TERMINÉES")
    print("="*60)
    print("\nProchaines étapes:")
    print("1. Vérifier les changements avec: git diff")
    print("2. Tester l'interface dans Home Assistant")
    print("3. Relancer l'audit de contraste WCAG")
    print("4. Commit et push si tout est OK")

if __name__ == '__main__':
    main()