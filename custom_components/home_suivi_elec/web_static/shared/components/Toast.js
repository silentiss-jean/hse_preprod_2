// shared/components/Toast.js
"use strict";

import { TOAST_TYPES } from '../constants.js';
import { createElement } from '../utils/dom.js';

export class Toast {
    static container = null;

    /**
     * Initialise le container de toasts
     */
    static init() {
        if (!this.container) {
            this.container = createElement('div', { 
                className: 'toast-container',
                id: 'toast-container'
            });
            document.body.appendChild(this.container);
        }
    }

    /**
     * Affiche un toast
     * @param {string} message - Message
     * @param {string} type - Type (success, error, warning, info)
     * @param {number} duration - Durée en ms (0 = permanent)
     */
    static show(message, type = TOAST_TYPES.INFO, duration = 5000) {
        this.init();

        const toast = createElement('div', { 
            className: `toast toast-${type}` 
        });

        const icon = this.getIcon(type);
        const content = createElement('div', { className: 'toast-content' }, [
            `${icon} ${message}`
        ]);

        const closeBtn = createElement('button', { 
            className: 'toast-close',
            onClick: () => this.remove(toast)
        }, ['×']);

        toast.appendChild(content);
        toast.appendChild(closeBtn);

        this.container.appendChild(toast);

        // Animation entrée
        setTimeout(() => toast.classList.add('show'), 10);

        // Auto-remove
        if (duration > 0) {
            setTimeout(() => this.remove(toast), duration);
        }

        return toast;
    }

    /**
     * Retire un toast
     */
    static remove(toast) {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }

    /**
     * Raccourcis
     */
    static success(message, duration = 5000) {
        return this.show(message, TOAST_TYPES.SUCCESS, duration);
    }

    static error(message, duration = 0) {
        return this.show(message, TOAST_TYPES.ERROR, duration);
    }

    static warning(message, duration = 7000) {
        return this.show(message, TOAST_TYPES.WARNING, duration);
    }

    static info(message, duration = 5000) {
        return this.show(message, TOAST_TYPES.INFO, duration);
    }

    /**
     * Icônes par type
     */
    static getIcon(type) {
        const icons = {
            [TOAST_TYPES.SUCCESS]: '✅',
            [TOAST_TYPES.ERROR]: '❌',
            [TOAST_TYPES.WARNING]: '⚠️',
            [TOAST_TYPES.INFO]: 'ℹ️'
        };
        return icons[type] || 'ℹ️';
    }
}
