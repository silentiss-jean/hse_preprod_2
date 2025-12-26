// js/stateModule.js
"use strict";

import { emit } from "./eventBus.js";

const initialState = {
  reference: { use_external: false, external_capteur: "", consommation_externe: null, mode: "capteur" },
  uiFold: { config: false, reference: false, duplicates: false },
  duplicates: { ignored: [], selected: {} },
  tarifs: {
    abonnement_ht: 0, abonnement_ttc: 0, type_contrat: "fixe",
    tarifHP: 0, tarifHC: 0, heuresHPDebut: "", heuresHPFin: ""
  }
};

class StateModule {
  constructor() {
    this.state = { ...initialState };
  }

  get(domain) {
    return this.state[domain];
  }

  set(domain, data) {
    const prev = this.state[domain] || {};
    this.state[domain] = { ...prev, ...data };
    emit("state:changed", { domain, data: this.state[domain] });
  }

  replace(domain, data) {
    this.state[domain] = data;
    emit("state:changed", { domain, data });
  }

  hydrate(externalState) {
    this.state = {
      ...this.state,
      ...externalState,
      reference: { ...this.state.reference, ...(externalState?.reference || {}) },
      uiFold: { ...this.state.uiFold, ...(externalState?.uiFold || {}) },
      duplicates: { ...this.state.duplicates, ...(externalState?.duplicates || {}) },
      tarifs: { ...this.state.tarifs, ...(externalState?.tarifs || {}) },
    };
    emit("state:hydrated", { full: this.state });
  }

  reset() {
    this.state = { ...initialState };
    emit("state:reset", { full: this.state });
  }
}

const stateModule = new StateModule();
export default stateModule;
