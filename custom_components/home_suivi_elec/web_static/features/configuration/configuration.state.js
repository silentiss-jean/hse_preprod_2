// js/configuration.state.js — Gestion état configuration complète

console.info("[config.state] module chargé");

const FOLD_KEY = "hse_fold_v1";

// ==================== FOLDS ====================

function readStore() {
    try {
        const raw = localStorage.getItem(FOLD_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch (e) {
        console.warn("[config.state] readStore error:", e);
        return {};
    }
}

function writeStore(obj) {
    try {
        localStorage.setItem(FOLD_KEY, JSON.stringify(obj || {}));
    } catch (e) {
        console.warn("[config.state] writeStore error:", e);
    }
}

export function getFold(integration, columnName) {
    const store = readStore();
    const col = store[columnName] || {};
    return col[integration] === true;
}

export function setFold(integration, columnName, isOpen) {
    const store = readStore();
    store[columnName] ??= {};
    store[columnName][integration] = !!isOpen;
    writeStore(store);
    console.debug("[config.state] setFold:", columnName, integration, !!isOpen);
}

// ==================== NORMALISATION ====================

/**
 * Convention canonique:
 * - "prix_unique"
 * - "heures_creuses"
 */
function normalizeTypeContrat(v) {
    const s = (v ?? "").toString().trim().toLowerCase();
    if (s === "heures_creuses" || s === "hp-hc" || s === "hphc" || s === "heurescreuses") return "heures_creuses";
    if (s === "prix_unique" || s === "fixe" || s === "prixunique") return "prix_unique";
    return s || "prix_unique";
}

// ==================== COMPOSITION CONFIG ====================

/**
 * Compose la configuration tarifaire à partir de options (priorité) et data (fallback).
 * On reste en snake_case + valeurs canonisées.
 *
 * @param {Object} options - Options persistées dans HA (config_entries.options)
 * @param {Object} data - Data initiale (config_entries.data)
 * @returns {Object} Configuration fusionnée
 */
export function composeConfig(options = {}, data = {}) {
    console.info("[config.state] composeConfig - options:", options, "data:", data);

    // Support rétro-compat si jamais un vieux payload traîne (camelCase ou alias)
    const rawType =
        options.type_contrat ??
        options.typeContrat ??
        data.type_contrat ??
        data.typeContrat ??
        "prix_unique";

    const type_contrat = normalizeTypeContrat(rawType);

    const num = (v) => {
        const n = parseFloat(v);
        return Number.isFinite(n) ? n : 0;
    };

    // ✅ Récupération de tous les champs, quel que soit le type de contrat
    const config = {
        type_contrat,

        // Abonnement
        abonnement_ht: num(
            options.abonnement_ht ??
            options.abonnement_mensuel_ht ??
            data.abonnement_ht ??
            data.abonnement_mensuel_ht ??
            0
        ),
        abonnement_ttc: num(
            options.abonnement_ttc ??
            options.abonnement_mensuel_ttc ??
            data.abonnement_ttc ??
            data.abonnement_mensuel_ttc ??
            0
        ),

        // Prix unique
        prix_ht: num(options.prix_ht ?? data.prix_ht ?? 0),
        prix_ttc: num(options.prix_ttc ?? data.prix_ttc ?? 0),

        // HP/HC
        prix_ht_hp: num(options.prix_ht_hp ?? data.prix_ht_hp ?? 0),
        prix_ttc_hp: num(options.prix_ttc_hp ?? data.prix_ttc_hp ?? 0),
        prix_ht_hc: num(options.prix_ht_hc ?? data.prix_ht_hc ?? 0),
        prix_ttc_hc: num(options.prix_ttc_hc ?? data.prix_ttc_hc ?? 0),

        hc_start: (options.hc_start ?? data.hc_start ?? "22:00").toString(),
        hc_end: (options.hc_end ?? data.hc_end ?? "06:00").toString(),
    };

    console.info("[config.state] Configuration composée:", config);
    return config;
}

// ==================== BINDING BOUTONS ====================

export function bindUserOptions(onSave) {
    console.info("[config.state] bindUserOptions");
    bindSaveUserConfig(onSave);
//    bindSaveSelection(onSave);
    // Le toggle visuel est déjà géré par userConfigPanel.
    // bindTypeContratToggle();
}

function bindSaveUserConfig(onSave) {
    const oldBtn = document.getElementById("saveUserConfig");
    if (oldBtn) {
        const newBtn = oldBtn.cloneNode(true);
        oldBtn.parentNode.replaceChild(newBtn, oldBtn);
    }

    const btn = document.getElementById("saveUserConfig");
    if (btn) {
        btn.addEventListener("click", async (ev) => {
            ev?.preventDefault?.();

            const type_contrat = normalizeTypeContrat(
                document.getElementById("type_contrat")?.value || "prix_unique"
            );

            const payload = {
                abonnement_ht: parseFloat(document.getElementById("abonnement_ht")?.value) || 0,
                abonnement_ttc: parseFloat(document.getElementById("abonnement_ttc")?.value) || 0,
                type_contrat,
                enable_cost_sensors_runtime: !!document.getElementById("enable_cost_sensors_runtime")?.checked,
            };

            if (type_contrat === "prix_unique") {
                payload.prix_ht = parseFloat(document.getElementById("tarifFixeHT")?.value) || 0;
                payload.prix_ttc = parseFloat(document.getElementById("tarifFixeTTC")?.value) || 0;
            } else {
                payload.prix_ht_hp = parseFloat(document.getElementById("tarifHPHT")?.value) || 0;
                payload.prix_ttc_hp = parseFloat(document.getElementById("tarifHPTTC")?.value) || 0;
                payload.prix_ht_hc = parseFloat(document.getElementById("tarifHCHT")?.value) || 0;
                payload.prix_ttc_hc = parseFloat(document.getElementById("tarifHCTTC")?.value) || 0;
                payload.hc_start = document.getElementById("heuresHPDebut")?.value || "22:00";
                payload.hc_end = document.getElementById("heuresHPFin")?.value || "06:00";
            }

            console.log("[config.state] Payload configuration:", payload);

            if (typeof onSave === "function") {
                try {
                    await onSave(payload); // ← Sauvegarde + rechargement
                    alert("✅ Configuration tarifaire sauvegardée !");
                } catch (error) {
                    console.error("[config.state] Erreur sauvegarde:", error);
                    alert("❌ Erreur lors de la sauvegarde");
                }
            }
        });
    }
}

function bindSaveSelection(onSave) {
    const oldBtn = document.getElementById("saveSelection");
    if (oldBtn) {
        const newBtn = oldBtn.cloneNode(true);
        oldBtn.parentNode.replaceChild(newBtn, oldBtn);
    }

    const btn = document.getElementById("saveSelection");
    if (btn) {
        btn.addEventListener("click", async (ev) => {
            ev?.preventDefault?.();

            const type_contrat = normalizeTypeContrat(
                document.getElementById("type_contrat")?.value || "prix_unique"
            );

            const payload = {
                abonnement_ht: parseFloat(document.getElementById("abonnement_ht")?.value) || 0,
                abonnement_ttc: parseFloat(document.getElementById("abonnement_ttc")?.value) || 0,
                type_contrat,
            };

            if (type_contrat === "prix_unique") {
                payload.prix_ht = parseFloat(document.getElementById("tarifFixeHT")?.value) || 0;
                payload.prix_ttc = parseFloat(document.getElementById("tarifFixeTTC")?.value) || 0;
            } else {
                payload.prix_ht_hp = parseFloat(document.getElementById("tarifHPHT")?.value) || 0;
                payload.prix_ttc_hp = parseFloat(document.getElementById("tarifHPTTC")?.value) || 0;
                payload.prix_ht_hc = parseFloat(document.getElementById("tarifHCHT")?.value) || 0;
                payload.prix_ttc_hc = parseFloat(document.getElementById("tarifHCTTC")?.value) || 0;
                payload.hc_start = document.getElementById("heuresHPDebut")?.value || "22:00";
                payload.hc_end = document.getElementById("heuresHPFin")?.value || "06:00";
            }

            console.log("[config.state] Payload sauvegarde sélection:", payload);
            if (typeof onSave === "function") {
                await onSave(payload);
            }
        });
    }
}
