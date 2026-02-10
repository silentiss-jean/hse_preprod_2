import os
import re
import json

CRITICAL_FUNCTIONS = [
    "enrichWithQualityScores", "categorizeSensors", "applyIgnoredFilter", "annotateSameDevice",
    "indexByDuplicateGroup", "computeSensorScore", "saveSelectionToBackend",
]
PANEL_CLASSES = [
    "SelectionPanel", "DuplicatesPanel", "ReferencePanel", "SavePanel",
]
SHARED_COMPONENTS = [
    "Button", "Badge", "Card", "Toast", "Modal", "Spinner", "Table"
]
API_PATTERNS = ["api/", "api.js"]
STATE_PATTERNS = ["state/", "state.js"]
VIEW_PATTERNS = ["view/", "view.js"]
SHARED_PATHS = ["shared/", "shared/components/", "shared/utils/"]
CORE_PATHS = ["core/app.js", "core/router.js"]
WEB_STATIC_ROOT = "web_static/"

def tree(dir_path):
    out = []
    for root, dirs, files in os.walk(dir_path):
        level = root.replace(dir_path, '').count(os.sep)
        indent = '│   ' * (level)
        out.append(f"{indent}├── {os.path.basename(root)}/")
        subindent = '│   ' * (level + 1)
        for f in files:
            out.append(f"{subindent}└── {f}")
    return "\n".join(out)

def find_all_func_classes(root_dir):
    all_funcs = {}
    all_classes = {}
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".js"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                funcs = set(re.findall(r'(?:function|const|let)\s+(\w+)\s*[\(\=:]', content))
                classes = set(re.findall(r'class\s+(\w+)', content))
                all_funcs[path] = funcs
                all_classes[path] = classes
    return all_funcs, all_classes

def find_component_usages(root_dir, component_names):
    comp_usage = {}
    for c in component_names:
        comp_usage[c] = []
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith(".js"):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if re.search(r'\b{}\b'.format(c), content):
                        comp_usage[c].append(path)
    return comp_usage

def get_example(file, count=8):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return ''.join([next(f) for _ in range(count)]).strip()
    except Exception:
        return ""

def main():
    report = {
        "tree": tree(WEB_STATIC_ROOT),
        "critical_functions": {},
        "critical_classes": {},
        "panel_presence": {},
        "panel_code_examples": {},
        "api_files": [],
        "state_files": [],
        "view_files": [],
        "core_files": [],
        "shared_components": {},
        "functions_present_elsewhere": [],
        "actions_list": [],
        "final_notes": [
            "NE SUPPRIMEZ JAMAIS une fonction métier sans recopie/test confirmé.",
            "Tout shared/component doit s'importer par un chemin correct (relative à features ou shared).",
            "Validez chaque migration par Q/A avant suppression du legacy.",
            "Tous les panels / API / state doivent utiliser les patterns d'import/export existants dans shared/components quand pertinent."
        ]
    }
    # Tree + all files
    root_dir = WEB_STATIC_ROOT
    all_funcs, all_classes = find_all_func_classes(root_dir)

    # Critical
    for fn in CRITICAL_FUNCTIONS:
        locs = [p for p, fs in all_funcs.items() if fn in fs]
        report["critical_functions"][fn] = locs
        if len(locs) == 0:
            report["actions_list"].append({
                "problem": f"{fn} introuvable dans l'arborescence.",
                "advice": f"Vérifier migration, NE PAS SUPPRIMER SI ENCORE UTILISÉ."
            })
        elif len(locs) > 1:
            report["functions_present_elsewhere"].append({fn: locs})

    # Panels/class presence
    for panel in PANEL_CLASSES:
        locs = [p for p, cs in all_classes.items() if panel in cs]
        report["panel_presence"][panel] = locs
        for l in locs:
            report["panel_code_examples"][panel] = get_example(l, 12) if l else ""

    # API, state, view, core detection
    for root, _, files in os.walk(root_dir):
        for f in files:
            fp = os.path.join(root, f)
            if any(patt in fp for patt in API_PATTERNS):
                report["api_files"].append(fp)
            if any(patt in fp for patt in STATE_PATTERNS):
                report["state_files"].append(fp)
            if any(patt in fp for patt in VIEW_PATTERNS):
                report["view_files"].append(fp)
            if any(fp.endswith(p) for p in CORE_PATHS):
                report["core_files"].append(fp)

    # Shared components inspection
    comp_usage = find_component_usages(root_dir, SHARED_COMPONENTS)
    for c in SHARED_COMPONENTS:
        locations = []
        for sh_root in SHARED_PATHS:
            for root, _, files in os.walk(sh_root) if os.path.exists(sh_root) else []:
                for f in files:
                    if f.lower().startswith(c.lower()):
                        fp = os.path.join(root, f)
                        locations.append(fp)
                        report["shared_components"][c] = {
                            "example_code": get_example(fp, 10),
                            "used_in": comp_usage.get(c, [])
                        }

    # Generate markdown
    with open("migration_ULTRA_PLAN.md", "w", encoding="utf-8") as f:
        f.write("# Plan migration ULTIME — web_static\n\n")
        f.write("## ARBORESCENCE DU PROJET :\n")
        f.write(report["tree"])
        f.write("\n```\n\n")
        f.write("## FONCTIONS MÉTIER CRITIQUES et leur localisation\n")
        for fn, locs in report["critical_functions"].items():
            f.write(f"- {fn}: {', '.join(locs) if locs else 'Absent!'}\n")
        f.write("\n## PANELS présents et exemples de code/liste des panels\n")
        for pan, locs in report["panel_presence"].items():
            f.write(f"- {pan}: {', '.join(locs) if locs else 'ABSENT!'}\n")
            if pan in report["panel_code_examples"] and report["panel_code_examples"][pan]:
                f.write(f"\n``````\n")
        f.write("\n## FICHIERS API TROUVÉS :\n")
        for a in report["api_files"]:
            f.write(f"- {a}\n")
        f.write("\n## FICHIERS STATE TROUVÉS :\n")
        for s in report["state_files"]:
            f.write(f"- {s}\n")
        f.write("\n## FICHIERS VIEW TROUVÉS :\n")
        for v in report["view_files"]:
            f.write(f"- {v}\n")
        f.write("\n## CORE (Routing/Wiring) :\n")
        for c in report["core_files"]:
            f.write(f"- {c}\n")
        f.write("\n## COMPONENTS/SHARED EXAMPLES :\n")
        for c, info in report["shared_components"].items():
            f.write(f"### {c} :\n``````\nUtilisé dans: {', '.join(info.get('used_in',[]))}\n\n")
        f.write("\n## PROBLÈMES ET ACTIONS :\n")
        for a in report["actions_list"]:
            f.write(f"- {a['problem']} | {a['advice']}\n")
        f.write("\n## Fonctions dupliquées ou ailleurs:\n")
        for dup in report["functions_present_elsewhere"]:
            f.write(f"- {dup}\n")
        f.write("\n## CONSEILS FINALS MIGRATION ULTIME\n")
        for note in report["final_notes"]:
            f.write(f"- {note}\n")


    # JSON
    with open("migration_ULTRA_PLAN.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("✔ Plan exhaustif généré : migration_ULTRA_PLAN.md et .json")

if __name__ == "__main__":
    main()
