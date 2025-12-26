// shared/components/Modal.js
"use strict";

import { createElement, clearElement } from '../utils/dom.js';
import { Button } from './Button.js';

export class Modal {
    constructor(title, content, options = {}) {
        this.title = title;
        this.content = content;
        this.options = {
            size: options.size || 'medium', // small, medium, large
            closeOnBackdrop: options.closeOnBackdrop !== false,
            showClose: options.showClose !== false,
            buttons: options.buttons || []
        };

        this.modal = null;
        this.backdrop = null;
    }

    /**
     * Affiche le modal
     */
    show() {
        // Backdrop
        this.backdrop = createElement('div', { className: 'modal-backdrop' });

        if (this.options.closeOnBackdrop) {
            this.backdrop.addEventListener('click', () => this.close());
        }

        // Modal
        this.modal = createElement('div', { 
            className: `modal modal-${this.options.size}` 
        });

        // Header
        const header = createElement('div', { className: 'modal-header' });
        const titleEl = createElement('h2', {}, [this.title]);
        header.appendChild(titleEl);

        if (this.options.showClose) {
            const closeBtn = Button.create('×', () => this.close(), 'link');
            closeBtn.className = 'modal-close';
            header.appendChild(closeBtn);
        }

        // Body
        const body = createElement('div', { className: 'modal-body' });
        if (this.content instanceof Node) {
            body.appendChild(this.content);
        } else {
            body.innerHTML = this.content;
        }

        // Footer (si boutons)
        let footer = null;
        if (this.options.buttons.length > 0) {
            footer = createElement('div', { className: 'modal-footer' });

            this.options.buttons.forEach(btn => {
                const button = Button.create(
                    btn.text,
                    () => {
                        if (btn.onClick) btn.onClick();
                        if (btn.closeOnClick !== false) this.close();
                    },
                    btn.variant || 'secondary'
                );
                footer.appendChild(button);
            });
        }

        // Assemblage
        this.modal.appendChild(header);
        this.modal.appendChild(body);
        if (footer) this.modal.appendChild(footer);

        // Ajout DOM
        document.body.appendChild(this.backdrop);
        document.body.appendChild(this.modal);

        // Animation
        setTimeout(() => {
            this.backdrop.classList.add('show');
            this.modal.classList.add('show');
        }, 10);
    }

    /**
     * Ferme le modal
     */
    close() {
        this.backdrop.classList.remove('show');
        this.modal.classList.remove('show');

        setTimeout(() => {
            if (this.backdrop) this.backdrop.remove();
            if (this.modal) this.modal.remove();
        }, 300);
    }

    /**
     * Helper statique pour modal de confirmation
     */
    static confirm(title, message, onConfirm) {
        const modal = new Modal(title, `<p>${message}</p>`, {
            buttons: [
                { text: 'Annuler', variant: 'secondary' },
                { 
                    text: 'Confirmer', 
                    variant: 'primary',
                    onClick: onConfirm
                }
            ]
        });

        modal.show();
        return modal;
    }
}
