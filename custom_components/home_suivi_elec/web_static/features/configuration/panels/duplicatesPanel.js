// features/configuration/panels/duplicatesPanel.js
"use strict";

import { createRoleBadgeHTML } from "../../../shared/utils/sensorRoles.js";

console.info("[dup] module chargé (panel doublons v2)");

/**
 * Rend le panneau complet "Doublons par appareil" :
 * - colonne 1 : doublons multi-intégrations
 * - colonne 2 : doublons par intégration
 * - colonne 3 : capteurs ignorés
 *
 * @param {HTMLElement} parentEl
 * @param {Object} cfg
 *   - groupsByDevice : Map signature -> { name, area, members:[{entity_id,integration,friendly_name}] }
 *   - ignored        : Set<string> entity_id ignorés
 *   - allCapteurs    : { entity_id: capteur enrichi }
 *   - refEntityId    : string (capteur de référence externe)
 *   - instantById    : { entity_id: number } (puissance instantanée)
 *   - onIgnore       : (entity_id, ignoreBool) => Promise
 *   - onKeepBest     : (entityIds: string[]) => Promise
 */
export function renderDuplicatesPanel(parentEl, cfg = {}) {
  if (!parentEl) return;

  const {
    groupsByDevice,
    ignored,
    allCapteurs,
    refEntityId,
    instantById,
    onIgnore,
    onKeepBest,
  } = cfg || {};

  const ignoredSet = new Set(ignored || []);

  const multiGroups = [];
  const intraByIntegration = new Map();
  const ignoredByIntegration = new Map();

  // =========================
  // Construction des groupes
  // =========================

  const groupsEntries = Array.from(
    groupsByDevice && typeof groupsByDevice.forEach === "function"
      ? groupsByDevice.entries()
      : [],
  );

  groupsEntries.forEach(([sig, g]) => {
    const base = g || {};
    const rawMembers = base.members || [];

    const activeMembers = rawMembers.filter(
      (m) => m && m.entity_id && !ignoredSet.has(m.entity_id),
    );

    if (activeMembers.length < 2) {
      return;
    }

    const integSet = new Set(
      activeMembers.map((m) => {
        const cap = allCapteurs?.[m.entity_id];
        return cap?.integration || m.integration || "unknown";
      }),
    );

    const groupObj = {
      signature: sig,
      name: base.name || "",
      area: base.area || "",
      members: activeMembers,
    };

    if (integSet.size >= 2) {
      multiGroups.push(groupObj);
    } else {
      const integ = Array.from(integSet)[0] || "unknown";
      if (!intraByIntegration.has(integ)) {
        intraByIntegration.set(integ, []);
      }
      intraByIntegration.get(integ).push(groupObj);
    }
  });

  // Capteurs ignorés : on les regroupe par intégration
  ignoredSet.forEach((eid) => {
    const cap = allCapteurs?.[eid];
    if (!cap) return;
    const integ = cap.integration || "unknown";
    if (!ignoredByIntegration.has(integ)) {
      ignoredByIntegration.set(integ, []);
    }
    ignoredByIntegration.get(integ).push(cap);
  });

  const totalMulti = multiGroups.reduce((sum, g) => sum + g.members.length, 0);
  const totalSame = Array.from(intraByIntegration.values()).reduce(
    (sum, arr) =>
      sum +
      arr.reduce((s, g) => s + (g.members ? g.members.length : 0), 0),
    0,
  );
  const totalIgnored = Array.from(ignoredByIntegration.values()).reduce(
    (sum, arr) => sum + arr.length,
    0,
  );

  console.log("[dup] regroupement", {
    groups: groupsEntries.length,
    totalMulti,
    totalSame,
    totalIgnored,
  });

  // =========================
  // Construction DOM
  // =========================

  parentEl.innerHTML = "";

  const title = document.createElement("h2");
  title.textContent = "Doublons par appareil";
  title.className = "hse-dup-title";
  parentEl.appendChild(title);

  const container = document.createElement("div");
  container.className = "hse-duplicates-grid";

  // ---------- Colonne 1 : multi-intégrations ----------

  const col1 = document.createElement("div");
  col1.className = "dup-column";

  const header1 = document.createElement("div");
  header1.className = "dup-column-header";
  header1.innerHTML = `
    <span>Doublons multi-intégrations</span>
    <span class="dup-count">${totalMulti}</span>
  `;
  col1.appendChild(header1);

  const body1 = document.createElement("div");
  body1.className = "dup-column-body";

  if (totalMulti === 0) {
    const p = document.createElement("p");
    p.textContent = "Aucun doublon multi-intégrations.";
    p.className = "dup-empty";
    body1.appendChild(p);
  } else {
    multiGroups.forEach((g) => {
      body1.appendChild(
        createGroupCard({
          group: g,
          labelPrefix: "Appareil",
          allCapteurs,
          refEntityId,
          instantById,
          onIgnore,
          onKeepBest,
          ignoredSet,
        }),
      );
    });
  }

  col1.appendChild(body1);
  container.appendChild(col1);

  // ---------- Colonne 2 : même intégration ----------

  const col2 = document.createElement("div");
  col2.className = "dup-column";

  const header2 = document.createElement("div");
  header2.className = "dup-column-header";
  header2.innerHTML = `
    <span>Doublons par intégration</span>
    <span class="dup-count">${totalSame}</span>
  `;
  col2.appendChild(header2);

  const body2 = document.createElement("div");
  body2.className = "dup-column-body";

  if (totalSame === 0) {
    const p = document.createElement("p");
    p.textContent = "Aucun doublon détecté.";
    p.className = "dup-empty";
    body2.appendChild(p);
  } else {
    const integKeys = Array.from(intraByIntegration.keys()).sort();
    integKeys.forEach((integ) => {
      const integGroups = intraByIntegration.get(integ) || [];
      const integHeader = document.createElement("div");
      integHeader.className = "dup-integration-header";
      integHeader.textContent = `${integ} (${integGroups.length})`;
      body2.appendChild(integHeader);

      integGroups.forEach((g) => {
        body2.appendChild(
          createGroupCard({
            group: g,
            labelPrefix: "Appareil",
            allCapteurs,
            refEntityId,
            instantById,
            onIgnore,
            onKeepBest,
            ignoredSet,
          }),
        );
      });
    });
  }

  col2.appendChild(body2);
  container.appendChild(col2);

  // ---------- Colonne 3 : ignorés ----------

  const col3 = document.createElement("div");
  col3.className = "dup-column";

  const header3 = document.createElement("div");
  header3.className = "dup-column-header";
  header3.innerHTML = `
    <span>Capteurs ignorés</span>
    <span class="dup-count">${totalIgnored}</span>
  `;
  col3.appendChild(header3);

  const body3 = document.createElement("div");
  body3.className = "dup-column-body";

  if (totalIgnored === 0) {
    const p = document.createElement("p");
    p.textContent = "Aucun capteur ignoré.";
    p.className = "dup-empty";
    body3.appendChild(p);
  } else {
    const integKeys = Array.from(ignoredByIntegration.keys()).sort();
    integKeys.forEach((integ) => {
      const sensors = ignoredByIntegration.get(integ) || [];
      const integHeader = document.createElement("div");
      integHeader.className = "dup-integration-header";
      integHeader.textContent = `${integ} (${sensors.length})`;
      body3.appendChild(integHeader);

      sensors.forEach((cap) => {
        const row = document.createElement("div");
        row.className = "dup-ignored-row";

        const main = document.createElement("div");
        main.className = "dup-ignored-main";

        const nameSpan = document.createElement("span");
        nameSpan.textContent =
          cap.friendly_name || cap.entity_id || "(sans nom)";
        nameSpan.className = "dup-sensor-name";
        main.appendChild(nameSpan);

        const roleHTML = createRoleBadgeHTML(cap);
        if (roleHTML) {
          const roleWrapper = document.createElement("span");
          roleWrapper.innerHTML = roleHTML;
          main.appendChild(roleWrapper);
        }

        row.appendChild(main);

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dup-btn-secondary";
        btn.textContent = "Réactiver";
        btn.onclick = () => {
          if (typeof onIgnore === "function") {
            onIgnore(cap.entity_id, false);
          }
        };
        row.appendChild(btn);

        body3.appendChild(row);
      });

    });
  }

  col3.appendChild(body3);
  container.appendChild(col3);

  parentEl.appendChild(container);
}


