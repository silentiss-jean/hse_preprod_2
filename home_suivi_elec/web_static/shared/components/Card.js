// shared/components/Card.js
"use strict";

import { createElement } from '../utils/dom.js';

export class Card {
    /**
     * Crée une card container
     * @param {string} title - Titre de la card
     * @param {HTMLElement} content - Contenu
     * @param {string} icon - Icon emoji optionnel
     */
    static create(title, content, icon = null) {
        const card = createElement('div', { className: 'card' });

        // Header
        const header = createElement('div', { className: 'card-header' });
        const titleEl = createElement('h3', { className: 'card-title' }, [
            icon ? `${icon} ${title}` : title
        ]);
        header.appendChild(titleEl);

        // Body
        const body = createElement('div', { className: 'card-body' });
        if (content instanceof Node) {
            body.appendChild(content);
        } else {
            body.innerHTML = content;
        }

        card.appendChild(header);
        card.appendChild(body);

        return card;
    }

    /**
     * Card avec footer
     */
    static createWithFooter(title, content, footer, icon = null) {
        const card = this.create(title, content, icon);

        const footerEl = createElement('div', { className: 'card-footer' });
        if (footer instanceof Node) {
            footerEl.appendChild(footer);
        } else {
            footerEl.innerHTML = footer;
        }

        card.appendChild(footerEl);

        return card;
    }
}
