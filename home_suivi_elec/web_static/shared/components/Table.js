// shared/components/Table.js
"use strict";

import { createElement } from '../utils/dom.js';

export class Table {
    /**
     * Crée une table générique
     * @param {Array} columns - Définition colonnes [{key, label, render}]
     * @param {Array} data - Données
     * @param {Object} options - Options
     */
    static create(columns, data, options = {}) {
        const table = createElement('table', { className: 'table' });

        // Header
        const thead = createElement('thead');
        const headerRow = createElement('tr');

        columns.forEach(col => {
            const th = createElement('th', {}, [col.label]);
            if (col.sortable) {
                th.style.cursor = 'pointer';
                th.addEventListener('click', () => {
                    if (options.onSort) {
                        options.onSort(col.key);
                    }
                });
            }
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Body
        const tbody = createElement('tbody');

        data.forEach((row, index) => {
            const tr = createElement('tr', {
                dataset: { index }
            });

            if (options.onRowClick) {
                tr.style.cursor = 'pointer';
                tr.addEventListener('click', () => options.onRowClick(row, index));
            }

            columns.forEach(col => {
                const td = createElement('td');

                if (col.render) {
                    const content = col.render(row[col.key], row, index);
                    if (content instanceof Node) {
                        td.appendChild(content);
                    } else {
                        td.innerHTML = content;
                    }
                } else {
                    td.textContent = row[col.key] || '-';
                }

                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        table.appendChild(tbody);

        return table;
    }
}
