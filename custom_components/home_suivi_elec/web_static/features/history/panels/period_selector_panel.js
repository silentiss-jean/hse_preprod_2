/**
 * Panel de sélection des périodes (presets + date pickers custom)
 */
import { createElement } from '../../../shared/utils/dom.js';
//import { formatDateShort } from '../logic/formatters.js';

export class PeriodSelectorPanel {
    constructor(state) {
        this.state = state;
        this.container = null;
    }

    render() {
        this.container = createElement('div', { class: 'history-period-selector' });

        // Presets
        const presetsRow = createElement('div', { class: 'presets-row' });
        
        const presets = [
            { value: 'today_vs_yesterday', label: "Aujourd'hui vs Hier" },
            { value: 'weekend', label: 'Ce weekend vs Dernier weekend' },
            { value: 'week', label: 'Cette semaine vs Semaine dernière' },
            { value: 'custom', label: 'Personnalisé' },
        ];

        presets.forEach(preset => {
            const btn = createElement('button', {
                class: `preset-btn ${this.state.get('preset') === preset.value ? 'active' : ''}`,
                textContent: preset.label,
            });
            
            btn.addEventListener('click', () => {
                this.state.applyPreset(preset.value);
                this.updatePresetButtons(preset.value);
                if (preset.value !== 'custom') {
                    this.updateDateInputs();
                }
            });
            
            presetsRow.appendChild(btn);
        });

        this.container.appendChild(presetsRow);

        // Date pickers (mode custom)
        const customContainer = createElement('div', { class: 'custom-dates-container' });
        customContainer.style.display = this.state.get('preset') === 'custom' ? 'grid' : 'none';

        // Baseline
        const baselineGroup = this.createDateGroup('baseline', 'Période de référence (baseline)');
        customContainer.appendChild(baselineGroup);

        // Event
        const eventGroup = this.createDateGroup('event', 'Période à comparer (event)');
        customContainer.appendChild(eventGroup);

        this.container.appendChild(customContainer);

        // Bouton Analyser
        const analyzeBtn = createElement('button', {
            class: 'btn-primary btn-analyze',
            textContent: 'Lancer l\'analyse',
        });
        
        analyzeBtn.addEventListener('click', () => this.handleAnalyze());
        this.container.appendChild(analyzeBtn);

        return this.container;
    }

    createDateGroup(prefix, label) {
        const group = createElement('div', { class: 'date-group' });
        
        const title = createElement('h4', { textContent: label });
        group.appendChild(title);

        const row = createElement('div', { class: 'date-inputs-row' });

        // Start
        const startLabel = createElement('label', { textContent: 'Début' });
        const startInput = createElement('input', {
            type: 'datetime-local',
            class: 'date-input',
            id: `${prefix}_start`,
        });
        
        const startValue = this.state.get(`${prefix}_start`);
        if (startValue) {
            startInput.value = this.toDateTimeLocal(startValue);
        }
        
        startInput.addEventListener('change', (e) => {
            const updates = {};
            updates[`${prefix}_start`] = new Date(e.target.value);
            this.state.update(updates);
        });

        row.appendChild(startLabel);
        row.appendChild(startInput);

        // End
        const endLabel = createElement('label', { textContent: 'Fin' });
        const endInput = createElement('input', {
            type: 'datetime-local',
            class: 'date-input',
            id: `${prefix}_end`,
        });
        
        const endValue = this.state.get(`${prefix}_end`);
        if (endValue) {
            endInput.value = this.toDateTimeLocal(endValue);
        }
        
        endInput.addEventListener('change', (e) => {
            const updates = {};
            updates[`${prefix}_end`] = new Date(e.target.value);
            this.state.update(updates);
        });

        row.appendChild(endLabel);
        row.appendChild(endInput);

        group.appendChild(row);

        return group;
    }

    updatePresetButtons(activePreset) {
        const buttons = this.container.querySelectorAll('.preset-btn');
        buttons.forEach(btn => {
            btn.classList.toggle('active', btn.textContent === this.getPresetLabel(activePreset));
        });

        const customContainer = this.container.querySelector('.custom-dates-container');
        if (customContainer) {
            customContainer.style.display = activePreset === 'custom' ? 'grid' : 'none';
        }
    }

    updateDateInputs() {
        ['baseline', 'event'].forEach(prefix => {
            ['start', 'end'].forEach(suffix => {
                const input = this.container.querySelector(`#${prefix}_${suffix}`);
                const value = this.state.get(`${prefix}_${suffix}`);
                if (input && value) {
                    input.value = this.toDateTimeLocal(value);
                }
            });
        });
    }

    getPresetLabel(value) {
        const map = {
            'today_vs_yesterday': "Aujourd'hui vs Hier",
            'weekend': 'Ce weekend vs Dernier weekend',
            'week': 'Cette semaine vs Semaine dernière',
            'custom': 'Personnalisé',
        };
        return map[value] || value;
    }

    toDateTimeLocal(date) {
        if (!date) return '';
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    async handleAnalyze() {
        const validation = this.state.validatePeriods();
        if (!validation.valid) {
            alert(validation.error);
            return;
        }

        // Émettre un événement pour déclencher l'analyse
        const EventBus = await import('../../../shared/eventBus.js');
        EventBus.emit('history:analyze:requested');
    }
}
