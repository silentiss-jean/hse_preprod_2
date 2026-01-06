/**
 * @file history_main.js
 * @description Main controller for History feature - orchestrates views
 */

import HistoryAPI from '../history.api.js';
import TodayPanel from '../panels/today_panel.js';
import { ComparisonController } from './comparison_controller.js';

export class HistoryMainController {
    constructor() {
        this.api = new HistoryAPI();
        this.currentView = 'today'; // 'today' or 'comparison'
        this.container = null;
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
        if (this.currentView === view) return;

        console.log(`[HISTORY-MAIN] Switching to view: ${view}`);

        this.currentView = view;

        // Update active button
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });

        // Get content container
        const contentEl = document.getElementById('history-content');
        if (!contentEl) return;

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
        container.innerHTML = '<div id="today-container"></div>';
        const todayContainer = document.getElementById('today-container');

        if (!todayContainer) return;

        this.todayPanel = new TodayPanel(todayContainer, this.api);
        await this.todayPanel.render();
    }

    /**
     * Render comparison view
     */
    async renderComparisonView(container) {
        container.innerHTML = '<div id="comparison-container"></div>';
        const comparisonContainer = document.getElementById('comparison-container');

        if (!comparisonContainer) return;

        this.comparisonController = new ComparisonController(comparisonContainer, this.api);
        await this.comparisonController.render('today_yesterday');
    }
}

export default HistoryMainController;
