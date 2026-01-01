# -*- coding: utf-8 -*-
"""Configuration et enregistrement du panneau statique Home Suivi Élec."""
import logging
import os
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

_LOGGER = logging.getLogger(__name__)

async def async_setup_panel(hass: HomeAssistant):
    """Setup du panneau /home_suivi_elec."""

    # Dossier de ton panneau statique
    panel_dir = os.path.join(
        hass.config.path("custom_components", "home_suivi_elec", "panel_static")
    )
    os.makedirs(panel_dir, exist_ok=True)

    panel_js = os.path.join(panel_dir, "panel.js")
    panel_html = os.path.join(panel_dir, "panel.html")

    if not os.path.exists(panel_js):
        _LOGGER.warning("[PANEL] Fichier panel.js introuvable : %s", panel_js)
        return

    # Crée panel.html automatiquement si inexistant
    if not os.path.exists(panel_html):
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Home Suivi Élec</title>
  <script type="module" src="/home_suivi_elec/panel.js"></script>
</head>
<body>
  <home-suivi-elec-panel></home-suivi-elec-panel>
</body>
</html>"""
        with open(panel_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        _LOGGER.info("[PANEL] panel.html créé automatiquement")

    # Enregistre le répertoire comme ressource statique
    hass.http.async_register_static_paths([
        frontend.StaticPathConfig("/home_suivi_elec", panel_dir)
    ])

    # Ajoute le panneau à la barre latérale si pas déjà fait
    if not hass.data.get("home_suivi_elec_panel_registered"):
        frontend.async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="Suivi Élec",
            sidebar_icon="mdi:flash",
            config={"url": "/home_suivi_elec/panel.html"},  # <-- URL HTML
            require_admin=True
        )
        hass.data["home_suivi_elec_panel_registered"] = True
        _LOGGER.info("[PANEL] ✅ Panneau Home Suivi Élec ajouté à la barre latérale")
    else:
        _LOGGER.debug("[PANEL] ⚙️ Panneau déjà enregistré, aucune action")