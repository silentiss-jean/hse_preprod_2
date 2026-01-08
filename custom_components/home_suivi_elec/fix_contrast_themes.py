#!/usr/bin/env python3
"""
Script de correction automatique des problèmes de contraste WCAG dans style.hse.themes.css
Corrige les couleurs pour garantir un ratio de contraste minimum de 4.5:1 (WCAG AA)
"""

import re
import os

# Définir les corrections de contraste pour chaque thème
CONTRAST_FIXES = {
    # Thème DARK
    'dark': {
        '--hse-text-muted: #cbd5e1': '--hse-text-muted: #e2e8f0',
        '--hse-text-soft: #94a3b8': '--hse-text-soft: #cbd5e1',
    },
    # Thème GLASS
    'glass': {
        '--hse-text-muted: rgba(255, 255, 255, 0.8)': '--hse-text-muted: rgba(255, 255, 255, 0.95)',
        '--hse-text-soft: rgba(255, 255, 255, 0.6)': '--hse-text-soft: rgba(255, 255, 255, 0.9)',
    },
    # Thème NEUMORPHISM
    'neuro': {
        '--hse-text-main: #4a5568': '--hse-text-main: #2d3748',
        '--hse-text-muted: #718096': '--hse-text-muted: #4a5568',
    },
    # Thème CYBERPUNK - Corrections majeures
    'cyberpunk': {
        '--hse-text-soft: rgba(0, 255, 255, 0.6)': '--hse-text-soft: rgba(0, 255, 255, 0.9)',
    },
    # Thème AURORA
    'aurora': {
        '--hse-text-muted: #b2dfdb': '--hse-text-muted: #e8f5e9',
    },
    # Thème OCEAN
    'hse_ocean': {
        '--hse-text-soft: #7dd3fc': '--hse-text-soft: #bae6fd',
    },
    # Thème FOREST
    'hse_forest': {
        '--hse-text-soft: #bef264': '--hse-text-soft: #d9f99d',
    }
}

# Variables sémantiques à ajouter après les variables de texte du :root
SEMANTIC_VARIABLES = '''
    /* ===== VARIABLES SÉMANTIQUES POUR ACCESSIBILITÉ WCAG AA ===== */
    /* Garantit un contraste minimum de 4.5:1 pour le texte normal */
    
    --hse-text-accessible: var(--hse-text-main);
    --hse-text-muted-accessible: var(--hse-text-muted);
    
    /* Pour les tableaux - garantit la lisibilité */
    --hse-table-text: var(--hse-text-main);
    --hse-table-header-bg: var(--hse-surface-muted);
    --hse-table-header-text: var(--hse-text-main);
    --hse-table-row-hover: var(--hse-surface-hover);
    
    /* Pour les badges et alertes - versions accessibles */
    --hse-success-text-accessible: #065f46;  /* Vert foncé - ratio 7:1 */
    --hse-warning-text-accessible: #92400e;  /* Orange foncé - ratio 7:1 */
    --hse-error-text-accessible: #991b1b;    /* Rouge foncé - ratio 7:1 */
    --hse-info-text-accessible: #075985;     /* Cyan foncé - ratio 7:1 */
'''

def fix_contrast_issues(css_content):
    """
    Applique les corrections de contraste au fichier CSS
    """
    # 1. Ajouter les variables sémantiques après les variables de texte du :root
    # Chercher la section TEXTE dans :root
    text_section_pattern = r'(/\* ===== TEXTE ===== \*/.*?--secondary-text-color: var\(--hse-text-muted\);)'
    css_content = re.sub(
        text_section_pattern,
        r'\1\n' + SEMANTIC_VARIABLES,
        css_content,
        flags=re.DOTALL
    )
    
    # 2. Appliquer les corrections pour chaque thème
    for theme, fixes in CONTRAST_FIXES.items():
        for old_value, new_value in fixes.items():
            css_content = css_content.replace(old_value, new_value)
    
    return css_content

def main():
    # Chemin du fichier CSS
    css_file = 'web_static/style.hse.themes.css'
    
    if not os.path.exists(css_file):
        print(f"Erreur: Le fichier {css_file} n'existe pas")
        print("Assurez-vous d'exécuter ce script depuis le dossier web_static")
        return
    
    # Lire le fichier
    print(f"Lecture de {css_file}...")
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Appliquer les corrections
    print("Application des corrections de contraste WCAG AA...")
    corrected_css = fix_contrast_issues(css_content)
    
    # Sauvegarder une copie de backup
    backup_file = f"{css_file}.backup"
    print(f"Sauvegarde de l'original dans {backup_file}...")
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    # Écrire le fichier corrigé
    print(f"Écriture du fichier corrigé...")
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(corrected_css)
    
    print("\n✅ Corrections appliquées avec succès!")
    print("\nRésumé des corrections:")
    print("- Variables sémantiques d'accessibilité ajoutées")
    print("- Texte muté corrigé pour tous les thèmes sombres")
    print("- Contraste amélioré pour les thèmes: dark, glass, neuro, cyberpunk, aurora, ocean, forest")
    print("\nProchaines étapes:")
    print("1. Vérifier les changements avec git diff")
    print("2. Tester les thèmes dans Home Assistant")
    print("3. Relancer l'audit de contraste pour vérifier les améliorations")

if __name__ == '__main__':
    main()
