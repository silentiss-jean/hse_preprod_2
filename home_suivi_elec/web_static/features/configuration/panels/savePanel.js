// savePanel.js — Sauvegarde globale indépendante (hors capteur de référence)
"use strict";

import { saveSelection, saveUserOptions } from "./configuration.api.js";
import { emit } from "../../../shared/eventBus.js";
import { toast } from "../../../shared/uiToast.js";

/**
 * Initialise le panneau de sauvegarde globale.
 * - Gère le bouton #saveSelection
 * - Gère l’affichage dynamique heures_creuses via #type_contrat
 * - N’affecte jamais la référence (capteur externe) gérée par referencePanel.js
 *
 * Convention:
 * - type_contrat: "prix_unique" | "heures_creuses"
 */
export function initSavePanel(root = document) {
  const btnSave = root.getElementById("saveSelection");
  const typeSel = root.getElementById("type_contrat");

  // Compat: ancien conteneur (hpHCFields) vs nouveau (tarifHPHCSection)
  const hcFields =
    root.getElementById("tarifHPHCSection") || root.getElementById("hpHCFields");

  // Affichage dynamique heures_creuses
  if (typeSel && hcFields) {
    const syncHeuresCreuses = () => {
      hcFields.style.display = typeSel.value === "heures_creuses" ? "block" : "none";
    };
    syncHeuresCreuses();
    typeSel.onchange = syncHeuresCreuses;
  }

  if (!btnSave) return;

  btnSave.addEventListener("click", async (ev) => {
    if (ev && typeof ev.preventDefault === "function") ev.preventDefault();

    // Sélections capteurs
    const selections = {};
    document
      .querySelectorAll("#content-configuration input[type='checkbox'].capteur-checkbox")
      .forEach((cb) => {
        const integ = cb.dataset.integration || "unknown";
        const eid = cb.dataset.entity;
        if (!eid) return;
        selections[integ] ??= [];
        selections[integ].push({ entity_id: eid, enabled: cb.checked });
      });

    // Options utilisateur (hors référence)
    const getVal = (id) => (document.getElementById(id)?.value ?? "").toString().trim();
    const toNum = (v) => {
      const n = parseFloat(v);
      return Number.isFinite(n) ? n : 0;
    };

    const type_contrat = getVal("type_contrat") || "prix_unique";

    // Lire les champs UI (nouveaux ids du userConfigPanel)
    const userDataUI = {
      type_contrat,
      abonnement_ht: toNum(getVal("abonnement_ht")),
      abonnement_ttc: toNum(getVal("abonnement_ttc")),

      // Prix unique
      prix_ht: toNum(getVal("tarifFixeHT")),
      prix_ttc: toNum(getVal("tarifFixeTTC")),

      // HP/HC
      prix_ht_hp: toNum(getVal("tarifHPHT")),
      prix_ttc_hp: toNum(getVal("tarifHPTTC")),
      prix_ht_hc: toNum(getVal("tarifHCHT")),
      prix_ttc_hc: toNum(getVal("tarifHCTTC")),
      hc_start: getVal("heuresHPDebut") || "22:00",
      hc_end: getVal("heuresHPFin") || "06:00",
      // La référence est gérée par referencePanel.js et ne doit pas être perdue
    };

    // Contrôle local “même appareil” minimal (tolère 1 power + 1 energy)
    try {
      const byDevice = new Map();
      document
        .querySelectorAll("#content-configuration input.capteur-checkbox:checked")
        .forEach((cb) => {
          const eid = cb.dataset.entity;
          const cap = window.__ALL_CAPTEURS__?.[eid]; // optionnel
          const did = cap?.device_id;
          if (!did) return;
          if (!byDevice.has(did)) byDevice.set(did, []);
          byDevice.get(did).push(eid);
        });

      const bad = [];

      byDevice.forEach((arr, did) => {
        if (arr.length <= 1) return;

        const types = arr.map((eid) => {
          const cap = window.__ALL_CAPTEURS__?.[eid] || {};
          let t = (cap.source_type || cap.type || "").toLowerCase();

          // Normalisation energy-like
          if (
            ["energydirect", "energy_direct", "energyutility", "energy_utility", "hseenergy", "hse_energy", "energy"]
              .includes(t.replace("-", "_"))
          ) {
            t = "energy";
          }

          // Normalisation power
          if (["power", "puissance"].includes(t)) t = "power";
          return t;
        });

        const typeSet = new Set(types);

        // Cas autorisé : exactement 2 entités, 1 power + 1 energy
        if (arr.length === 2 && typeSet.size === 2 && typeSet.has("power") && typeSet.has("energy")) {
          return;
        }

        bad.push({ device_id: did, entities: arr });
      });

      if (bad.length) {
        console.log("LOCAL BAD DEVICES", bad);
        alert(
          "Conflit: plusieurs mesures pour le même appareil:\n" +
            bad.map((b) => `- ${b.device_id}: ${b.entities.join(", ")}`).join("\n")
        );
        return;
      }
    } catch {
      // ignore si __ALL_CAPTEURS__ non défini
    }

    try {
      // 1) Sauvegarde de la sélection capteurs
      const selJson = await saveSelection(selections);
      if (selJson && selJson.success === false) {
        const conflicts = selJson?.conflicts || [];
        const msg = conflicts.length
          ? "Doublons détectés:\n" +
            conflicts
              .map(
                (c) =>
                  `- ${c.friendly_name} (${c.entity_id}) [${c.integration}] - zone: ${c.area}`
              )
              .join("\n")
          : selJson?.error || "Erreur de sauvegarde";
        alert(msg);
        toast.warning("Conflits détectés, vérifie la sélection");
        return;
      }

      // 2) Merge côté front pour ne pas effacer la référence
      const current = await fetch("/api/home_suivi_elec/get_user_options").then((r) =>
        r.ok ? r.json() : {}
      );

      // 3) Construire payload snake_case only (on écrase uniquement les champs UI gérés ici)
      const merged = {
        ...current,

        // Champs communs
        abonnement_ht: userDataUI.abonnement_ht,
        abonnement_ttc: userDataUI.abonnement_ttc,
        type_contrat: userDataUI.type_contrat,
      };

      if (userDataUI.type_contrat === "prix_unique") {
        merged.prix_ht = userDataUI.prix_ht;
        merged.prix_ttc = userDataUI.prix_ttc;

        // Optionnel: ne pas polluer avec hp/hc si tu veux garder l'ancien dernier état, mais ce n'est pas gênant
        // merged.prix_ht_hp = merged.prix_ht_hp ?? 0;
        // merged.prix_ttc_hp = merged.prix_ttc_hp ?? 0;
        // merged.prix_ht_hc = merged.prix_ht_hc ?? 0;
        // merged.prix_ttc_hc = merged.prix_ttc_hc ?? 0;
      } else {
        merged.prix_ht_hp = userDataUI.prix_ht_hp;
        merged.prix_ttc_hp = userDataUI.prix_ttc_hp;
        merged.prix_ht_hc = userDataUI.prix_ht_hc;
        merged.prix_ttc_hc = userDataUI.prix_ttc_hc;
        merged.hc_start = userDataUI.hc_start;
        merged.hc_end = userDataUI.hc_end;
      }

      // Important: on ne touche pas aux clés de référence existantes (use_external, external_capteur, etc.)
      await saveUserOptions(merged);

      emit("selection:saved", selections);
      toast.success("Configuration enregistrée");
    } catch (err) {
      alert("Erreur sauvegarde configuration");
      console.error(err);
      toast.error("Erreur de sauvegarde");
    }
  });
}
