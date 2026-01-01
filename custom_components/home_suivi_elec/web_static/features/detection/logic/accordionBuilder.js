"use strict";

import { createElement } from '../../../shared/utils/dom.js';

/**
 * Crée un accordéon pliable/dépliable réutilisable
 * @param {string} title - Titre de l'accordéon
 * @param {Node|string} content - Contenu (DOM ou HTML)
 * @param {boolean} isOpen - Ouvert par défaut
 * @param {string} icon - Emoji/icône à afficher
 * @returns {HTMLElement}
 */
export function createAccordion(title, content, isOpen = true, icon = '📦') {
    const container = createElement('div', {
        className: 'accordion-item',
        style: 'margin-bottom: 15px; border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden;'
    });

    // Header cliquable
    const header = createElement('div', {
        className: 'accordion-header',
        style: 'padding: 15px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;'
    });

    const titleDiv = createElement('div', {
        style: 'display: flex; align-items: center; gap: 10px; font-weight: 600;'
    });

    const iconSpan = createElement('span', { style: 'font-size: 20px;' });
    iconSpan.textContent = icon;

    const titleText = createElement('span');
    titleText.textContent = title;

    titleDiv.appendChild(iconSpan);
    titleDiv.appendChild(titleText);

    // Flèche rotation
    const arrow = createElement('span', {
        className: 'accordion-arrow',
        style: `font-size: 20px; transition: transform 0.3s ease; transform: rotate(${isOpen ? '90deg' : '0deg'});`
    });
    arrow.textContent = '▶';

    header.appendChild(titleDiv);
    header.appendChild(arrow);

    // Body pliable
    const body = createElement('div', {
        className: 'accordion-body',
        style: `max-height: ${isOpen ? '2000px' : '0'}; overflow: hidden; transition: max-height 0.3s ease; background: white;`
    });

    const bodyInner = createElement('div', { style: 'padding: 20px;' });

    if (content instanceof Node) {
        bodyInner.appendChild(content);
    } else {
        bodyInner.innerHTML = content;
    }

    body.appendChild(bodyInner);

    // Toggle
    header.addEventListener('click', () => {
        const isCurrentlyOpen = body.style.maxHeight !== '0px';
        if (isCurrentlyOpen) {
            body.style.maxHeight = '0px';
            arrow.style.transform = 'rotate(0deg)';
        } else {
            body.style.maxHeight = '2000px';
            arrow.style.transform = 'rotate(90deg)';
        }
    });

    container.appendChild(header);
    container.appendChild(body);

    return container;
}
