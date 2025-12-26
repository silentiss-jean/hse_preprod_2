// shared/utils/dom.js
"use strict";

/**
 * Crée un élément DOM avec attributs
 */
export function createElement(tag, attributes = {}, children = []) {
    const element = document.createElement(tag);

    // Appliquer attributs
    if (attributes && typeof attributes === 'object') {
        Object.entries(attributes).forEach(([key, value]) => {
            if (key === 'className' || key === 'class') {
                // Supporte className ET class
                element.className = value;
            } else if (key === 'dataset' && value && typeof value === 'object') {
                Object.entries(value).forEach(([dataKey, dataValue]) => {
                    element.dataset[dataKey] = dataValue;
                });
            } else if (key.startsWith('on') && typeof value === 'function') {
                element.addEventListener(key.substring(2).toLowerCase(), value);
            } else if (key === 'style' && typeof value === 'string') {
                // Optionnel : support direct d'un style en string
                element.style.cssText = value;
            } else if (value !== undefined && value !== null) {
                element.setAttribute(key, value);
            }
        });
    }

    // Normaliser children en tableau
    let childArray;
    if (children === undefined || children === null) {
        childArray = [];
    } else if (Array.isArray(children)) {
        childArray = children;
    } else {
        // string, number, Node, etc.
        childArray = [children];
    }

    // Ajouter enfants
    childArray.forEach(child => {
        if (child === null || child === undefined) return;

        if (typeof child === 'string' || typeof child === 'number') {
            element.appendChild(document.createTextNode(String(child)));
        } else if (child instanceof Node) {
            element.appendChild(child);
        }
        // Si ce n'est ni string/number ni Node, on l'ignore silencieusement
    });

    return element;
}


/**
 * Vide un élément DOM
 */
export function clearElement(element) {
    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

/**
 * Toggle classe
 */
export function toggleClass(element, className, force = null) {
    if (force === null) {
        element.classList.toggle(className);
    } else {
        element.classList.toggle(className, force);
    }
}

/**
 * Query selector sécurisé
 */
export function $(selector, parent = document) {
    return parent.querySelector(selector);
}

export function $$(selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
}
