# -*- coding: utf-8 -*-

"""Constantes globales pour Home Suivi Élec."""

DOMAIN = "home_suivi_elec"

FICHIER_CAPTEURS = "custom_components/home_suivi_elec/data/capteurs_detectes.json"

# -----------------------------------------------------------------------------
# Champs ConfigFlow / Options (CANONIQUES = snake_case)
# -----------------------------------------------------------------------------

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_URL = "base_url"

CONF_TYPE_CONTRAT = "type_contrat"

CONF_PRIX_HT = "prix_ht"
CONF_PRIX_TTC = "prix_ttc"

CONF_PRIX_HT_HP = "prix_ht_hp"
CONF_PRIX_TTC_HP = "prix_ttc_hp"

CONF_PRIX_HT_HC = "prix_ht_hc"
CONF_PRIX_TTC_HC = "prix_ttc_hc"

CONF_ABONNEMENT_MENSUEL_HT = "abonnement_ht"
CONF_ABONNEMENT_MENSUEL_TTC = "abonnement_ttc"

CONF_HC_START = "hc_start"
CONF_HC_END = "hc_end"

CONF_AUTO_GENERATE = "auto_generate_lovelace"

# Options additionnelles (elles existent chez toi en camelCase aujourd’hui,
# mais on veut du snake_case pur en canon)
CONF_IGNORED_ENTITIES = "ignored_entities"
CONF_USE_EXTERNAL = "use_external"
CONF_EXTERNAL_CAPTEUR = "external_capteur"
CONF_CONSOMMATION_EXTERNE = "consommation_externe"
CONF_ENABLE_COST_SENSORS_RUNTIME = "enable_cost_sensors_runtime"

# -----------------------------------------------------------------------------
# Alias de NOMS (compat code legacy)
# -> Ces alias pointent volontairement vers les clés CANONIQUES (snake_case).
# -----------------------------------------------------------------------------

CONFNAME = CONF_NAME
CONFMODE = CONF_MODE
CONFURL = CONF_URL
CONFTYPECONTRAT = CONF_TYPE_CONTRAT

CONFPRIXHT = CONF_PRIX_HT
CONFPRIXTTC = CONF_PRIX_TTC
CONFPRIXHTHP = CONF_PRIX_HT_HP
CONFPRIXTTCHP = CONF_PRIX_TTC_HP
CONFPRIXHTHC = CONF_PRIX_HT_HC
CONFPRIXTTCHC = CONF_PRIX_TTC_HC

CONFABONNEMENTMENSUELHT = CONF_ABONNEMENT_MENSUEL_HT
CONFABONNEMENTMENSUELTTC = CONF_ABONNEMENT_MENSUEL_TTC

CONFHCSTART = CONF_HC_START
CONFHCEND = CONF_HC_END

CONFAUTOGENERATE = CONF_AUTO_GENERATE


# -----------------------------------------------------------------------------
# Mapping des alias de clés (legacy/camelCase/anciens formats) -> CANON snake_case
# -----------------------------------------------------------------------------
KEY_ALIASES_TO_CANONICAL = {
    # --- snake_case (déjà canon) : pas nécessaire, mais inoffensif si tu veux les garder ---
    # "abonnement_ht": CONF_ABONNEMENT_MENSUEL_HT,
    # "abonnement_ttc": CONF_ABONNEMENT_MENSUEL_TTC,
    # "type_contrat": CONF_TYPE_CONTRAT,
    # "use_external": CONF_USE_EXTERNAL,
    # "external_capteur": CONF_EXTERNAL_CAPTEUR,
    # "consommation_externe": CONF_CONSOMMATION_EXTERNE,
    # "enable_cost_sensors_runtime": CONF_ENABLE_COST_SENSORS_RUNTIME,

    # --- camelCase observé (audit) ---
    "typeContrat": CONF_TYPE_CONTRAT,
    "useExternal": CONF_USE_EXTERNAL,
    "externalCapteur": CONF_EXTERNAL_CAPTEUR,
    "consommationExterne": CONF_CONSOMMATION_EXTERNE,
    "abonnementHT": CONF_ABONNEMENT_MENSUEL_HT,
    "abonnementTTC": CONF_ABONNEMENT_MENSUEL_TTC,
    "enableCostSensorsRuntime": CONF_ENABLE_COST_SENSORS_RUNTIME,

    # --- v1 "compact" (sans underscore) ---
    "typecontrat": CONF_TYPE_CONTRAT,
    "prixht": CONF_PRIX_HT,
    "prixttc": CONF_PRIX_TTC,
    "prixhthp": CONF_PRIX_HT_HP,
    "prixttchp": CONF_PRIX_TTC_HP,
    "prixhthc": CONF_PRIX_HT_HC,
    "prixttchc": CONF_PRIX_TTC_HC,
    "abonnementht": CONF_ABONNEMENT_MENSUEL_HT,
    "abonnementttc": CONF_ABONNEMENT_MENSUEL_TTC,
    "hcstart": CONF_HC_START,
    "hcend": CONF_HC_END,
    "autogeneratelovelace": CONF_AUTO_GENERATE,

    # --- autres variantes possibles ---
    "baseurl": CONF_URL,
}