// =========================
// Helpers internes
// =========================

function createGroupCard(opts) {
  const {
    group,
    labelPrefix,
    allCapteurs,
    refEntityId,
    instantById,
    onIgnore,
    onKeepBest,
    ignoredSet,
  } = opts;

  const g = group || {};
  const members = g.members || [];

  const card = document.createElement("div");
  card.className = "dup-group-card";

  const title = document.createElement("div");
  title.className = "dup-group-title";
  title.innerHTML = `
    <span>${labelPrefix || "Groupe"} ${g.name || ""}${
      g.area ? " — " + g.area : ""
    }</span>
    <span>×${members.length}</span>
  `;
  card.appendChild(title);

  if (g.area) {
    const sub = document.createElement("div");
    sub.className = "dup-group-sub";
    sub.textContent = g.area;
    card.appendChild(sub);
  }

  members.forEach((m) => {
    const cap = allCapteurs?.[m.entity_id] || {};
    const row = document.createElement("div");
    row.className = "dup-sensor-row";

    const main = document.createElement("div");
    main.className = "dup-sensor-main";

    const nameLine = document.createElement("div");
    const nameSpan = document.createElement("span");
    nameSpan.className = "dup-sensor-name";
    nameSpan.textContent =
      cap.friendly_name || m.friendly_name || m.entity_id || "(sans nom)";
    nameLine.appendChild(nameSpan);

    if (m.entity_id === refEntityId) {
      const star = document.createElement("span");
      star.className = "dup-ref-star";
      star.textContent = "★";
      nameLine.appendChild(star);
    }

    const roleHTML = createRoleBadgeHTML(cap);
    if (roleHTML) {
      const roleWrapper = document.createElement("span");
      roleWrapper.innerHTML = roleHTML;
      nameLine.appendChild(roleWrapper);
    }

    main.appendChild(nameLine);

    const meta = document.createElement("div");
    meta.className = "dup-sensor-meta";

    const integSpan = document.createElement("span");
    integSpan.textContent = cap.integration || m.integration || "—";
    meta.appendChild(integSpan);

    const score = cap.quality_score;
    if (typeof score === "number") {
      const scoreSpan = document.createElement("span");
      scoreSpan.className = "dup-sensor-score";
      scoreSpan.textContent = `Score: ${score}`;
      meta.appendChild(scoreSpan);
    }

    const val = instantById?.[m.entity_id];
    if (typeof val === "number") {
      const liveSpan = document.createElement("span");
      liveSpan.textContent = `${val.toFixed(0)} W`;
      meta.appendChild(liveSpan);
    }

    main.appendChild(meta);
    row.appendChild(main);

    const btnIgnore = document.createElement("button");
    btnIgnore.type = "button";
    btnIgnore.className = "dup-btn-secondary";
    btnIgnore.textContent = "Ignorer";
    btnIgnore.onclick = () => {
      if (typeof onIgnore === "function") {
        onIgnore(m.entity_id, true);
      }
    };
    row.appendChild(btnIgnore);

    card.appendChild(row);
  });

  if (members.length > 1 && typeof onKeepBest === "function") {
    const actions = document.createElement("div");
    actions.className = "dup-actions";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "dup-btn-primary";
    btn.textContent = "Garder le meilleur";
    btn.onclick = () => {
      const ids = members.map((m) => m.entity_id).filter(Boolean);
      onKeepBest(ids);
    };

    actions.appendChild(btn);
    card.appendChild(actions);
  }

  return card;
}
