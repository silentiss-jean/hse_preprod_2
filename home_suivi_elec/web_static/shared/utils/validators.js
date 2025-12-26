// shared/utils/validators.js
"use strict";

/**
 * Valide un email
 */
export function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Valide un nombre
 */
export function isValidNumber(value, min = null, max = null) {
    const num = parseFloat(value);
    if (isNaN(num)) return false;

    if (min !== null && num < min) return false;
    if (max !== null && num > max) return false;

    return true;
}

/**
 * Valide une entity_id Home Assistant
 */
export function isValidEntityId(entityId) {
    const re = /^[a-z_]+\.[a-z0-9_]+$/;
    return re.test(entityId);
}

/**
 * Valide du YAML
 */
export function isValidYAML(yamlString) {
    try {
        // Simple vérification de syntaxe
        if (!yamlString || yamlString.trim() === '') return false;

        // Vérifier indentation cohérente
        const lines = yamlString.split('
');
        for (let line of lines) {
            if (line.trim() && !line.match(/^[\s]*[a-zA-Z0-9_-]+:/)) {
                return false;
            }
        }

        return true;
    } catch (e) {
        return false;
    }
}
