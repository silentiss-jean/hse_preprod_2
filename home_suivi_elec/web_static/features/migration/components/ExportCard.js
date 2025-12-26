// features/migration/components/ExportCard.js
"use strict";

import { Card } from "../../../shared/components/Card.js";
import { Button } from "../../../shared/components/Button.js";
import { createElement } from "../../../shared/utils/dom.js";


/**
 * Composant UI pour une option d'export (utility_meter, templates, etc.).
 *
 * option = {
 *   id: string,
 *   title: string,
 *   description: string,
 *   features?: string[],
 *   warnings?: string[],
 *   buttons: [{ text, onClick, variant?, icon?, disabled? }],
 *   icon?: string | null,
 *   rating?: number,
 *   recommended?: boolean,
 * }
 */
export class ExportCard {
  static create(option) {
    const content = createElement("div", {
      className: "export-card-content",
    });

    // Description
    const desc = createElement(
      "p",
      { className: "export-description" },
      option.description || ""
    );
    content.appendChild(desc);

    // Liste des features
    if (option.features && option.features.length > 0) {
      const ul = createElement("ul", { className: "export-features" });
      option.features.forEach((feature) => {
        const li = createElement("li", {}, feature);
        ul.appendChild(li);
      });
      content.appendChild(ul);
    }

    // Warnings éventuels
    if (option.warnings && option.warnings.length > 0) {
      const warnings = createElement("div", { className: "export-warnings" });
      option.warnings.forEach((warning) => {
        const p = createElement("p", {}, warning);
        warnings.appendChild(p);
      });
      content.appendChild(warnings);
    }

    // Boutons d'action
    const actions = createElement("div", { className: "export-actions" });
    (option.buttons || []).forEach((btn) => {
      const button = Button.create(
        btn.text,
        btn.onClick,
        btn.variant || "primary",
        btn.icon || null
      );
      if (btn.disabled) {
        button.disabled = true;
      }
      actions.appendChild(button);
    });
    content.appendChild(actions);

    // Titre avec éventuelle notation (★)
    let titleText = option.title || "";
    if (typeof option.rating === "number" && option.rating > 0) {
      const stars = "★".repeat(Math.min(option.rating, 5));
      titleText = `${titleText} ${stars}`;
    }

    // Création de la card via le composant partagé
    const card = Card.create(titleText, content, option.icon || null);
    card.classList.add("export-card");
    if (option.recommended) {
      card.classList.add("recommended");
    }

    return card;
  }
}
