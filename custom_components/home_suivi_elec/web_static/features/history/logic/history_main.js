/**
 * @file history_main.js
 * @description Main controller for History feature - orchestrates views
 */

import HistoryAPI from '../history.api.js';
import TodayPanel from '../panels/today_panel.js';
import ComparisonController from './comparison_controller.js';

export class HistoryMainController {
    constructor() {
        this.currentView = 'today'; // 'today' or 'comparison'
        this.container = null;
        this.api = new HistoryAPI(); // ✅ Instance API partagée
        this.todayPanel = null;
        this.comparisonController = null;
    }

    /**
     * Initialize the history feature
     */
    async init(container) {
        this.container = container;
        
        console.log('[HISTORY-MAIN] Initializing...');

        // Create main layout
        this.container.innerHTML = `
            <div class="history-feature">
                <div class="history-header">
                    <h1>📊 Analyse de coûts</h1>
                    <div class="view-switcher">
                        <button id="view-today" class="view-btn active" data-view="today">
                            Aujourd'hui
                        </button>
                        <button id="view-comparison" class="view-btn" data-view="comparison">
                            Comparaisons
                        </button>
                    </div>
                </div>
                <div id="history-content" class="history-content"></div>
            </div>
        `;

        // Attach view switcher listeners
        this.attachViewSwitchers();

        // Load initial view (today)
        await this.switchView('today');
    }

    /**
     * Attach view switcher event listeners
     */
    attachViewSwitchers() {
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.target.dataset.view;
                this.switchView(view);
            });
        });

        // Listen for custom switchView events from child components
        this.container.addEventListener('switchView', (e) => {
            this.switchView(e.detail.view);
        });
    }

    /**
     * Switch between views
     */
    async switchView(view) {
        console.log(`[HISTORY-MAIN] Switching to view: ${view}`);
        
        this.currentView = view;

        // Update active button
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });

        // Get content container
        const contentEl = document.getElementById('history-content');
        if (!contentEl) {
            console.error('[HISTORY-MAIN] Content container not found');
            return;
        }

        // Clear content
        contentEl.innerHTML = '';

        // Render appropriate view
        if (view === 'today') {
            await this.renderTodayView(contentEl);
        } else if (view === 'comparison') {
            await this.renderComparisonView(contentEl);
        }
    }

    /**
     * Render "Aujourd'hui" view
     */
    async renderTodayView(container) {
        console.log('[HISTORY-MAIN] Rendering Today view...');
        
        this.todayPanel = new TodayPanel(container, this.api); // ✅ Passer l'API
        await this.todayPanel.init();
    }

    /**
     * Render comparison view
     */
    async renderComparisonView(container) {
        console.log('[HISTORY-MAIN] Rendering Comparison view...');
        
        this.comparisonController = new ComparisonController(container, this.api); // ✅ Passer l'API
        await this.comparisonController.init();
    }
}

export default HistoryMainController;
