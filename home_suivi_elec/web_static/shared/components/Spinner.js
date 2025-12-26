// shared/components/Spinner.js
"use strict";

export class Spinner {
    /**
     * Crée un spinner de chargement
     * @param {string} size - Taille (small, medium, large)
     * @param {string} text - Texte optionnel
     */
    static create(size = 'medium', text = null) {
        const spinner = document.createElement('div');
        spinner.className = `spinner spinner-${size}`;

        const circle = document.createElement('div');
        circle.className = 'spinner-circle';
        spinner.appendChild(circle);

        if (text) {
            const label = document.createElement('span');
            label.className = 'spinner-label';
            label.textContent = text;
            spinner.appendChild(label);
        }

        return spinner;
    }

    /**
     * Spinner inline (pour boutons)
     */
    static inline() {
        return '⏳';
    }
}
