/**
 * @file history.js
 * @description Entry point for History Analysis feature
 */

import HistoryMainController from './logic/history_main.js';

console.log('[HISTORY] Module loaded');

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    console.log('[HISTORY] DOM ready, initializing...');

    // Find the history container
    const container = document.getElementById('history-app');

    if (!container) {
        console.error('[HISTORY] Container #history-app not found');
        return;
    }

    // Create and initialize main controller
    const mainController = new HistoryMainController();
    await mainController.init(container);

    console.log('[HISTORY] Initialization complete');
});

