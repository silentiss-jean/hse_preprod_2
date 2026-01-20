/**
 * @file period_selector_panel.js
 * @description Period selector panel with presets + custom date ranges, no inline styles.
 * UI is styled via history.css tokens/classes.
 */

export default class PeriodSelectorPanel {
  /**
   * @param {HTMLElement} container
   * @param {{
   *  initialType?: 'today_yesterday'|'week_lastweek'|'weekend_lastweekend'|'custom',
   *  onAnalyze?: (params: { baseline_start: string, baseline_end: string, event_start: string, event_end: string, type: string }) => void,
   * }} options
   */
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.type = options.initialType || 'today_yesterday';
  }

  init() {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="history-period-selector" data-period-type="${this.type}">
        <div class="presets-row">
          <button type="button" class="preset-btn" data-type="today_yesterday">Aujourd'hui vs Hier</button>
          <button type="button" class="preset-btn" data-type="week_lastweek">Cette semaine vs Dernière</button>
          <button type="button" class="preset-btn" data-type="weekend_lastweekend">Weekend vs Weekend dernier</button>
          <button type="button" class="preset-btn" data-type="custom">Personnalisé</button>
        </div>

        <div class="custom-dates-container" id="hse-custom-dates" hidden>
          <div class="date-group">
            <h4>Période de référence</h4>
            <div class="date-inputs-row">
              <label for="hse-baseline-start">Début</label>
              <input id="hse-baseline-start" class="date-input" type="datetime-local" />
            </div>
            <div class="date-inputs-row">
              <label for="hse-baseline-end">Fin</label>
              <input id="hse-baseline-end" class="date-input" type="datetime-local" />
            </div>
          </div>

          <div class="date-group">
            <h4>Période à comparer</h4>
            <div class="date-inputs-row">
              <label for="hse-event-start">Début</label>
              <input id="hse-event-start" class="date-input" type="datetime-local" />
            </div>
            <div class="date-inputs-row">
              <label for="hse-event-end">Fin</label>
              <input id="hse-event-end" class="date-input" type="datetime-local" />
            </div>
          </div>
        </div>

        <button type="button" class="btn-analyze" id="hse-period-analyze">🚀 Lancer l'analyse</button>
      </div>
    `;

    this.rootEl = this.container.querySelector('.history-period-selector');
    this.customEl = this.container.querySelector('#hse-custom-dates');

    this._bind();
    this._setType(this.type);
  }

  _bind() {
    this.container.querySelectorAll('.preset-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.type;
        if (!type) return;
        this._setType(type);
      });
    });

    this.container.querySelector('#hse-period-analyze')?.addEventListener('click', () => {
      const params = this._buildParams();
      if (!params) return;

      if (typeof this.options.onAnalyze === 'function') {
        this.options.onAnalyze(params);
      }

      this.container.dispatchEvent(
        new CustomEvent('periodAnalyze', {
          detail: params,
          bubbles: true,
        })
      );
    });
  }

  _setType(type) {
    this.type = type;

    // Active button
    this.container.querySelectorAll('.preset-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.type === type);
    });

    // Toggle custom dates
    if (this.customEl) this.customEl.hidden = type !== 'custom';
    if (this.rootEl) this.rootEl.dataset.periodType = type;

    this.container.dispatchEvent(
      new CustomEvent('periodChange', {
        detail: { type },
        bubbles: true,
      })
    );
  }

  _buildParams() {
    if (this.type === 'custom') {
      const baselineStart = this.container.querySelector('#hse-baseline-start')?.value;
      const baselineEnd = this.container.querySelector('#hse-baseline-end')?.value;
      const eventStart = this.container.querySelector('#hse-event-start')?.value;
      const eventEnd = this.container.querySelector('#hse-event-end')?.value;

      if (!baselineStart || !baselineEnd || !eventStart || !eventEnd) {
        this.container.dispatchEvent(
          new CustomEvent('periodError', {
            detail: { message: 'Veuillez renseigner toutes les dates' },
            bubbles: true,
          })
        );
        return null;
      }

      return {
        type: this.type,
        baseline_start: new Date(baselineStart).toISOString(),
        baseline_end: new Date(baselineEnd).toISOString(),
        event_start: new Date(eventStart).toISOString(),
        event_end: new Date(eventEnd).toISOString(),
      };
    }

    const periods = this._calculatePeriods(this.type);
    return { type: this.type, ...periods };
  }

  _calculatePeriods(type) {
    const now = new Date();
    let baseline_start, baseline_end, event_start, event_end;

    switch (type) {
      case 'today_yesterday':
        event_start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        event_end = now;
        baseline_start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0);
        baseline_end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59);
        break;

      case 'week_lastweek': {
        const dayOfWeek = now.getDay() || 7;
        const mondayThisWeek = new Date(now);
        mondayThisWeek.setDate(now.getDate() - dayOfWeek + 1);
        mondayThisWeek.setHours(0, 0, 0, 0);

        event_start = mondayThisWeek;
        event_end = now;

        const mondayLastWeek = new Date(mondayThisWeek);
        mondayLastWeek.setDate(mondayThisWeek.getDate() - 7);

        baseline_start = mondayLastWeek;
        baseline_end = new Date(mondayLastWeek);
        baseline_end.setDate(mondayLastWeek.getDate() + 6);
        baseline_end.setHours(23, 59, 59);
        break;
      }

      case 'weekend_lastweekend': {
        const today = now.getDay();
        let saturdayThisWeekend = new Date(now);

        if (today === 0) {
          saturdayThisWeekend.setDate(now.getDate() - 1);
        } else if (today === 6) {
          saturdayThisWeekend.setDate(now.getDate());
        } else {
          saturdayThisWeekend.setDate(now.getDate() + (6 - today));
        }
        saturdayThisWeekend.setHours(0, 0, 0, 0);

        event_start = saturdayThisWeekend;
        event_end = now;

        const saturdayLastWeekend = new Date(saturdayThisWeekend);
        saturdayLastWeekend.setDate(saturdayThisWeekend.getDate() - 7);

        baseline_start = saturdayLastWeekend;
        baseline_end = new Date(saturdayLastWeekend);
        baseline_end.setDate(saturdayLastWeekend.getDate() + 1);
        baseline_end.setHours(23, 59, 59);
        break;
      }

      default:
        event_start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        event_end = now;
        baseline_start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0);
        baseline_end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59);
    }

    return {
      baseline_start: baseline_start.toISOString(),
      baseline_end: baseline_end.toISOString(),
      event_start: event_start.toISOString(),
      event_end: event_end.toISOString(),
    };
  }
}
