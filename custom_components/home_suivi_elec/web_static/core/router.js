// router.js - Router pour modules migrés Phase 3

"use strict";

console.log("✅ Router Phase 3 - Chargement");

/**
 * Router pour gérer les modules migrés vers Phase 2/3
 * Ce fichier coexiste avec app.js pendant la migration
 */
class ModuleRouter {
  constructor() {
    this.currentTab = null;
    // ✅ AJOUT : 'history' dans les modules migrés
    this.migratedModules = new Set([
      'detection',
      'summary',
      'diagnostics',
      'configuration',
      'generation',
      'customisation',
      'migration',
      'history'  // 👈 NOUVEAU
    ]);
    this.loadedModules = new Set();
    this.moduleInstances = new Map(); // 👈 NOUVEAU : pour stocker les instances
    console.log("🎯 Router initialisé");
    console.log("📦 Modules migrés:", Array.from(this.migratedModules));
  }

  /**
   * Vérifie si un module est migré vers Phase 2/3
   */
  isMigrated(moduleName) {
    return this.migratedModules.has(moduleName);
  }

  /**
   * Charge un module migré à la demande (lazy loading)
   */
  async loadModule(moduleName) {
    // Si déjà chargé, ne rien faire
    if (this.loadedModules.has(moduleName)) {
      console.log(`⏭️ ${moduleName} déjà chargé`);
      
      // Si c'est le module history, rappeler init pour re-render
      if (moduleName === 'history' && this.moduleInstances.has('history')) {
        const instance = this.moduleInstances.get('history');
        await instance.init();
      }
      
      return;
    }

    // Si pas migré, laisser app.js le gérer
    if (!this.isMigrated(moduleName)) {
      console.log(`⏭️ ${moduleName} géré par app.js`);
      return;
    }

    console.log(`📦 Chargement lazy de ${moduleName}...`);
    try {
      const module = await import(`../features/${moduleName}/${moduleName}.js`);
      
      // Cas spécial pour history (pattern Class Module)
      if (moduleName === 'history') {
          const HistoryModule = module.default;  // ✅ CORRECTION
          const instance = new HistoryModule();
          await instance.init();
          this.moduleInstances.set('history', instance);
          this.loadedModules.add(moduleName);
          console.log(`✅ ${moduleName} chargé (Phase 3 - Module Class)`);
          return;
      }
      
      // Pattern classique (fonction loadXxx)
      const entryPoint = module[`load${this.capitalize(moduleName)}`];
      
      if (entryPoint) {
        await entryPoint();
        this.loadedModules.add(moduleName);
        console.log(`✅ ${moduleName} chargé (Phase 3)`);
      }
    } catch (e) {
      console.error(`❌ Erreur chargement ${moduleName}:`, e);
    }
  }

  /**
   * Capitalise la première lettre
   */
  capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  /**
   * Navigation intelligente
   * Charge via router si migré, sinon laisse app.js gérer
   */
  async navigateTo(tab) {
    // ✅ MAPPING : home → summary (car l'onglet HTML s'appelle 'home' mais le module s'appelle 'summary')
    const moduleName = tab === 'home' ? 'summary' : tab;
    
    this.currentTab = moduleName;
    console.log(`🔄 Router: Navigation vers ${tab} (module: ${moduleName})`);
    
    // Si le module est migré, le charger via le router
    if (this.isMigrated(moduleName)) {
      await this.loadModule(moduleName);
    } else {
      console.log(`⏭️ ${moduleName} géré par app.js (non migré)`);
    }
  }

  /**
   * Détruit un module (cleanup)
   */
  destroyModule(moduleName) {
    if (this.moduleInstances.has(moduleName)) {
      const instance = this.moduleInstances.get(moduleName);
      if (instance.destroy && typeof instance.destroy === 'function') {
        instance.destroy();
        console.log(`🗑️ ${moduleName} détruit`);
      }
      this.moduleInstances.delete(moduleName);
    }
    this.loadedModules.delete(moduleName);
  }
}

// Instance globale du router
const router = new ModuleRouter();

// Export pour debugging
window.__router = router;

function hookShowTabWhenReady() {
  if (typeof window.showTab !== "function") {
    setTimeout(hookShowTabWhenReady, 0);
    return;
  }

  const originalShowTab = window.showTab;

  // évite double-hook si rechargement/hot reload
  if (originalShowTab.__hseHooked) return;

  const wrapped = async function(tab) {
    console.log(`📍 showTab intercepté: ${tab}`);
    originalShowTab(tab);
    await router.navigateTo(tab);
  };
  wrapped.__hseHooked = true;

  window.showTab = wrapped;
  console.log("✅ showTab amélioré avec router (hook tardif)");
}

hookShowTabWhenReady();
document.addEventListener("DOMContentLoaded", hookShowTabWhenReady);



/**
 * Auto-chargement au démarrage (seulement modules migrés)
 */
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 Router: Initialisation terminée");
  console.log("💡 Utilisez window.__router pour debug");

  // ✅ Si l'onglet home est actif au démarrage, charger summary une fois
  const homeTab = document.getElementById('home');
  if (homeTab && homeTab.classList.contains('active')) {
    console.log("🔁 Router: auto-chargement initial de 'summary' (onglet home actif)");
    router.navigateTo('home');  // mappé vers summary par navigateTo
  }
});
