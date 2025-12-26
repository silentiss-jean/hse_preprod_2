"use strict";

/**
 * Vues communes réutilisables entre modules
 * Pattern Phase 3 : DOM manipulation avec composants partagés
 */

import { Spinner } from '../components/Spinner.js';
import { Card } from '../components/Card.js';
import { createElement } from '../utils/dom.js';
import { Toast } from '../components/Toast.js';

/**
 * Affiche un spinner de chargement standard
 * @param {HTMLElement} container - Conteneur DOM
 * @param {string} message - Message à afficher (défaut: 'Chargement...')
 */
export function renderLoader(container, message = 'Chargement...') {
    if (!container) {
        console.error('[commonViews] renderLoader: container requis');
        return;
    }
    
    container.innerHTML = '';
    const spinner = Spinner.create('medium', message);
    container.appendChild(spinner);
}

/**
 * Affiche un message d'erreur standard avec Card et Toast
 * @param {HTMLElement} container - Conteneur DOM
 * @param {Error|string} error - Erreur ou message d'erreur
 */
export function renderError(container, error) {
    if (!container) {
        console.error('[commonViews] renderError: container requis');
        return;
    }
    
    container.innerHTML = '';

    const errorP = createElement('p', { style: 'color: #dc3545;' });
    errorP.textContent = error.message || error;

    const errorCard = Card.create('Erreur', errorP, '❌');
    container.appendChild(errorCard);

    Toast.error(`Erreur: ${error.message || error}`);
}

/**
 * Affiche un message d'état vide standard
 * @param {HTMLElement} container - Conteneur DOM
 * @param {string} message - Message à afficher
 * @param {string} icon - Icône emoji (défaut: '🔍')
 */
export function renderEmptyState(container, message, icon = '🔍') {
    if (!container) {
        console.error('[commonViews] renderEmptyState: container requis');
        return;
    }
    
    container.innerHTML = '';

    const emptyP = createElement('p', { style: 'color: #666;' });
    emptyP.textContent = message;

    const emptyCard = Card.create('Aucun résultat', emptyP, icon);
    container.appendChild(emptyCard);
}