# -----------------------------------------------------------------------------
# Contrats / Valeurs par défaut
# -----------------------------------------------------------------------------

CONTRATS = {
    "prix_unique": "Tarif unique",
    "heures_creuses": "Heures Pleines / Creuses",
}

DEFAULTS = {
    "prix_unique": {
        CONF_PRIX_HT: 0.1327,
        CONF_PRIX_TTC: 0.1952,
        CONF_ABONNEMENT_MENSUEL_HT: 13.7900,
        CONF_ABONNEMENT_MENSUEL_TTC: 19.7910,
    },
    "heures_creuses": {
        CONF_PRIX_HT_HP: 0.1327,
        CONF_PRIX_TTC_HP: 0.1952,
        CONF_PRIX_HT_HC: 0.1327,
        CONF_PRIX_TTC_HC: 0.1952,
        CONF_ABONNEMENT_MENSUEL_HT: 13.7900,
        CONF_ABONNEMENT_MENSUEL_TTC: 19.7910,
        CONF_HC_START: "22:00",
        CONF_HC_END: "06:00",
    },
}

# -----------------------------------------------------------------------------
# ===== PHASE 2: PATTERNS HSE CENTRALISÉS =====
# -----------------------------------------------------------------------------

# Cycles supportés (noms complets Phase 2)
HSE_CYCLES = ["hourly", "daily", "weekly", "monthly", "yearly"]
HSE_CYCLE_SUFFIXES = [f"_{cycle}" for cycle in HSE_CYCLES]

# Patterns de détection HSE energy sensors
HSE_SENSOR_PREFIX = "sensor.hse_"
HSE_ENERGY_SENSOR_PREFIX = "sensor.hse_energy_"


def build_hse_sensor_id(base_name: str, cycle: str, source_entity_id: str) -> str:
    """Construit ID HSE selon conventions Phase 2.

    Args:
        base_name: Nom de base (ex: chambre_tv_prise_connectee_today_energy)
        cycle: Cycle complet (hourly, daily, weekly, monthly, yearly)
        source_entity_id: ID capteur source pour détecter le type

    Returns:
        sensor.hse_{base_name}_{cycle} pour today_energy sources
        sensor.hse_energy_{base_name}_{cycle} pour autres sources energy
    """
    if cycle not in HSE_CYCLES:
        raise ValueError(f"Cycle invalide: {cycle}. Cycles supportés: {HSE_CYCLES}")

    if "today_energy" in source_entity_id:
        return f"sensor.hse_{base_name}_{cycle}"
    return f"sensor.hse_energy_{base_name}_{cycle}"


def extract_cycle_from_hse_id(entity_id: str) -> str:
    """Extrait cycle depuis ID HSE (Phase 2)."""
    for cycle in HSE_CYCLES:
        if entity_id.endswith(f"_{cycle}"):
            return cycle
    return "unknown"


def is_hse_sensor(entity_id: str) -> bool:
    """Détermine si entity_id est un capteur HSE energy."""
    if not entity_id.startswith((HSE_SENSOR_PREFIX, HSE_ENERGY_SENSOR_PREFIX)):
        return False
    return entity_id.endswith(tuple(HSE_CYCLE_SUFFIXES))


# Events HSE
HSE_EVENT_SENSORS_READY = "hse_energy_sensors_ready"

# -----------------------------------------------------------------------------
# ===== STORAGE API - PHASE 2.7 =====
# -----------------------------------------------------------------------------

STORAGE_VERSION = 2

STORE_USER_CONFIG = "home_suivi_elec_user_config_v2"
STORE_CAPTEURS_SELECTION = "home_suivi_elec_capteurs_selection_v2"
STORE_IGNORED_ENTITIES = "home_suivi_elec_ignored_entities_v1"
STORE_SENSOR_GROUPS = "home_suivi_elec_sensor_groups_v1"

# ✅ Nouveau store canon : group_sets (rooms/types/...) + version dédiée
GROUP_SETS_STORAGE_VERSION = 1
STORE_GROUP_SETS = "home_suivi_elec_group_sets_v1"

HSE_EVENT_STORAGE_MIGRATED = "hse_storage_migrated"
CAPTEURS_POWER_STORAGE_VERSION = 1
STORE_CAPTEURS_POWER = "home_suivi_elec_capteurs_power_v1"
