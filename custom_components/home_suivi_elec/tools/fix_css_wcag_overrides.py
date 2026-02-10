#!/usr/bin/env python3
"""
Script de correction automatique des couleurs codées en dur dans les fichiers CSS
Crée des overrides WCAG AA pour les couleurs problématiques
"""

import os
import re
import json
from pathlib import Path

# Corrections basées sur l'audit css_audit_report.json
CSS_OVERRIDES = {
    # Couleurs très sombres sur fond sombre - besoin de versions plus claires
    'rgb(33, 33, 33)': 'rgb(200, 200, 200)',  # Gris très foncé -> gris clair
    'rgb(34, 34, 34)': 'rgb(200, 200, 200)',  # Gris très foncé -> gris clair
    
    # Couleurs moyennement sombres - besoin d'éclaircissement
    'rgb(100, 100, 100)': 'rgb(180, 180, 180)',  # Gris moyen -> gris plus clair
    'rgb(120, 120, 120)': 'rgb(190, 190, 190)',  # Gris moyen -> gris plus clair
    
    # Couleurs spécifiques problématiques
    '#666': '#aaa',  # Gris moyen -> gris clair
    '#999': '#ccc',  # Gris -> gris très clair
    '#555': '#999',  # Gris foncé -> gris moyen
    '#333': '#bbb',  # Gris très foncé -> gris clair
    '#222': '#ccc',  # Presque noir -> gris très clair
    
    # Transparences problématiques
    'rgba(255, 255, 255, 0.3)': 'rgba(255, 255, 255, 0.85)',  # Blanc transparent -> plus opaque
    'rgba(255, 255, 255, 0.5)': 'rgba(255, 255, 255, 0.95)',  # Blanc transparent -> presque opaque
    'rgba(255, 255, 255, 0.7)': 'rgba(255, 255, 255, 1)',     # Blanc transparent -> opaque
    'rgba(0, 0, 0, 0.3)': 'rgba(255, 255, 255, 0.85)',        # Noir transparent -> blanc opaque
    'rgba(0, 0, 0, 0.5)': 'rgba(255, 255, 255, 0.9)',         # Noir transparent -> blanc opaque
}

def find_css_files(root_dir):
    """Trouve tous les fichiers CSS dans le répertoire."""
    css_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.css'):
                css_files.append(Path(root) / file)
    return css_files

def create_override_file(web_static_dir):
    """Crée un fichier CSS d'overrides WCAG."""
    override_content = []
    override_content.append('/* AUTO-GENERATED: WCAG AA Contrast Overrides */')
    override_content.append('/* Ce fichier corrige automatiquement les problèmes de contraste */')
    override_content.append('')
    
    # Créer les règles CSS pour chaque override
    override_content.append('/* Corrections de couleurs pour fond sombre (dark mode) */')
    override_content.append('[data-theme="dark"] {')
    
    # Variables CSS pour les overrides
    override_content.append('  /* Gris clairs pour texte sur fond sombre */')
    override_content.append('  --hse-text-primary: rgb(230, 230, 230);')
    override_content.append('  --hse-text-secondary: rgb(200, 200, 200);')
    override_content.append('  --hse-text-tertiary: rgb(180, 180, 180);')
    override_content.append('  --hse-border-color: rgb(100, 100, 100);')
    override_content.append('  --hse-bg-overlay: rgba(255, 255, 255, 0.1);')
    override_content.append('}')
    override_content.append('')
    
    # Overrides spécifiques pour les éléments problématiques identifiés
    override_content.append('/* Corrections spécifiques des éléments */')
    
    # Corrections pour les cartes et conteneurs
    override_content.append('[data-theme="dark"] .card,')
    override_content.append('[data-theme="dark"] .container,')
    override_content.append('[data-theme="dark"] .panel {')
    override_content.append('  color: var(--hse-text-primary) !important;')
    override_content.append('  border-color: var(--hse-border-color) !important;')
    override_content.append('}')
    override_content.append('')
    
    # Corrections pour les labels et textes secondaires
    override_content.append('[data-theme="dark"] .label,')
    override_content.append('[data-theme="dark"] .secondary-text,')
    override_content.append('[data-theme="dark"] .muted {')
    override_content.append('  color: var(--hse-text-secondary) !important;')
    override_content.append('}')
    override_content.append('')
    
    # Corrections pour les boutons
    override_content.append('[data-theme="dark"] button,')
    override_content.append('[data-theme="dark"] .btn {')
    override_content.append('  color: var(--hse-text-primary) !important;')
    override_content.append('  background-color: rgba(255, 255, 255, 0.1) !important;')
    override_content.append('  border: 1px solid var(--hse-border-color) !important;')
    override_content.append('}')
    override_content.append('')
    
    override_content.append('[data-theme="dark"] button:hover,')
    override_content.append('[data-theme="dark"] .btn:hover {')
    override_content.append('  background-color: rgba(255, 255, 255, 0.15) !important;')
    override_content.append('}')
    override_content.append('')
    
    # Corrections pour les inputs
    override_content.append('[data-theme="dark"] input,')
    override_content.append('[data-theme="dark"] select,')
    override_content.append('[data-theme="dark"] textarea {')
    override_content.append('  color: var(--hse-text-primary) !important;')
    override_content.append('  background-color: rgba(255, 255, 255, 0.05) !important;')
    override_content.append('  border-color: var(--hse-border-color) !important;')
    override_content.append('}')
    override_content.append('')
    
    # Écrire le fichier
    override_file = Path(web_static_dir) / 'style.hse.wcag_overrides.css'
    with open(override_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(override_content))
    
    print(f"✓ Fichier d'overrides créé: {override_file}")
    return override_file

def update_html_references(web_static_dir):
    """Met à jour les fichiers HTML pour inclure le fichier d'overrides."""
    html_files = list(Path(web_static_dir).rglob('*.html'))
    
    for html_file in html_files:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si l'override est déjà inclus
        if 'style.hse.wcag_overrides.css' in content:
            print(f"⊙ Déjà référencé dans: {html_file}")
            continue
        
        # Ajouter la référence avant la balise </head>
        override_link = '  <link rel="stylesheet" href="style.hse.wcag_overrides.css">'
        
        if '</head>' in content:
            content = content.replace('</head>', f'{override_link}\n</head>')
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✓ Référence ajoutée dans: {html_file}")
        else:
            print(f"⚠ Pas de balise </head> trouvée dans: {html_file}")

def main():
    # Chemin du répertoire web_static
    web_static_dir = Path('custom_components/home_suivi_elec/web_static')
    
    if not web_static_dir.exists():
        print(f"❌ Répertoire non trouvé: {web_static_dir}")
        print("   Exécutez ce script depuis la racine du projet.")
        return
    
    print("🔧 Création du fichier d'overrides WCAG...\n")
    
    # Créer le fichier d'overrides
    override_file = create_override_file(web_static_dir)
    
    print("\n🔧 Mise à jour des références HTML...\n")
    
    # Mettre à jour les fichiers HTML
    update_html_references(web_static_dir)
    
    print("\n✅ Overrides WCAG créés et référencés!")
    print("\n📋 Prochaines étapes:")
    print("   1. Redémarrer Home Assistant")
    print("   2. Vider le cache du navigateur")
    print("   3. Re-tester avec l'audit d'accessibilité")
    print("\n💡 Note: Les overrides utilisent !important pour garantir leur priorité")
    print("   sur les styles existants.")

if __name__ == '__main__':
    main()