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
    // ✅ AJOUT : 'diagnostics' dans les modules migrés
    this.migratedModules = new Set(['detection', 'summary', 'diagnostics', 'configuration', 'generation', 'customisation', 'migration']);
    this.loadedModules = new Set();
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
      console.log(` ⏭️ ${moduleName} déjà chargé`);
      return;
    }

    // Si pas migré, laisser app.js le gérer
    if (!this.isMigrated(moduleName)) {
      console.log(` ⏭️ ${moduleName} géré par app.js`);
      return;
    }

    console.log(` 📦 Chargement lazy de ${moduleName}...`);
    try {
      const module = await import(`../features/${moduleName}/${moduleName}.js`);
      const entryPoint = module[`load${this.capitalize(moduleName)}`];
      
      if (entryPoint) {
        await entryPoint();
        this.loadedModules.add(moduleName);
        console.log(` ✅ ${moduleName} chargé (Phase 3)`);
      }
    } catch (e) {
      console.error(` ❌ Erreur chargement ${moduleName}:`, e);
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
      console.log(` ⏭️ ${moduleName} géré par app.js (non migré)`);
    }
  }
}

// Instance globale du router
const router = new ModuleRouter();

// Export pour debugging
window.__router = router;

/**
 * Intercepter showTab pour utiliser le router si nécessaire
 * ⚠️ Ne remplace PAS showTab, juste l'améliore
 */
const originalShowTab = window.showTab;
if (originalShowTab) {
  window.showTab = async function(tab) {
    console.log(`📍 showTab intercepté: ${tab}`);
    
    // Appeler l'original (app.js)
    originalShowTab(tab);
    
    // Puis charger via router si migré
    await router.navigateTo(tab);
  };
  console.log("✅ showTab amélioré avec router");
}

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
