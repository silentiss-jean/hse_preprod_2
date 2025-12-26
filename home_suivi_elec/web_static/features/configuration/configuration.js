// configuration.js — Orchestrateur principal (refactorisé + state canonique + isDirty)
"use strict";


// === IMPORTS API ===
import {
  getSensors,
  getUserOptions,
  saveUserOptions,
  setIgnoredEntity,
  chooseBestForDevice,
  getCostSensorsStatus,
  generateCostSensors,
} from "./configuration.api.js";


// === IMPORTS ÉTAT ===
import { bindUserOptions, composeConfig } from "./configuration.state.js";


// === IMPORTS PANELS / VUES ===
import { renderSelectionColumns } from "./panels/selectionPanel.js";
import { initReferencePanel } from "./panels/referencePanel.js";
import {
  renderUserConfigPanel,
  initUserConfigPanel,
} from "./panels/userConfigPanel.js";
import {
  renderAutoSelectPanel,
  initAutoSelectPanel,
} from "./panels/autoSelectPanel.js";
import { renderDuplicatesPanel } from "./panels/duplicatesPanel.js";


// === IMPORTS LOGIQUE MÉTIER ===
import {
  enrichWithQualityScores,
  getInstantPowerMap,
} from "./logic/sensorEnrichment.js";
import { indexByDuplicateGroup } from "./logic/sensorCategories.js";
import {
  annotateSameDevice,
  applyIgnoredFilter,
  deepClone,
} from "./logic/sensorAnnotation.js";
import { saveSelectionFromState } from "./logic/selectionSaver.js";


// === IMPORTS SHARED ===
import { createQualityBadgeHTML } from "../../shared/utils/sensorScoring.js";
import { emit } from "../../shared/eventBus.js";
import { toast } from "../../shared/uiToast.js";

console.info(
  "[config] module chargé (architecture modulaire v2 + state canonique + isDirty)",
);

export { createQualityBadgeHTML };


// =========================
// STATE CANONIQUE
// =========================

let currentOutSel = {};
let currentOutAlt = {};
let currentAllCapteurs = {};
let currentContentUpdated = null;

// État "dirty"
let isDirty = false;
let saveTimeout = null;

// Index duplicate_group
let duplicateIndex = new Map();


// =========================
// Helpers état / sauvegarde
// =========================

function markDirty() {
  isDirty = true;
  const saveBtn = document.getElementById("saveSelection");
  if (saveBtn) {
    saveBtn.textContent =
      "💾 Sauvegarder la sélection * (modifications en attente)";
    saveBtn.style.backgroundColor = "#ff9800";
    saveBtn.style.fontWeight = "600";
  }
}

function markClean() {
  isDirty = false;
  const saveBtn = document.getElementById("saveSelection");
  if (saveBtn) {
    saveBtn.textContent = "💾 Sauvegarder la sélection des capteurs";
    saveBtn.style.backgroundColor = "";
    saveBtn.style.fontWeight = "";
  }
}

function debouncedSave(callback, delay = 500) {
  if (saveTimeout) clearTimeout(saveTimeout);

  markDirty();

  saveTimeout = setTimeout(async () => {
    try {
      await callback();
      markClean();
    } catch (e) {
      console.error("[config] Erreur debouncedSave:", e);
    } finally {
      saveTimeout = null;
    }
  }, delay);
}


// =========================
// Gestion doublons actifs
// =========================

function hasActiveDuplicate(entityId, allCapteurs, contentEl) {
  const sensor = allCapteurs[entityId];
  if (!sensor) return false;

  const group = sensor.duplicate_group;
  const sensorType = sensor.type;
  if (!group) return false;

  const groupMembers = duplicateIndex.get(group) || [];

  const conflicts = groupMembers
    .filter((eid) => eid !== entityId)
    .map((eid) => allCapteurs[eid])
    .filter((c) => c && (!sensorType || c.type === sensorType));

  const activeConflicts = conflicts.filter((c) => {
    const cb = contentEl.querySelector(
      `input.capteur-checkbox[data-entity="${c.entity_id}"]`,
    );
    return cb?.checked;
  });

  if (activeConflicts.length > 0) {
    const conflict = activeConflicts[0];
    toast.error(
      `⚠️ Ce capteur est en doublon avec ` +
        `${conflict.friendly_name || conflict.entity_id} (${conflict.integration}). ` +
        `Utilise le panneau "Doublons par appareil" pour en ignorer un.`,
    );
    return true;
  }

  return false;
}


