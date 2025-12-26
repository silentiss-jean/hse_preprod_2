from homeassistant import config_entries, core
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.core import callback

from .const import (
    DOMAIN, CONTRATS, DEFAULTS,
    CONF_NAME, CONF_TYPE_CONTRAT, CONF_AUTO_GENERATE,
    CONF_PRIX_HT, CONF_PRIX_TTC,
    CONF_PRIX_HT_HP, CONF_PRIX_TTC_HP,
    CONF_PRIX_HT_HC, CONF_PRIX_TTC_HC,
    CONF_HC_START, CONF_HC_END,
    CONF_ABONNEMENT_MENSUEL_HT, CONF_ABONNEMENT_MENSUEL_TTC
)

from .options_flow import HomeSuiviElecOptionsFlow

def _normalize_type_contrat(value: str | None) -> str:
    """Normalise type_contrat vers valeurs canon: prix_unique | heures_creuses."""
    v = (value or "").strip().lower()
    if v in ("hp-hc", "hphc", "heurescreuses", "heures_creuses"):
        return "heures_creuses"
    if v in ("fixe", "prixunique", "prix_unique"):
        return "prix_unique"
    # fallback safe
    return v or "prix_unique"

class HomeSuiviElecFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pour Home Suivi Élec avec nom du hub et tarifs."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Formulaire principal pour nom, type de contrat et option auto_generate."""
        if user_input is not None:
            self._user_data = user_input
            
            # Normaliser le type_contrat (robustesse / rétro-compat)
            self._user_data[CONF_TYPE_CONTRAT] = _normalize_type_contrat(
                self._user_data.get(CONF_TYPE_CONTRAT)
            )
            
            # Vérifier doublons
            for entry in self._async_current_entries():
                if entry.data.get(CONF_NAME) == self._user_data[CONF_NAME]:
                    return self.async_abort(reason="hub_exists")
            
            return await self.async_step_tarifs()

        schema = vol.Schema({
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_TYPE_CONTRAT, default="prix_unique"): vol.In(CONTRATS.keys()),
            vol.Optional(CONF_AUTO_GENERATE, default=True): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_tarifs(self, user_input=None):
        """Formulaire des tarifs selon le type de contrat choisi."""
        if user_input is not None:
            self._user_data.update(user_input)
            return self.async_create_entry(title=self._user_data[CONF_NAME], data=self._user_data)

        contrat = _normalize_type_contrat(
            getattr(self, "_user_data", {}).get(CONF_TYPE_CONTRAT, "prix_unique")
        )

        if contrat == "prix_unique":
            schema = vol.Schema({
                vol.Optional(CONF_PRIX_HT, default=DEFAULTS["prix_unique"][CONF_PRIX_HT]): cv.positive_float,
                vol.Optional(CONF_PRIX_TTC, default=DEFAULTS["prix_unique"][CONF_PRIX_TTC]): cv.positive_float,
                vol.Optional(CONF_ABONNEMENT_MENSUEL_HT, default=DEFAULTS["prix_unique"][CONF_ABONNEMENT_MENSUEL_HT]): cv.positive_float,
                vol.Optional(CONF_ABONNEMENT_MENSUEL_TTC, default=DEFAULTS["prix_unique"][CONF_ABONNEMENT_MENSUEL_TTC]): cv.positive_float,
            })
        else:
            schema = vol.Schema({
                vol.Optional(CONF_PRIX_HT_HP, default=DEFAULTS["heures_creuses"][CONF_PRIX_HT_HP]): cv.positive_float,
                vol.Optional(CONF_PRIX_TTC_HP, default=DEFAULTS["heures_creuses"][CONF_PRIX_TTC_HP]): cv.positive_float,
                vol.Optional(CONF_PRIX_HT_HC, default=DEFAULTS["heures_creuses"][CONF_PRIX_HT_HC]): cv.positive_float,
                vol.Optional(CONF_PRIX_TTC_HC, default=DEFAULTS["heures_creuses"][CONF_PRIX_TTC_HC]): cv.positive_float,
                vol.Optional(CONF_HC_START, default=DEFAULTS["heures_creuses"][CONF_HC_START]): cv.string,
                vol.Optional(CONF_HC_END, default=DEFAULTS["heures_creuses"][CONF_HC_END]): cv.string,
                vol.Optional(CONF_ABONNEMENT_MENSUEL_HT, default=DEFAULTS["heures_creuses"][CONF_ABONNEMENT_MENSUEL_HT]): cv.positive_float,
                vol.Optional(CONF_ABONNEMENT_MENSUEL_TTC, default=DEFAULTS["heures_creuses"][CONF_ABONNEMENT_MENSUEL_TTC]): cv.positive_float,
            })

        return self.async_show_form(step_id="tarifs", data_schema=schema)

    # --- Liaison OptionsFlow pour la roue crantée
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Retourne l'OptionsFlow associé à cette ConfigEntry."""
        # ✅ CORRECTION : Ne pas passer config_entry en argument
        return HomeSuiviElecOptionsFlow()
