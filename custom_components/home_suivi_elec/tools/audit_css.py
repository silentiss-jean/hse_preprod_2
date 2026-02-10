#!/usr/bin/env python3
"""
HSE CSS Architecture Auditor
Analyse la structure CSS actuelle et génère un rapport d'harmonisation
"""

import os
import re
from pathlib import Path
from collections import defaultdict
import json

class CSSAuditor:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.results = {
            "modules": {},
            "css_files": [],
            "missing_css": [],
            "variable_usage": defaultdict(int),
            "selectors": defaultdict(list),
            "inconsistencies": []
        }
    
    def scan_structure(self):
        """Scanne la structure web_static/"""
        features_path = self.base_path / "features"
        
        if not features_path.exists():
            print(f"❌ Chemin introuvable: {features_path}")
            return
        
        for module_dir in sorted(features_path.iterdir()):
            if not module_dir.is_dir():
                continue
            
            module_name = module_dir.name
            css_file = module_dir / f"{module_name}.css"
            js_file = module_dir / f"{module_name}.js"
            
            self.results["modules"][module_name] = {
                "path": str(module_dir),
                "has_css": css_file.exists(),
                "has_js": js_file.exists(),
                "css_path": str(css_file) if css_file.exists() else None
            }
            
            if css_file.exists():
                self.results["css_files"].append(str(css_file))
                self.analyze_css_file(css_file, module_name)
            else:
                self.results["missing_css"].append(module_name)
    
    def analyze_css_file(self, css_path, module_name):
        """Analyse un fichier CSS"""
        try:
            content = css_path.read_text(encoding='utf-8')
            
            # Recherche variables CSS utilisées
            var_pattern = r'var\((--[\w-]+)'
            variables = re.findall(var_pattern, content)
            for var in variables:
                self.results["variable_usage"][var] += 1
            
            # Recherche sélecteurs de classe
            class_pattern = r'\.([a-zA-Z][\w-]*)'
            classes = re.findall(class_pattern, content)
            for cls in set(classes):
                self.results["selectors"][cls].append(module_name)
            
            # Détecte hardcoded colors
            color_pattern = r'(?:color|background|border):\s*(#[0-9a-fA-F]{3,6}|rgb|rgba)'
            hardcoded = re.findall(color_pattern, content)
            if hardcoded:
                self.results["inconsistencies"].append({
                    "module": module_name,
                    "type": "hardcoded_colors",
                    "count": len(hardcoded),
                    "examples": hardcoded[:3]
                })
                
        except Exception as e:
            print(f"⚠️  Erreur lecture {css_path}: {e}")
    
    def check_theme_consistency(self):
        """Vérifie que les variables --hse-* sont utilisées"""
        theme_path = self.base_path / "style.hse.themes.css"
        
        if not theme_path.exists():
            print(f"❌ Fichier thème introuvable: {theme_path}")
            return
        
        content = theme_path.read_text(encoding='utf-8')
        
        # Extract defined variables
        defined_vars = set(re.findall(r'(--hse-[\w-]+):', content))
        used_vars = set(self.results["variable_usage"].keys())
        
        unused = defined_vars - used_vars
        undefined = used_vars - defined_vars
        
        self.results["theme_analysis"] = {
            "defined_variables": len(defined_vars),
            "used_variables": len(used_vars),
            "unused_variables": list(unused)[:10],
            "undefined_variables": list(undefined)[:10]
        }
    
    def generate_report(self):
        """Génère le rapport final"""
        print("\n" + "="*70)
        print("🎨 AUDIT CSS — HOME SUIVI ÉLEC")
        print("="*70 + "\n")
        
        # Modules
        print("📁 MODULES DÉTECTÉS")
        print("-" * 70)
        for module, info in self.results["modules"].items():
            status = "✅" if info["has_css"] else "❌"
            print(f"  {status} {module:20} | CSS: {info['has_css']:5} | JS: {info['has_js']}")
        
        # Missing CSS
        if self.results["missing_css"]:
            print(f"\n⚠️  MODULES SANS CSS ({len(self.results['missing_css'])})")
            print("-" * 70)
            for module in self.results["missing_css"]:
                print(f"  • {module}")
        
        # Variable usage
        print(f"\n🎨 VARIABLES CSS ({len(self.results['variable_usage'])})")
        print("-" * 70)
        top_vars = sorted(self.results["variable_usage"].items(), 
                         key=lambda x: x[1], reverse=True)[:10]
        for var, count in top_vars:
            print(f"  {var:30} utilisé {count:3}x")
        
        # Inconsistencies
        if self.results["inconsistencies"]:
            print(f"\n⚠️  INCOHÉRENCES DÉTECTÉES ({len(self.results['inconsistencies'])})")
            print("-" * 70)
            for issue in self.results["inconsistencies"]:
                print(f"  • {issue['module']}: {issue['type']} ({issue['count']} occurrences)")
                if "examples" in issue:
                    for ex in issue["examples"]:
                        print(f"    → {ex}")
        
        # Theme analysis
        if "theme_analysis" in self.results:
            ta = self.results["theme_analysis"]
            print(f"\n🎨 ANALYSE DU THÈME")
            print("-" * 70)
            print(f"  Variables définies : {ta['defined_variables']}")
            print(f"  Variables utilisées : {ta['used_variables']}")
            if ta["unused_variables"]:
                print(f"  Variables inutilisées ({len(ta['unused_variables'])}) :")
                for var in ta["unused_variables"][:5]:
                    print(f"    • {var}")
            if ta["undefined_variables"]:
                print(f"  Variables non définies ({len(ta['undefined_variables'])}) :")
                for var in ta["undefined_variables"][:5]:
                    print(f"    • {var}")
        
        print("\n" + "="*70)
        print("✅ AUDIT TERMINÉ")
        print("="*70 + "\n")
        
        # Save JSON
        output_file = self.base_path / "css_audit_report.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"📄 Rapport JSON : {output_file}")
    
    def run(self):
        """Exécute l'audit complet"""
        print("🔍 Démarrage de l'audit CSS...\n")
        self.scan_structure()
        self.check_theme_consistency()
        self.generate_report()

if __name__ == "__main__":
    # Path à ajuster selon ton environnement
    base_path = "custom_components/home_suivi_elec/web_static"
    
    auditor = CSSAuditor(base_path)
    auditor.run()
