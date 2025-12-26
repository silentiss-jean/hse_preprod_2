"use strict";

import { createElement } from '../../../shared/utils/dom.js';
import { formatPower } from '../../../shared/utils/formatters.js';
import { Badge } from '../../../shared/components/Badge.js';
import { Card } from '../../../shared/components/Card.js';
import { createAccordion } from './accordionBuilder.js';

/**
 * Formate la valeur d'un capteur en fonction de son unité.
 * - W / kW : utilise formatPower
 * - Autres unités : concatène valeur + unité
 * - Pas d'unité : affiche juste la valeur
 *
 * @param {Object} sensor
 * @returns {string}
 */
function formatSensorValue(sensor) {
    const raw = sensor && sensor.value != null ? Number(sensor.value) : 0;
    const value = Number.isFinite(raw) ? raw : 0;
    const unit = sensor && sensor.unit_of_measurement ? String(sensor.unit_of_measurement) : '';

    if (unit === 'W' || unit === 'kW') {
        return formatPower(value);
    }

    if (unit) {
        return `${value} ${unit}`;
    }

    return `${value}`;
}

/**
 * Crée une card pour le capteur de référence
 */
export function buildReferenceCard(reference) {
    const container = createElement('div', { style: 'padding: 15px;' });

    if (!reference || !reference.entity_id) {
        const emptyP = createElement('p', { style: 'color: #666;' });
        emptyP.textContent = 'Aucun capteur de référence configuré';
        return Card.create('Capteur de référence', emptyP, '⭐');
    }

    const integration = reference.integration || '?';
    const area = reference.area || '?';

    // Titre
    const titleEl = createElement('h3', { style: 'margin: 0 0 10px 0;' });
    titleEl.textContent = reference.friendly_name || reference.entity_id;

    // Grid infos
    const gridDiv = createElement('div', {
        style: 'display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;'
    });

    // Intégration
    const integDiv = createElement('div');
    const integLabel = createElement('div', { style: 'color: #666; font-size: 12px;' });
    integLabel.textContent = 'Intégration';
    const integValue = createElement('div', { style: 'font-weight: bold;' });
    integValue.textContent = integration;
    integDiv.appendChild(integLabel);
    integDiv.appendChild(integValue);

    // Zone
    const areaDiv = createElement('div');
    const areaLabel = createElement('div', { style: 'color: #666; font-size: 12px;' });
    areaLabel.textContent = 'Zone';
    const areaValue = createElement('div', { style: 'font-weight: bold;' });
    areaValue.textContent = area;
    areaDiv.appendChild(areaLabel);
    areaDiv.appendChild(areaValue);

    gridDiv.appendChild(integDiv);
    gridDiv.appendChild(areaDiv);

    // Carte valeur actuelle
    const valueCard = createElement('div', {
        style: 'background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;'
    });

    const valueLabel = createElement('div', { style: 'font-size: 12px; opacity: 0.9;' });
    valueLabel.textContent = 'Valeur actuelle';

    const valueValue = createElement('div', { style: 'font-size: 32px; font-weight: bold; margin-top: 5px;' });
    valueValue.textContent = formatSensorValue(reference);

    valueCard.appendChild(valueLabel);
    valueCard.appendChild(valueValue);

    container.appendChild(titleEl);
    container.appendChild(gridDiv);
    container.appendChild(valueCard);

    return Card.create('Capteur de référence', container, '⭐');
}

/**
 * Crée un accordéon pour une intégration avec ses capteurs
 */
