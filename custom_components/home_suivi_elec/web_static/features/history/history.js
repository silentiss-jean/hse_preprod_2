/**
 * Module Analyse de coûts (History)
 * Point d'entrée du module pour comparaison baseline vs event
 */
import HistoryAPI from './history.api.js';
import HistoryView from './history.view.js';
import HistoryState from './history.state.js';

class HistoryModule {
    constructor() {
        this.api = new HistoryAPI();
        this.state = new HistoryState();
        this.view = null;
    }

    async init() {
        console.log('[HISTORY] Initializing History module...');
        
        this.view = new HistoryView(this.state, this.api);
        await this.view.init();
        
        console.log('[HISTORY] ✅ History module initialized');
    }

    destroy() {
        if (this.view) {
            this.view.destroy();
        }
        console.log('[HISTORY] Module destroyed');
    }
}

export default HistoryModule;
