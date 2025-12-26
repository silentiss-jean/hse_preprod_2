// auth.js - Gestion auth via contexte Home Assistant
"use strict";

let HA_TOKEN = null;

/**
 * Récupère le token depuis le contexte Home Assistant (panel iframe)
 */
export async function initAuth() {
  try {
    // Essayer de récupérer depuis le contexte HA
    const hass = window?.parent?.customElements?.get?.('home-assistant')?.hass;
    
    if (hass?.auth?.data?.access_token) {
      HA_TOKEN = hass.auth.data.access_token;
      console.log("[AUTH] ✅ Token récupéré depuis contexte HA");
      return true;
    }
    
    // Fallback : Mode sans auth (requires_auth = False)
    console.warn("[AUTH] ⚠️ Token HA non disponible, mode sans auth");
    return false;
  } catch (err) {
    console.error("[AUTH] ❌ Erreur récupération token:", err);
    return false;
  }
}

export function getToken() {
  return HA_TOKEN;
}

/**
 * Fetch avec authentification automatique
 * ✅ Ajoute Bearer token si disponible
 * ✅ Ajoute credentials: same-origin
 * ✅ Initialise auth automatiquement si nécessaire
 * 
 * @param {string} url - URL à appeler
 * @param {Object} options - Options fetch
 * @returns {Promise<Response>} - Response brute (non parsée)
 */
export async function fetchAuth(url, options = {}) {
  // Auto-init si token absent
  if (!HA_TOKEN) {
    await initAuth();
  }
  
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };
  
  if (HA_TOKEN) {
    headers["Authorization"] = `Bearer ${HA_TOKEN}`;
  }
  
  return fetch(url, {
    credentials: "same-origin",  // ✅ AJOUTÉ (pour cookies session)
    ...options,
    headers
  });
}

/**
 * ✨ NOUVEAU : Fetch avec authentification + parsing JSON automatique
 * Équivalent au fetchJSON() de configuration.api.js
 * 
 * @param {string} url - URL à appeler
 * @param {Object} options - Options fetch
 * @returns {Promise<Object>} - Données JSON parsées
 * @throws {Error} Si la requête échoue (status !== 2xx)
 */
export async function fetchAuthJSON(url, options = {}) {
  const response = await fetchAuth(url, options);
  
  if (!response.ok) {
    // Format d'erreur similaire à configuration.api.js
    const cleanUrl = url.split("?")[0].split("#")[0].replace(location.origin, "");
    throw new Error(`${cleanUrl} failed with status ${response.status}`);
  }
  
  return await response.json();
}