// =========================
// Helpers sur les buckets
// =========================

function removeEntityFromBucket(buckets, integration, entityId) {
  if (!buckets[integration]) return;
  buckets[integration] = buckets[integration].filter(
    (c) => c.entity_id !== entityId,
  );
  if (buckets[integration].length === 0) {
    delete buckets[integration];
  }
}

function addEntityToBucketUnique(buckets, integration, capteur) {
  if (!capteur?.entity_id) return;
  buckets[integration] ??= [];
  if (!buckets[integration].some((c) => c.entity_id === capteur.entity_id)) {
    buckets[integration].push(capteur);
  }
}


// =========================
// Auto sélection par score
// =========================

async function autoSelectBestSensors() {
  console.log("[config] autoSelectBestSensors démarré");

  const selectedArray = [];
  const alternativesArray = [];

  for (const integrationKey in currentOutSel) {
    const sensors = currentOutSel[integrationKey];
    if (Array.isArray(sensors)) {
      selectedArray.push(...sensors);
    }
  }

  for (const integrationKey in currentOutAlt) {
    const sensors = currentOutAlt[integrationKey];
    if (Array.isArray(sensors)) {
      alternativesArray.push(...sensors);
    }
  }

  const allSensors = [...selectedArray, ...alternativesArray];

  console.log("[config] Alternatives reçues:", alternativesArray.length);
  console.log("[config] Sélectionnés déjà présents:", selectedArray.length);
  console.log("[config] Total capteurs à analyser:", allSensors.length);

  if (allSensors.length === 0) {
    console.warn("[config] Aucun capteur disponible pour sélection auto");
    return { count: 0, sensors: [] };
  }

  const deviceMap = new Map();

  allSensors.forEach((sensor) => {
    let groupKey = sensor.device_id || sensor.deviceId;
    if (!groupKey || groupKey === "null") {
      groupKey = sensor.duplicate_group || sensor.entity_id;
    }

    if (!deviceMap.has(groupKey)) {
      deviceMap.set(groupKey, []);
    }
    deviceMap.get(groupKey).push(sensor);
  });

  console.log("[config] Appareils/groupes détectés:", deviceMap.size);

  let selectedCount = 0;
  const selectedSensors = [];

  for (const [, sensors] of deviceMap.entries()) {
    const sorted = sensors.sort((a, b) => {
      const scoreA = a.quality_score || a.qualityScore || 0;
      const scoreB = b.quality_score || b.qualityScore || 0;
      return scoreB - scoreA;
    });

    const best = sorted[0];
    if (!best) continue;

    const bestId = best.entity_id || best.entityId;

    for (const sensor of sensors) {
      const eid = sensor.entity_id || sensor.entityId;
      const integSensor = sensor.integration || "unknown";

      if (eid === bestId) {
        removeEntityFromBucket(currentOutAlt, integSensor, eid);
        addEntityToBucketUnique(currentOutSel, integSensor, sensor);
      } else {
        removeEntityFromBucket(currentOutSel, integSensor, eid);
        addEntityToBucketUnique(currentOutAlt, integSensor, sensor);
      }
    }

    for (const sensor of sensors) {
      const eid = sensor.entity_id || sensor.entityId;
      const checkbox = document.querySelector(
        `input.capteur-checkbox[data-entity="${eid}"]`,
      );
      if (!checkbox) continue;

      checkbox.checked = eid === bestId;
    }

    selectedCount++;
    selectedSensors.push(best);
    console.log(
      `[config] ✅ Auto sélection state: ${bestId} (score: ${
        best.quality_score || 0
      })`,
    );
  }

  console.log(
    `[config] Sélection auto terminée (state) : ${selectedCount} capteur(s) sélectionné(s)`,
  );

  markDirty();

  toast.info(
    `Sélection auto appliquée dans l'interface (${selectedCount} capteur(s)). ` +
      `Clique sur "Sauvegarder" pour persister.`,
  );

  return {
    count: selectedCount,
    sensors: selectedSensors,
  };
}


