import requests
import re
import json
import yaml
import os

def fetch_integrations():
    url = "https://www.home-assistant.io/integrations/"
    resp = requests.get(url)
    text = resp.text

    # Recherche le bloc 'const integrations = [...]'
    match = re.search(r'const integrations = (\[.*?\]);', text, re.DOTALL)
    if not match:
        raise Exception("Bloc 'integrations' non trouvé dans la page source !")
    
    integration_json_str = match.group(1)
    integration_json_str = re.sub(r",\s*]", "]", integration_json_str)
    integration_json_str = re.sub(r",\s*}", "}", integration_json_str)
    
    # Correction : la liste JS est un pseudo-JSON
    try:
        integrations = json.loads(integration_json_str)
    except Exception as e:
        # En cas d'erreur, donne une idée de la cause
        raise Exception(f"Erreur lors du chargement JSON : {str(e)}")

    # Construction du mapping qualité
    quality_map = {}
    for integ in integrations:
        domain = integ.get("domain", "")
        quality = integ.get("quality_scale", "")
        if domain and quality:
            quality_map[domain] = quality

    # Sauvegarde du mapping dans /data/
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    map_file = os.path.join(data_dir, "integration_quality.yaml")
    with open(map_file, "w", encoding="utf-8") as f:
        yaml.dump(quality_map, f, allow_unicode=True, default_flow_style=False)

    print(f"Mapping qualité exporté dans : {map_file}")
    print(f"{len(quality_map)} intégrations référencées.")

if __name__ == "__main__":
    fetch_integrations()
