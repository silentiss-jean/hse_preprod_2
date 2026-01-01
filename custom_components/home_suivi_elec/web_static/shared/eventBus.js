// js/eventBus.js
"use strict";

const listeners = {};

/**
 * Enregistre un handler pour un event.
 * @param {string} event
 * @param {(data:any)=>void} callback
 */
export function on(event, callback) {
  if (!listeners[event]) listeners[event] = [];
  listeners[event].push(callback);
}

/**
 * Désenregistre un handler pour un event.
 * @param {string} event
 * @param {(data:any)=>void} callback
 */
export function off(event, callback) {
  if (!listeners[event]) return;
  const idx = listeners[event].indexOf(callback);
  if (idx >= 0) listeners[event].splice(idx, 1);
}

/**
 * Emet un event à tous les handlers.
 * @param {string} event
 * @param {any} data
 */
export function emit(event, data) {
  (listeners[event] || []).forEach(cb => {
    try { cb(data); } catch (e) { console.error("[eventBus] handler error", event, e); }
  });
}

/**
 * Enregistre un handler one-shot.
 * @param {string} event
 * @param {(data:any)=>void} callback
 */
export function once(event, callback) {
  const wrapper = (data) => {
    try { callback(data); } finally { off(event, wrapper); }
  };
  on(event, wrapper);
}

export const eventBus = { on, off, once, emit };
export default { on, off, once, emit };