// =========================
// Chargement principal
// =========================

async function initCostSensorsRuntimePanel(options) {
  const checkbox = document.getElementById("enable_cost_sensors_runtime");
  const statusEl = document.getElementById("costSensorsStatus");
  const btn = document.getElementById("btnGenerateCostSensors");

  if (checkbox) checkbox.checked = !!options?.enable_cost_sensors_runtime;

  async function refreshStatus() {
    if (!statusEl) return;
    statusEl.textContent = "Statut : chargement...";
    try {
      const res = await getCostSensorsStatus();
      const count = res?.data?.count ?? res?.count ?? 0;
      statusEl.textContent = `${count} capteurs coût détectés`;
    } catch (e) {
      statusEl.textContent = "Statut : erreur";
    }
  }

  if (btn) {
    btn.addEventListener("click", async () => {
      if (statusEl) statusEl.textContent = "Génération en cours...";
      await generateCostSensors();
      await refreshStatus();
    });
  }

  await refreshStatus();
}

export async function loadConfiguration() {
  const configContainer = document.getElementById("configuration");
  if (!configContainer) {
    console.error("[config] Conteneur #configuration introuvable");
    return;
  }

  const content = document.getElementById("content-configuration");
  if (content) {
    content.innerHTML = "Chargement...";
  }

  try {
    const [sensorsRaw, options] = await Promise.all([
      getSensors(),
      getUserOptions(),
    ]);

    console.log("✅ [config] Données chargées:", { sensorsRaw, options });

    let {
      selected = {},
      alternatives = {},
      reference_sensor = {},
    } = deepClone(sensorsRaw || {});

    const useExternal = !!options?.use_external;

    const refEntityId = useExternal ? options?.external_capteur || "" : "";
    const ignored_entities = new Set(
      (options?.ignored_entities || []).filter(Boolean),
    );

    const allCapteurs = {};
    for (const lst of [selected, alternatives]) {
      Object.values(lst || {})
        .flat()
        .forEach((c) => {
          if (c && c.entity_id) allCapteurs[c.entity_id] = c;
        });
    }

    await enrichWithQualityScores(allCapteurs);
    window.__ALL_CAPTEURS__ = allCapteurs;

    // Index duplicate_group pour hasActiveDuplicate
    duplicateIndex = new Map();
    Object.entries(allCapteurs).forEach(([eid, capteur]) => {
      if (capteur.duplicate_group) {
        if (!duplicateIndex.has(capteur.duplicate_group)) {
          duplicateIndex.set(capteur.duplicate_group, []);
        }
        duplicateIndex.get(capteur.duplicate_group).push(eid);
      }
    });
    window.__DUPLICATE_INDEX__ = duplicateIndex;

    const { outSel, outAlt } = applyIgnoredFilter(
      selected,
      alternatives,
      ignored_entities,
    );
    annotateSameDevice(outSel, outAlt);

    // Filtrer le capteur de référence des sélections
    const refId = useExternal ? options?.external_capteur || "" : "";
    if (refId) {
      for (const integration in outSel) {
        outSel[integration] = (outSel[integration] || []).filter(
          (c) => c.entity_id !== refId,
        );
        if (outSel[integration].length === 0) {
          delete outSel[integration];
        }
      }
      for (const integration in outAlt) {
        outAlt[integration] = (outAlt[integration] || []).filter(
          (c) => c.entity_id !== refId,
        );
        if (outAlt[integration].length === 0) {
          delete outAlt[integration];
        }
      }
    }

    currentOutSel = outSel;
    currentOutAlt = outAlt;
    currentAllCapteurs = allCapteurs;

    console.log("[config] Données stockées dans les variables de module:", {
      selected: Object.keys(currentOutSel).length,
      alternatives: Object.keys(currentOutAlt).length,
      allCapteurs: Object.keys(currentAllCapteurs).length,
    });

    const groupsByDevice = indexByDuplicateGroup(allCapteurs);
    window.__DBG_GROUPS_BY_DEVICE__ = groupsByDevice;

    const instantById = await getInstantPowerMap();

    // Squelette HTML principal
    configContainer.innerHTML = `
      ${renderUserConfigPanel()}
      ${renderAutoSelectPanel()}
      <div id="reference-panel" class="card"></div>
      <div id="content-configuration"></div>
      <button id="saveSelection" class="primary" type="button">
        💾 Sauvegarder la sélection des capteurs
      </button>
    `;

    const contentUpdated = document.getElementById("content-configuration");
    currentContentUpdated = contentUpdated;

    // =========================
    // Initialisation panneaux
    // =========================

    console.log("[config] 1. Appel initUserConfigPanel avec composeConfig");
    const onSaveSelection = async () => {
      try {
        await saveSelectionFromState(
          currentOutSel,
          currentOutAlt,
          currentAllCapteurs,
          loadConfiguration,
        );
        markClean();
      } catch (e) {
        console.error("[config] Erreur onSaveSelection", e);
      }
    };

    const composedConfig = composeConfig(options, sensorsRaw?.data || {});
    initUserConfigPanel(composedConfig);
    await initCostSensorsRuntimePanel(options);

    console.log("[config] 2. Appel initAutoSelectPanel");
    initAutoSelectPanel(autoSelectBestSensors);

    const referencePanel = document.getElementById("reference-panel");
    if (referencePanel) {
      console.log("[config] 3. Appel initReferencePanel");
      await initReferencePanel(referencePanel, allCapteurs);
    }

    // =========================
    // Contenu dynamique config
    // =========================

    contentUpdated.innerHTML = "";

    const banner = document.createElement("div");
    banner.style.cssText = `
      background: #fff3cd;
      border: 1px solid #ffc107;
      border-radius: 4px;
      padding: 12px;
      margin-bottom: 16px;
      font-size: 14px;
    `;
    banner.innerHTML = `
      <strong>ℹ️ Gestion des doublons multi-intégrations</strong><br>
      Un seul capteur par appareil physique (par type : energy/power) peut être actif.<br>
      Les capteurs en conflit seront automatiquement ignorés lors de l'activation.
    `;
    contentUpdated.appendChild(banner);

    // Gestion du pliage par intégration
    const getFold = (k, c) => {
      try {
        return JSON.parse(
          sessionStorage.getItem(`fold:${k}:${c}`) || "false",
        );
      } catch {
        return false;
      }
    };

    const setFold = (k, c, v) => {
      try {
        sessionStorage.setItem(`fold:${k}:${c}`, JSON.stringify(!!v));
      } catch {
        // ignore
      }
    };

    // Fonction de rendu des colonnes de sélection
    function refreshSelectionColumns() {
      if (!contentUpdated) return;
      renderSelectionColumns(contentUpdated, {
        selected: currentOutSel,
        alternatives: currentOutAlt,
        refEntityId,
        handlers,
        getFold,
        setFold,
      });
    }

    // Handlers de sélection (utilisés par selectionPanel)
    const handlers = {
      selectAll: async (integration) => {
        const integ = integration || "unknown";

        const sensors = [
          ...(currentOutSel[integ] || []),
          ...(currentOutAlt[integ] || []),
        ];

        for (const sensor of sensors) {
          const eid = sensor.entity_id;
          if (!eid) continue;

          if (hasActiveDuplicate(eid, allCapteurs, contentUpdated)) {
            continue;
          }

          removeEntityFromBucket(currentOutAlt, integ, eid);
          addEntityToBucketUnique(currentOutSel, integ, sensor);

          const cb = contentUpdated.querySelector(
            `input.capteur-checkbox[data-entity="${eid}"]`,
          );
          if (cb) cb.checked = true;
        }

        debouncedSave(() =>
          saveSelectionFromState(
            currentOutSel,
            currentOutAlt,
            currentAllCapteurs,
            loadConfiguration,
          ),
        );
      },

      deselectAll: async (integration) => {
        const integ = integration || "unknown";
        const sensors = [...(currentOutSel[integ] || [])];

        for (const sensor of sensors) {
          const eid = sensor.entity_id;
          if (!eid) continue;
          removeEntityFromBucket(currentOutSel, integ, eid);
          addEntityToBucketUnique(currentOutAlt, integ, sensor);

          const cb = contentUpdated.querySelector(
            `input.capteur-checkbox[data-entity="${eid}"]`,
          );
          if (cb) cb.checked = false;
        }

        debouncedSave(() =>
          saveSelectionFromState(
            currentOutSel,
            currentOutAlt,
            currentAllCapteurs,
            loadConfiguration,
          ),
        );
      },

      checkbox: async (entityId, checked) => {
        const capteur = currentAllCapteurs[entityId];
        if (!capteur) return;
        const integ = capteur.integration || "unknown";

        if (checked) {
          if (hasActiveDuplicate(entityId, allCapteurs, contentUpdated)) {
            setTimeout(() => {
              const cb = contentUpdated.querySelector(
                `input.capteur-checkbox[data-entity="${entityId}"]`,
              );
              if (cb) cb.checked = false;
            }, 0);
            return;
          }

          removeEntityFromBucket(currentOutAlt, integ, entityId);
          addEntityToBucketUnique(currentOutSel, integ, capteur);
        } else {
          removeEntityFromBucket(currentOutSel, integ, entityId);
          addEntityToBucketUnique(currentOutAlt, integ, capteur);
        }

        debouncedSave(() =>
          saveSelectionFromState(
            currentOutSel,
            currentOutAlt,
            currentAllCapteurs,
            loadConfiguration,
          ),
        );
      },

      toggleSummary: (entityId, include) => {
        const capteur = currentAllCapteurs[entityId];
        if (!capteur) return;

        capteur.include_in_summary = !!include;
        console.log("[config] toggleSummary", entityId, include);

        // On considère que ça fait partie de la sélection à sauver
        markDirty();
      },

      // ✅ Bulk Summary pour une intégration (selected + alternatives)
      setSummaryForIntegration: (integration, value) => {
        const integ = integration || "unknown";
        const next = !!value;

        const apply = (buckets) => {
          const list = buckets[integ] || [];
          list.forEach((cap) => {
            if (!cap) return;
            cap.include_in_summary = next;
          });
        };

        apply(currentOutSel);
        apply(currentOutAlt);

        console.log("[config] setSummaryForIntegration", integ, next, {
          sel: (currentOutSel[integ] || []).length,
          alt: (currentOutAlt[integ] || []).length,
        });

        markDirty();
        refreshSelectionColumns();
      },

    };

    console.log(
      "[DEBUG selection] selected.template =",
      (currentOutSel?.template || []).length,
      "alternatives.template =",
      (currentOutAlt?.template || []).length,
    );

    // Panneau de sélection
    refreshSelectionColumns();

    // =========================
    // Nouveau panneau doublons
    // =========================

    const dupRoot = document.createElement("div");
    dupRoot.id = "hse-duplicates-root";
    contentUpdated.appendChild(dupRoot);

    renderDuplicatesPanel(dupRoot, {
      groupsByDevice,
      ignored: ignored_entities,
      allCapteurs,
      refEntityId,
      instantById,
      onIgnore: async (entity_id, ignore) => {
        try {
          await setIgnoredEntity(entity_id, ignore);
          await loadConfiguration();
          toast.info(ignore ? "Capteur ignoré" : "Capteur réintégré");
        } catch (err) {
          alert("❌ Erreur mise à jour des ignorés");
          console.error(err);
          toast.error("Erreur mise à jour ignorés");
        }
      },
      onKeepBest: async (entityIds) => {
        try {
          console.log("[onKeepBest] 🔵 Démarrage avec entityIds:", entityIds);

          if (!Array.isArray(entityIds) || entityIds.length === 0) {
            toast.error("Aucun capteur à traiter");
            return;
          }

          const sensors = entityIds
            .map((eid) => currentAllCapteurs[eid])
            .filter(Boolean)
            .sort(
              (a, b) => (b.quality_score || 0) - (a.quality_score || 0),
            );

          if (sensors.length === 0) {
            toast.error("Capteurs introuvables");
            return;
          }

          const best = sensors[0];
          console.log(
            "[onKeepBest] ✨ Meilleur:",
            best.entity_id,
            "score:",
            best.quality_score,
          );

          for (const sensor of sensors) {
            const eid = sensor.entity_id;
            const integ = sensor.integration || "unknown";

            if (eid === best.entity_id) {
              removeEntityFromBucket(currentOutAlt, integ, eid);
              addEntityToBucketUnique(currentOutSel, integ, sensor);
            } else {
              removeEntityFromBucket(currentOutSel, integ, eid);
              addEntityToBucketUnique(currentOutAlt, integ, sensor);
            }
          }

          for (const sensor of sensors) {
            const eid = sensor.entity_id;
            const cb = contentUpdated.querySelector(
              `input.capteur-checkbox[data-entity="${eid}"]`,
            );
            if (cb) {
              cb.checked = eid === best.entity_id;
            }
          }

          console.log("[onKeepBest] 💾 Construction payload normalisé...");

          const selections = {};

          for (const [integration, capteurs] of Object.entries(
            currentOutSel,
          )) {
            if (!selections[integration]) selections[integration] = [];
            for (const c of capteurs) {
              selections[integration].push({
                entity_id:
                  typeof c === "object" && c !== null
                    ? c.entity_id
                    : String(c),
                enabled: true,
              });
            }
          }

          for (const [integration, capteurs] of Object.entries(
            currentOutAlt,
          )) {
            if (!selections[integration]) selections[integration] = [];
            for (const c of capteurs) {
              selections[integration].push({
                entity_id:
                  typeof c === "object" && c !== null
                    ? c.entity_id
                    : String(c),
                enabled: false,
              });
            }
          }

          console.log("[onKeepBest] 📦 Payload:", {
            integrations: Object.keys(selections),
            total: Object.values(selections).flat().length,
            example: selections[Object.keys(selections)[0]]?.[0],
          });

          const response = await fetch(
            "/api/home_suivi_elec/save_selection",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(selections),
            },
          );

          const result = await response.json();
          console.log("[onKeepBest] 📥 Réponse:", result);

          if (result.success) {
            const losers = sensors.filter(
              (s) => s.entity_id !== best.entity_id,
            );
            console.log(
              "[onKeepBest] ✅ Sauvegarde OK, losers à ignorer:",
              losers.map((l) => l.entity_id),
            );

            for (const loser of losers) {
              try {
                await setIgnoredEntity(loser.entity_id, true);
                console.log("[onKeepBest] 🚫 Ignoré:", loser.entity_id);
              } catch (e) {
                console.error(
                  "[onKeepBest] Erreur setIgnoredEntity pour",
                  loser.entity_id,
                  e,
                );
              }
            }

            toast.success(
              `✅ Meilleur conservé : ${
                best.friendly_name || best.entity_id
              }`,
            );
            markClean();

            await loadConfiguration();
            console.log(
              "[onKeepBest] 🔄 Configuration rechargée (meilleur + ignorés mis à jour)",
            );
          } else {
            toast.error(`❌ ${result.error || "Erreur sauvegarde"}`);
            console.error("[onKeepBest] Backend error:", result);
          }
        } catch (err) {
          console.error("[onKeepBest] ❌ Exception:", err);
          toast.error("Erreur choix automatique");
        }
      },
    });

    // =========================
    // Bind options + sauvegarde
    // =========================

    console.log("[config] 4. Appel bindUserOptions");
    bindUserOptions(async (payload) => {
      console.log("[config] ✅ Sauvegarde options avec payload:", payload);
      await saveUserOptions(payload);
      await loadConfiguration();
      toast.success("Options enregistrées");
    });

    const saveButton = document.getElementById("saveSelection");
    if (saveButton) {
      saveButton.addEventListener("click", onSaveSelection);
    }

    window.removeEventListener("hse:save-selection", onSaveSelection);
    window.addEventListener("hse:save-selection", onSaveSelection);

    window.addEventListener("beforeunload", (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue =
          "Modifications non sauvegardées. Quitter quand même ?";
        return e.returnValue;
      }
    });

    console.log("✅ [config] Configuration chargée avec succès");

    markClean();
  } catch (err) {
    console.error("[config] loadConfiguration() — erreur", err);
    const errorContent = document.getElementById("content-configuration");
    if (errorContent) {
      errorContent.innerHTML = `
        <div style="color: red; padding: 20px;">
          <h3>❌ Erreur de chargement</h3>
          <p>${err.message}</p>
        </div>
      `;
    }
    toast.error("Erreur de chargement configuration");
  }
}
