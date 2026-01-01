/**
 * Panel de sélection du capteur focus avec autocomplétion
 */
import { createElement } from '../../../shared/utils/dom.js';

export class FocusSelectorPanel {
    constructor(state) {
        this.state = state;
        this.container = null;
        this.sensors = [];
        this.filteredSensors = [];
    }

    render(sensors = []) {
        this.sensors = sensors;
        this.filteredSensors = sensors;

        this.container = createElement('div', { class: 'focus-selector-panel' });

        const label = createElement('label', { 
            textContent: 'Capteur à mettre en avant (optionnel):',
            class: 'focus-label',
        });
        this.container.appendChild(label);

        // Input avec autocomplétion
        const inputWrapper = createElement('div', { class: 'autocomplete-wrapper' });

        const input = createElement('input', {
            type: 'text',
            class: 'focus-input',
            placeholder: 'Rechercher un capteur...',
            id: 'focus_search',
        });

        input.addEventListener('input', (e) => this.handleSearch(e.target.value));
        input.addEventListener('focus', () => this.showDropdown());

        inputWrapper.appendChild(input);

        // Dropdown des suggestions
        const dropdown = createElement('ul', { 
            class: 'autocomplete-dropdown',
            id: 'focus_dropdown',
            style: 'display: none;',
        });
        inputWrapper.appendChild(dropdown);

        this.container.appendChild(inputWrapper);

        // Bouton clear
        const clearBtn = createElement('button', {
            class: 'btn-secondary btn-small',
            textContent: '✕ Retirer le focus',
            style: 'display: none;',
            id: 'clear_focus_btn',
        });

        clearBtn.addEventListener('click', () => this.clearFocus());
        this.container.appendChild(clearBtn);

        // Si un focus est déjà sélectionné, l'afficher
        const currentFocus = this.state.get('focus_entity_id');
        if (currentFocus) {
            const sensor = this.sensors.find(s => s.entity_id === currentFocus);
            if (sensor) {
                input.value = sensor.display_name;
                clearBtn.style.display = 'inline-block';
            }
        }

        return this.container;
    }

    handleSearch(query) {
        const q = query.toLowerCase().trim();

        if (!q) {
            this.filteredSensors = this.sensors;
        } else {
            this.filteredSensors = this.sensors.filter(s => 
                s.display_name.toLowerCase().includes(q) || 
                s.entity_id.toLowerCase().includes(q)
            );
        }

        this.updateDropdown();
    }

    showDropdown() {
        const dropdown = document.getElementById('focus_dropdown');
        if (dropdown) {
            this.updateDropdown();
            dropdown.style.display = 'block';
        }
    }

    hideDropdown() {
        const dropdown = document.getElementById('focus_dropdown');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    }

    updateDropdown() {
        const dropdown = document.getElementById('focus_dropdown');
        if (!dropdown) return;

        dropdown.innerHTML = '';

        if (this.filteredSensors.length === 0) {
            const emptyItem = createElement('li', { 
                textContent: 'Aucun résultat',
                class: 'dropdown-item empty',
            });
            dropdown.appendChild(emptyItem);
            dropdown.style.display = 'block';
            return;
        }

        // Limiter à 10 résultats
        const toShow = this.filteredSensors.slice(0, 10);

        toShow.forEach(sensor => {
            const item = createElement('li', { class: 'dropdown-item' });
            item.innerHTML = `
                <strong>${sensor.display_name}</strong>
                <span class="entity-id-small">${sensor.entity_id}</span>
            `;

            item.addEventListener('click', () => this.selectSensor(sensor));
            dropdown.appendChild(item);
        });

        dropdown.style.display = 'block';
    }

    selectSensor(sensor) {
        const input = document.getElementById('focus_search');
        const clearBtn = document.getElementById('clear_focus_btn');

        if (input) {
            input.value = sensor.display_name;
        }

        if (clearBtn) {
            clearBtn.style.display = 'inline-block';
        }

        this.state.update({ focus_entity_id: sensor.entity_id });
        this.hideDropdown();
    }

    clearFocus() {
        const input = document.getElementById('focus_search');
        const clearBtn = document.getElementById('clear_focus_btn');

        if (input) {
            input.value = '';
        }

        if (clearBtn) {
            clearBtn.style.display = 'none';
        }

        this.state.update({ focus_entity_id: null });
        this.filteredSensors = this.sensors;
        this.hideDropdown();
    }
}
