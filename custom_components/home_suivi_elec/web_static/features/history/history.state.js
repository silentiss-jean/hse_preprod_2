/**
 * Gestion de l'état du module History
 */
import * as EventBus from '../../shared/eventBus.js';

export class HistoryState {
    constructor() {
        this.data = {
            // Périodes de comparaison
            baseline_start: null,
            baseline_end: null,
            event_start: null,
            event_end: null,
            
            // Focus entity
            focus_entity_id: null,
            
            // Paramètres
            group_by: 'hour',
            week_anchor_day: 'monday',
            top_limit: 10,
            top_sort_by: 'cost_ttc',
            
            // Résultats
            analysis_result: null,
            available_sensors: [],
            
            // UI
            loading: false,
            error: null,
            preset: 'custom', // 'today_vs_yesterday', 'weekend', 'week', 'custom'
        };
    }

    /**
     * Met à jour le state et notifie les observateurs
     */
    update(updates) {
        Object.assign(this.data, updates);
        EventBus.emit('history:state:changed', this.data);
    }

    /**
     * Récupère une valeur du state
     */
    get(key) {
        return this.data[key];
    }

    /**
     * Applique un preset de période
     */
    applyPreset(preset) {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        
        // ✅ CORRECTION : Déclare dayOfWeek ICI (avant le switch)
        const dayOfWeek = now.getDay(); // 0=dimanche, 6=samedi
        
        let baseline_start, baseline_end, event_start, event_end;

        switch (preset) {
            case 'today_vs_yesterday':
                // Aujourd'hui vs hier (18h-23h59)
                event_start = new Date(today);
                event_start.setHours(18, 0, 0, 0);
                event_end = new Date(today);
                event_end.setHours(23, 59, 59, 999);
                
                baseline_start = new Date(event_start);
                baseline_start.setDate(baseline_start.getDate() - 1);
                baseline_end = new Date(event_end);
                baseline_end.setDate(baseline_end.getDate() - 1);
                break;

            case 'weekend':
                // Ce weekend vs dernier weekend (samedi 00h - dimanche 23h59)
                // ❌ SUPPRIME cette ligne (dayOfWeek est déjà déclarée en haut)
                // const dayOfWeek = now.getDay();
                
                const daysToLastSunday = dayOfWeek === 0 ? 0 : dayOfWeek;
                
                // Weekend en cours (samedi dernier)
                event_start = new Date(today);
                event_start.setDate(today.getDate() - daysToLastSunday - 1);
                event_start.setHours(0, 0, 0, 0);
                event_end = new Date(event_start);
                event_end.setDate(event_end.getDate() + 1);
                event_end.setHours(23, 59, 59, 999);
                
                // Weekend précédent
                baseline_start = new Date(event_start);
                baseline_start.setDate(baseline_start.getDate() - 7);
                baseline_end = new Date(event_end);
                baseline_end.setDate(baseline_end.getDate() - 7);
                break;

            case 'week':
                // Cette semaine vs semaine dernière (lundi 00h - dimanche 23h59)
                const daysSinceMonday = (dayOfWeek + 6) % 7; // 0=lundi, 6=dimanche
                
                event_start = new Date(today);
                event_start.setDate(today.getDate() - daysSinceMonday);
                event_start.setHours(0, 0, 0, 0);
                event_end = new Date(event_start);
                event_end.setDate(event_end.getDate() + 6);
                event_end.setHours(23, 59, 59, 999);
                
                baseline_start = new Date(event_start);
                baseline_start.setDate(baseline_start.getDate() - 7);
                baseline_end = new Date(event_end);
                baseline_end.setDate(baseline_end.getDate() - 7);
                break;

            case 'custom':
            default:
                // Mode personnalisé : ne rien changer
                return;
        }

        this.update({
            preset,
            baseline_start,
            baseline_end,
            event_start,
            event_end,
        });
    }

    /**
     * Valide que les périodes sont correctes
     */
    validatePeriods() {
        const { baseline_start, baseline_end, event_start, event_end } = this.data;
        
        if (!baseline_start || !baseline_end || !event_start || !event_end) {
            return { valid: false, error: 'Veuillez sélectionner toutes les dates' };
        }

        if (baseline_start >= baseline_end) {
            return { valid: false, error: 'La date de fin baseline doit être après la date de début' };
        }

        if (event_start >= event_end) {
            return { valid: false, error: 'La date de fin event doit être après la date de début' };
        }

        return { valid: true };
    }

    /**
     * Construit le payload pour l'API
     */
    buildPayload() {
        const { baseline_start, baseline_end, event_start, event_end, focus_entity_id, group_by, top_limit, top_sort_by } = this.data;

        return {
            selection_scope: 'summary_selected',
            focus_entity_id: focus_entity_id || undefined,
            group_by,
            comparison_periods: {
                baseline: {
                    start: baseline_start.toISOString(),
                    end: baseline_end.toISOString(),
                },
                event: {
                    start: event_start.toISOString(),
                    end: event_end.toISOString(),
                },
            },
            top_limit,
            top_sort_by,
        };
    }
}
export default HistoryState;