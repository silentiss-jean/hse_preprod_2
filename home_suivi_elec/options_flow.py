from homeassistant import config_entries
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
import logging

from .const import (
    DOMAIN, 
    CONF_NAME, CONF_TYPE_CONTRAT, CONF_AUTO_GENERATE,
    CONF_PRIX_HT, CONF_PRIX_TTC,
    CONF_PRIX_HT_HP, CONF_PRIX_TTC_HP,
    CONF_PRIX_HT_HC, CONF_PRIX_TTC_HC,
    CONF_HC_START, CONF_HC_END,
    CONF_ABONNEMENT_MENSUEL_HT, CONF_ABONNEMENT_MENSUEL_TTC
)

_LOGGER = logging.getLogger(__name__)

# ✅ Fallback robuste si CONTRATS ou DEFAULTS ne sont pas définis dans const.py
try:
    from .const import CONTRATS, DEFAULTS
except ImportError:
    _LOGGER.warning("CONTRATS ou DEFAULTS non trouvés dans const.py, utilisation de valeurs par défaut")
    CONTRATS = {
        "prix_unique": "Tarif unique",
        "heures_creuses": "Heures Pleines / Heures Creuses"
    }
    DEFAULTS = {
        "prix_unique": {
            CONF_PRIX_HT: 0.2062,
            CONF_PRIX_TTC: 0.2516,
            CONF_ABONNEMENT_MENSUEL_HT: 11.47,
            CONF_ABONNEMENT_MENSUEL_TTC: 13.99
        },
        "heures_creuses": {
            CONF_PRIX_HT_HP: 0.27,
            CONF_PRIX_TTC_HP: 0.2769,
            CONF_PRIX_HT_HC: 0.2068,
            CONF_PRIX_TTC_HC: 0.2120,
            CONF_HC_START: "22:00",
            CONF_HC_END: "06:00",
            CONF_ABONNEMENT_MENSUEL_HT: 12.44,
            CONF_ABONNEMENT_MENSUEL_TTC: 15.17
        }
    }

def _as_float(data, key, fallback):
    """Conversion robuste en float avec fallback."""
    try:
        return float(data.get(key, fallback))
    except (TypeError, ValueError, AttributeError):
        return fallback

def _normalize_type_contrat(value: str | None) -> str:
    """Normalise type_contrat vers valeurs canon: prix_unique | heures_creuses."""
    v = (value or "").strip().lower()
    if v in ("hp-hc", "hphc", "heurescreuses", "heures_creuses"):
        return "heures_creuses"
    if v in ("fixe", "prixunique", "prix_unique"):
        return "prix_unique"
    return v or "prix_unique"

