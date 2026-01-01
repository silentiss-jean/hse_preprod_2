// shared/components/Button.js
"use strict";

export class Button {
    /**
     * Crée un bouton stylisé
     * @param {string} text - Texte du bouton
     * @param {Function} onClick - Callback click
     * @param {string} variant - Variant (primary, secondary, danger, success)
     * @param {string} icon - Emoji icon optionnel
     */
    static create(text, onClick, variant = 'primary', icon = null) {
        const button = document.createElement('button');
        button.className = `btn btn-${variant}`;

        if (icon) {
            button.innerHTML = `${icon} ${text}`;
        } else {
            button.textContent = text;
        }

        button.addEventListener('click', onClick);

        return button;
    }

    /**
     * Bouton avec loading spinner
     */
    static createWithLoading(text, onClick, variant = 'primary', icon = null) {
        const button = this.create(text, async (e) => {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = '⏳ Chargement...';

            try {
                await onClick(e);
            } finally {
                button.disabled = false;
                button.textContent = button.dataset.originalText;
            }
        }, variant, icon);

        return button;
    }
}
