// shared/components/DownloadButton.js
"use strict";

import { Button } from './Button.js';
import { Toast } from './Toast.js';

export class DownloadButton {
    /**
     * Crée un bouton de téléchargement
     * @param {string} text - Texte du bouton
     * @param {Function} getData - Fonction qui retourne les données
     * @param {string} filename - Nom du fichier
     * @param {string} mimeType - Type MIME
     */
    static create(text, getData, filename, mimeType = 'text/plain') {
        return Button.createWithLoading(text, async () => {
            try {
                const data = await getData();
                this.download(data, filename, mimeType);
                Toast.success(`Fichier ${filename} téléchargé`);
            } catch (error) {
                console.error('Erreur téléchargement:', error);
                Toast.error(`Erreur: ${error.message}`);
            }
        }, 'primary', '📥');
    }

    /**
     * Télécharge des données
     */
    static download(data, filename, mimeType) {
        const blob = new Blob([data], { type: mimeType });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        URL.revokeObjectURL(url);
    }
}
