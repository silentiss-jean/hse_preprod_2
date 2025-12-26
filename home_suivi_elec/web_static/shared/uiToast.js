// uiToast.js — Mini toasts non bloquants
"use strict";

const TOAST_CONTAINER_ID = "hse-toast-container";

function ensureContainer() {
  let el = document.getElementById(TOAST_CONTAINER_ID);
  if (el) return el;
  el = document.createElement("div");
  el.id = TOAST_CONTAINER_ID;
  el.style.position = "fixed";
  el.style.zIndex = "9999";
  el.style.right = "16px";
  el.style.bottom = "16px";
  el.style.display = "flex";
  el.style.flexDirection = "column-reverse";
  el.style.gap = "8px";
  document.body.appendChild(el);
  return el;
}

function colorFor(type) {
  switch ((type || "info").toLowerCase()) {
    case "success": return "#15a34a";
    case "error": return "#dc2626";
    case "warning": return "#f59e0b";
    default: return "#2563eb"; // info
  }
}

export function showToast(message, { type = "info", timeout = 3000 } = {}) {
  const box = document.createElement("div");
  const bg = colorFor(type);
  box.style.background = "#111827";
  box.style.color = "white";
  box.style.border = `1px solid ${bg}`;
  box.style.boxShadow = "0 6px 18px rgba(0,0,0,0.3)";
  box.style.borderRadius = "8px";
  box.style.padding = "10px 12px";
  box.style.minWidth = "220px";
  box.style.maxWidth = "380px";
  box.style.fontSize = "14px";
  box.style.lineHeight = "1.35";
  box.style.position = "relative";
  box.style.overflow = "hidden";

  const bar = document.createElement("div");
  bar.style.position = "absolute";
  bar.style.left = "0";
  bar.style.top = "0";
  bar.style.height = "3px";
  bar.style.width = "100%";
  bar.style.background = bg;
  box.appendChild(bar);

  const text = document.createElement("div");
  text.textContent = message || "";
  box.appendChild(text);

  const close = document.createElement("button");
  close.textContent = "×";
  close.title = "Fermer";
  close.style.position = "absolute";
  close.style.top = "4px";
  close.style.right = "8px";
  close.style.border = "none";
  close.style.background = "transparent";
  close.style.color = "white";
  close.style.fontSize = "16px";
  close.style.cursor = "pointer";
  close.addEventListener("click", () => box.remove());
  box.appendChild(close);

  const container = ensureContainer();
  container.appendChild(box);

  if (timeout && timeout > 0) {
    const start = Date.now();
    const tick = () => {
      const elapsed = Date.now() - start;
      const p = Math.max(0, 1 - elapsed / timeout);
      bar.style.transform = `scaleX(${p})`;
      bar.style.transformOrigin = "left";
      if (elapsed >= timeout) {
        box.remove();
      } else {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);
  }

  return box;
}

export const toast = {
  info: (msg, opts={}) => showToast(msg, { ...opts, type: "info" }),
  success: (msg, opts={}) => showToast(msg, { ...opts, type: "success" }),
  warning: (msg, opts={}) => showToast(msg, { ...opts, type: "warning" }),
  error: (msg, opts={}) => showToast(msg, { ...opts, type: "error" }),
};