export function buildIntegrationAccordion(integration, sensors, isOpen = true) {
    const listDiv = createElement('div', { style: 'max-height: 400px; overflow-y: auto;' });

    sensors.forEach(sensor => {
        const area = sensor.area || 'Non assigné';

        const itemDiv = createElement('div', {
            className: 'sensor-item',
            style: 'padding: 12px; border-bottom: 1px solid #eee; transition: background 0.2s;'
        });

        // Hover
        itemDiv.addEventListener('mouseenter', () => itemDiv.style.background = '#f8f9fa');
        itemDiv.addEventListener('mouseleave', () => itemDiv.style.background = 'white');

        const flexDiv = createElement('div', {
            style: 'display: flex; justify-content: space-between; align-items: center;'
        });

        // Gauche
        const leftDiv = createElement('div');

        const nameEl = createElement('strong', { style: 'color: #333; font-size: 14px;' });
        nameEl.textContent = sensor.friendly_name || sensor.entity_id;

        const infoEl = createElement('div', { style: 'font-size: 12px; color: #666; margin-top: 4px;' });
        infoEl.textContent = `Zone: ${area} | ${sensor.entity_id}`;

        leftDiv.appendChild(nameEl);
        leftDiv.appendChild(infoEl);

        // Droite
        const rightDiv = createElement('div', { style: 'text-align: right;' });

        const valueEl = createElement('div', { style: 'font-weight: bold; color: #667eea; font-size: 16px;' });
        valueEl.textContent = formatSensorValue(sensor);

        rightDiv.appendChild(valueEl);

        flexDiv.appendChild(leftDiv);
        flexDiv.appendChild(rightDiv);

        itemDiv.appendChild(flexDiv);
        listDiv.appendChild(itemDiv);
    });

    // Badge compteur
    const badge = Badge.create(`${sensors.length} capteur(s)`, 'info');
    const badgeDiv = createElement('div', { style: 'margin-bottom: 15px;' });
    badgeDiv.appendChild(badge);

    const container = createElement('div');
    container.appendChild(badgeDiv);
    container.appendChild(listDiv);

    return createAccordion(`Intégration: ${integration}`, container, isOpen, '🔌');
}

/**
 * Crée l'accordéon des alternatives
 */
export function buildAlternativesAccordion(alternatives) {
    const total = Object.values(alternatives).reduce(
        (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
        0
    );

    if (total === 0) {
        const emptyDiv = createElement('p', {
            style: 'color: #666; text-align: center; padding: 20px;'
        });
        emptyDiv.textContent = 'Aucun capteur alternatif trouvé';
        return createAccordion('Capteurs alternatifs', emptyDiv, false, '🔄');
    }

    const container = createElement('div');

    Object.entries(alternatives).forEach(([integration, sensors]) => {
        const sensorList = createElement('div');

        sensors.forEach(s => {
            const itemDiv = createElement('div', {
                style: 'padding: 10px; border-bottom: 1px solid #eee;'
            });

            const flexDiv = createElement('div', {
                style: 'display: flex; justify-content: space-between; align-items: center;'
            });

            const nameEl = createElement('div', { style: 'font-size: 14px;' });
            nameEl.textContent = s.friendly_name || s.entity_id;

            const valueEl = createElement('div', { style: 'font-weight: bold; color: #f59e0b;' });
            valueEl.textContent = formatSensorValue(s);

            flexDiv.appendChild(nameEl);
            flexDiv.appendChild(valueEl);

            itemDiv.appendChild(flexDiv);
            sensorList.appendChild(itemDiv);
        });

        const badge = Badge.create(`${sensors.length} capteur(s)`, 'warning');
        const badgeDiv = createElement('div', { style: 'margin-bottom: 10px;' });
        badgeDiv.appendChild(badge);

        const innerContainer = createElement('div');
        innerContainer.appendChild(badgeDiv);
        innerContainer.appendChild(sensorList);

        const subAccordion = createAccordion(integration, innerContainer, false, '⚠️');
        container.appendChild(subAccordion);
    });

    const mainContainer = createElement('div', {
        style: 'background: #fff9e6; padding: 10px; border-radius: 8px;'
    });

    mainContainer.appendChild(container);

    return createAccordion(`Capteurs alternatifs (${total} total)`, mainContainer, false, '🔄');
}
