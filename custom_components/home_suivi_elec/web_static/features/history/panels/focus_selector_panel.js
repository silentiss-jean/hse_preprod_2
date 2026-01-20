/**
 * @file focus_selector_panel.js
 * @description Focus selector panel (autocomplete) with no inline styles.
 * UI is styled via history.css tokens/classes.
 */

export default class FocusSelectorPanel {
  /**
   * @param {HTMLElement} container
   * @param {{
   *  entities?: Array<{ entity_id: string, display_name?: string }>,
   *  placeholder?: string,
   *  label?: string,
   *  onSelect?: (entityId: string) => void,
   * }} options
   */
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.entities = Array.isArray(options.entities) ? options.entities : [];

    this._onDocClick = this._onDocClick.bind(this);
  }

  init() {
    if (!this.container) return;

    const label = this.options.label || '🎯 Focus capteur';
    const placeholder = this.options.placeholder || 'Rechercher un capteur…';

    this.container.innerHTML = `
      <div class="focus-selector-panel">
        <label class="focus-label" for="hse-focus-input">${label}</label>
        <div class="autocomplete-wrapper">
          <input
            id="hse-focus-input"
            class="focus-input"
            type="text"
            autocomplete="off"
            placeholder="${placeholder}"
            aria-label="${label}"
          />
          <ul id="hse-focus-dropdown" class="autocomplete-dropdown" hidden></ul>
        </div>
      </div>
    `;

    this.inputEl = this.container.querySelector('#hse-focus-input');
    this.dropdownEl = this.container.querySelector('#hse-focus-dropdown');

    if (!this.inputEl || !this.dropdownEl) return;

    this.inputEl.addEventListener('input', () => this._renderDropdown());
    this.inputEl.addEventListener('focus', () => this._renderDropdown());
    document.addEventListener('click', this._onDocClick);

    // First render (empty)
    this._renderDropdown();
  }

  destroy() {
    document.removeEventListener('click', this._onDocClick);
  }

  setEntities(entities) {
    this.entities = Array.isArray(entities) ? entities : [];
    this._renderDropdown();
  }

  _onDocClick(e) {
    if (!this.container) return;
    if (!this.container.contains(e.target)) this._hideDropdown();
  }

  _hideDropdown() {
    if (this.dropdownEl) this.dropdownEl.hidden = true;
  }

  _normalize(s) {
    return String(s || '').toLowerCase().trim();
  }

  _filterEntities(query) {
    const q = this._normalize(query);
    if (!q) return this.entities.slice(0, 50);

    return this.entities
      .map((e) => ({
        entity_id: e.entity_id,
        display_name: e.display_name || e.entity_id,
      }))
      .filter((e) => {
        const name = this._normalize(e.display_name);
        const id = this._normalize(e.entity_id);
        return name.includes(q) || id.includes(q);
      })
      .slice(0, 50);
  }

  _renderDropdown() {
    if (!this.inputEl || !this.dropdownEl) return;

    const items = this._filterEntities(this.inputEl.value);

    if (items.length === 0) {
      this.dropdownEl.innerHTML = '<li class="dropdown-item empty">Aucun résultat</li>';
      this.dropdownEl.hidden = false;
      return;
    }

    this.dropdownEl.innerHTML = items
      .map(
        (e) => `
        <li class="dropdown-item" data-entity-id="${e.entity_id}">
          <strong>${e.display_name}</strong>
          <span class="entity-id-small">${e.entity_id}</span>
        </li>
      `
      )
      .join('');

    this.dropdownEl.hidden = false;

    this.dropdownEl.querySelectorAll('.dropdown-item[data-entity-id]').forEach((li) => {
      li.addEventListener('click', () => {
        const entityId = li.dataset.entityId;
        if (!entityId) return;

        const display = li.querySelector('strong')?.textContent || entityId;
        this.inputEl.value = display;
        this._hideDropdown();

        // Callback
        if (typeof this.options.onSelect === 'function') {
          this.options.onSelect(entityId);
        }

        // Event
        this.container.dispatchEvent(
          new CustomEvent('focusSelected', {
            detail: { entityId },
            bubbles: true,
          })
        );
      });
    });
  }
}
