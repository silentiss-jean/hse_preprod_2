// shared/api/httpClient.js
"use strict";

/**
 * Client HTTP générique pour Home Suivi Élec.
 */
export class HttpClient {
  constructor(baseURL = "") {
    this.baseURL = baseURL;
    this.defaultOptions = {
      headers: {
        "Content-Type": "application/json",
      },
    };
  }

  async request(endpoint, options = {}, retries = 3) {
    const isAbsolute =
      typeof endpoint === "string" &&
      (endpoint.startsWith("http://") ||
        endpoint.startsWith("https://") ||
        endpoint.startsWith("/"));

    const url = isAbsolute ? endpoint : `${this.baseURL}${endpoint}`;
    const config = { ...this.defaultOptions, ...options };

    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const response = await fetch(url, config);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
          return await response.json();
        }

        // YAML ou texte brut
        return await response.text();
      } catch (error) {
        console.error(`Tentative ${attempt}/${retries} échouée:`, error);
        if (attempt === retries) {
          throw error;
        }
        await this.delay(Math.pow(2, attempt) * 1000);
      }
    }
  }

  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(url, { method: "GET" });
  }

  async post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async download(endpoint, data, filename) {
    try {
      const content = await this.post(endpoint, data);
      const blob = new Blob([content], { type: "text/yaml" });
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      URL.revokeObjectURL(url);
      return true;
    } catch (error) {
      console.error("Erreur téléchargement:", error);
      throw error;
    }
  }

  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// Instance globale réutilisable
export const httpClient = new HttpClient();
