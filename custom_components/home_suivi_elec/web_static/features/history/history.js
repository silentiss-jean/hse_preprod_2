/**
 * @file history.js
 * @description Entry point for History Analysis feature
 */

import HistoryMainController from './logic/history_main.js';

console.log('[HISTORY] Module loaded');

/**
 * HistoryModule - Classe compatible avec le router Phase 3
 */
class HistoryModule {
    constructor() {
        this.mainController = null;
    }

    async init() {
        console.log('[HISTORY] Initializing History module...');

        // Find the history container
        const container = document.getElementById('history-app');

        if (!container) {
            console.error('[HISTORY] Container #history-app not found');
            return;
        }

        // Create and initialize main controller
        this.mainController = new HistoryMainController();
        await this.mainController.init(container);

        console.log('[HISTORY] ✅ Initialization complete');
    }

    destroy() {
        console.log('[HISTORY] Module destroyed');
        if (this.mainController) {
            // Cleanup if needed
            this.mainController = null;
        }
    }
}

// ✅ EXPORT DEFAULT pour le router
export default HistoryModule;

