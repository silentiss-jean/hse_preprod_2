// shared/constants.js
"use strict";

// Types de capteurs
export const SENSOR_TYPES = {
    POWER: 'power',
    ENERGY: 'energy',
    TEMPERATURE: 'temperature',
    HUMIDITY: 'humidity'
};

// Types de toasts
export const TOAST_TYPES = {
    SUCCESS: 'success',
    ERROR: 'error',
    WARNING: 'warning',
    INFO: 'info'
};

// Niveaux de qualité
export const QUALITY_LEVELS = {
    EXCELLENT: { score: 90, label: 'Excellent', color: '#28a745' },
    BON: { score: 70, label: 'Bon', color: '#17a2b8' },
    MOYEN: { score: 50, label: 'Moyen', color: '#ffc107' },
    FAIBLE: { score: 30, label: 'Faible', color: '#fd7e14' },
    MAUVAIS: { score: 0, label: 'Mauvais', color: '#dc3545' }
};

// Cycles migration
export const MIGRATION_CYCLES = {
    DAILY: 'daily',
    WEEKLY: 'weekly',
    MONTHLY: 'monthly',
    QUARTERLY: 'quarterly',
    YEARLY: 'yearly'
};

// API endpoints
export const API_BASE = '/api/home_suivi_elec';
export const ENDPOINTS = {
    CONFIG: `${API_BASE}/config`,
    DETECTION: `${API_BASE}/detection`,
    DUPLICATES: `${API_BASE}/duplicates`,
    MIGRATION: `${API_BASE}/migration`,
    DIAGNOSTICS: `${API_BASE}/diagnostics`,
    PROXY: `${API_BASE}/proxy`
};
