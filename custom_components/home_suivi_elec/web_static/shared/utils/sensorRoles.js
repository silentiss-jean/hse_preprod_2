// shared/utils/sensorRoles.js
"use strict";

export function getSensorRole(capteur) {
  if (!capteur) return null;

  // 1) Priorité au champ ui_role posé par sensorEnrichment
  const raw = (capteur.ui_role || "").toLowerCase();

  if (raw === "power") {
    return {
      id: "power",
      label: "Puissance",
      cssClass: "hse-role-badge hse-role-badge-power",
    };
  }

  if (raw === "energy") {
    return {
      id: "energy",
      label: "Énergie",
      cssClass: "hse-role-badge hse-role-badge-energy",
    };
  }

  // 2) Sinon, aucun rôle explicite
  return null;
}

// Petit helper HTML
export function createRoleBadgeHTML(capteur) {
  const role = getSensorRole(capteur);
  if (!role) return "";

  // On renvoie directement un span avec les classes dédiées
  return `<span class="${role.cssClass}">${role.label}</span>`;
}