class HomeSuiviElecOptionsFlow(config_entries.OptionsFlowWithReload):
    """Options flow pour Home Suivi Élec.
    
    Important:
    - On merge avec les options existantes pour ne pas supprimer des clés
    non affichées dans le formulaire (ex: use_external, external_capteur, etc.).
    """

    # ❌ NE PAS REDÉFINIR __init__() - La classe parente fournit déjà self.config_entry
    # def __init__(self, config_entry: config_entries.ConfigEntry):
    #     self.config_entry = config_entry  # ← ERREUR : config_entry est une property en lecture seule

    async def async_step_init(self, user_input=None):
        """Afficher tous les champs avec valeurs par défaut."""
        
        # ✅ Protection anti-crash
        try:
            if user_input is not None:
                # Merge pour ne pas perdre les champs hors UI (référence, etc.)
                merged = dict(self.config_entry.options or {})
                merged.update(user_input)
                
                # Normaliser type_contrat
                merged[CONF_TYPE_CONTRAT] = _normalize_type_contrat(merged.get(CONF_TYPE_CONTRAT))
                
                return self.async_create_entry(title="", data=merged)

            # Valeurs effectives: options prioritaire sur data (utile si options encore vides)
            effective = dict(self.config_entry.data or {})
            effective.update(self.config_entry.options or {})

            # Type de contrat courant (canon)
            type_contrat = _normalize_type_contrat(effective.get(CONF_TYPE_CONTRAT, "prix_unique"))

            defaults_unique = DEFAULTS.get("prix_unique", {})
            defaults_hc = DEFAULTS.get("heures_creuses", {})

            # Abonnement: selon contrat (fallback cohérent)
            default_ab_ht = (
                defaults_hc.get(CONF_ABONNEMENT_MENSUEL_HT, 12.44)
                if type_contrat == "heures_creuses"
                else defaults_unique.get(CONF_ABONNEMENT_MENSUEL_HT, 11.47)
            )

            default_ab_ttc = (
                defaults_hc.get(CONF_ABONNEMENT_MENSUEL_TTC, 15.17)
                if type_contrat == "heures_creuses"
                else defaults_unique.get(CONF_ABONNEMENT_MENSUEL_TTC, 13.99)
            )

            schema = vol.Schema({
                # NB: changer CONF_NAME ici n'update pas le title de la config_entry automatiquement.
                vol.Optional(CONF_NAME, default=effective.get(CONF_NAME, self.config_entry.title or "Home Suivi Élec")): str,
                vol.Optional(CONF_TYPE_CONTRAT, default=type_contrat): vol.In(CONTRATS.keys()),
                vol.Optional(CONF_AUTO_GENERATE, default=effective.get(CONF_AUTO_GENERATE, True)): bool,

                # Champs communs (abonnement)
                vol.Optional(
                    CONF_ABONNEMENT_MENSUEL_HT,
                    default=_as_float(effective, CONF_ABONNEMENT_MENSUEL_HT, default_ab_ht),
                ): cv.positive_float,
                vol.Optional(
                    CONF_ABONNEMENT_MENSUEL_TTC,
                    default=_as_float(effective, CONF_ABONNEMENT_MENSUEL_TTC, default_ab_ttc),
                ): cv.positive_float,

                # Tarif unique (prix_unique)
                vol.Optional(
                    CONF_PRIX_HT,
                    default=_as_float(effective, CONF_PRIX_HT, defaults_unique.get(CONF_PRIX_HT, 0.2062)),
                ): cv.positive_float,
                vol.Optional(
                    CONF_PRIX_TTC,
                    default=_as_float(effective, CONF_PRIX_TTC, defaults_unique.get(CONF_PRIX_TTC, 0.2516)),
                ): cv.positive_float,

                # Heures Pleines / Creuses (heures_creuses)
                vol.Optional(
                    CONF_PRIX_HT_HP,
                    default=_as_float(effective, CONF_PRIX_HT_HP, defaults_hc.get(CONF_PRIX_HT_HP, 0.27)),
                ): cv.positive_float,
                vol.Optional(
                    CONF_PRIX_TTC_HP,
                    default=_as_float(effective, CONF_PRIX_TTC_HP, defaults_hc.get(CONF_PRIX_TTC_HP, 0.2769)),
                ): cv.positive_float,
                vol.Optional(
                    CONF_PRIX_HT_HC,
                    default=_as_float(effective, CONF_PRIX_HT_HC, defaults_hc.get(CONF_PRIX_HT_HC, 0.2068)),
                ): cv.positive_float,
                vol.Optional(
                    CONF_PRIX_TTC_HC,
                    default=_as_float(effective, CONF_PRIX_TTC_HC, defaults_hc.get(CONF_PRIX_TTC_HC, 0.2120)),
                ): cv.positive_float,
                vol.Optional(
                    CONF_HC_START,
                    default=effective.get(CONF_HC_START, defaults_hc.get(CONF_HC_START, "22:00")),
                ): cv.string,
                vol.Optional(
                    CONF_HC_END,
                    default=effective.get(CONF_HC_END, defaults_hc.get(CONF_HC_END, "06:00")),
                ): cv.string,
            })

            return self.async_show_form(step_id="init", data_schema=schema)
            
        except Exception as e:
            _LOGGER.exception("❌ Erreur dans options_flow.async_step_init: %s", e)
            # Retourner un formulaire minimal en cas d'erreur
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({
                    vol.Optional(CONF_NAME, default="Home Suivi Élec"): str,
                })
            )
