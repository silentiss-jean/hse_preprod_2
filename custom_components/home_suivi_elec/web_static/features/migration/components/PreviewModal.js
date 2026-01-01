// features/migration/components/PreviewModal.js
"use strict";

import { Modal } from "../../../shared/components/Modal.js";
import { Button } from "../../../shared/components/Button.js";
import { createElement } from "../../../shared/utils/dom.js";
import { Toast } from "../../../shared/components/Toast.js";

/**
 * Modale de prévisualisation YAML avec copie presse-papiers + téléchargement.
 */
export class PreviewModal {
  /**
   * Affiche la modale.
   *
   * @param {string} title        Titre de la modale
   * @param {string} yamlContent  Contenu YAML à afficher
   * @param {Function} downloadFn Callback appelé quand on clique sur "Télécharger"
   * @returns {Modal}
   */
  static show(title, yamlContent, downloadFn) {
    const container = createElement("div", {
      className: "yaml-preview",
    });

    // Toolbar (bouton Copier)
    const toolbar = createElement("div", { className: "yaml-toolbar" });
    const copyBtn = Button.create(
      "Copier",
      () => PreviewModal.copyToClipboard(yamlContent),
      "secondary"
    );
    toolbar.appendChild(copyBtn);

    // Zone de code YAML
    const pre = createElement("pre", { className: "yaml-code" });
    const code = createElement("code", {}, yamlContent || "");
    pre.appendChild(code);

    container.appendChild(toolbar);
    container.appendChild(pre);


    const modal = new Modal(title, container, {
      size: "large",
      buttons: [
        { text: "Fermer", variant: "secondary" },
        {
          // on utilise un bouton standard pour garder la même API Modal
          text: "Télécharger",
          variant: "primary",
          onClick: downloadFn,
          closeOnClick: false,
        },
      ],
    });

    modal.show();
    return modal;
  }

  /**
   * Copie le texte YAML dans le presse-papiers.
   */
  static async copyToClipboard(text) {
    const value = text || "";
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        Toast.success("YAML copié dans le presse-papiers");
        return;
      }
      throw new Error("clipboard API unavailable");
    } catch (error) {
      try {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.exec.Command("copy");
        document.body.removeChild(ta);
        Toast.success("YAML copié dans le presse-papiers");
      } catch (e2) {
        console.error("[PreviewModal] Erreur copie presse-papiers:", error, e2);
        Toast.error("Erreur de copie dans le presse-papiers");
      }
    }
  }


}
