"use strict";

function yaml_quote(value) {
  const str = String(value ?? "");
  const escaped = str.replace(/"/g, "\\\"");
  return `"${escaped}"`;
}

function push_secondary_info(lines, indent, entity_id) {
  if (!entity_id) return;
  lines.push(`${indent}secondary_info:`);
  lines.push(`${indent}  entity: ${entity_id}`);
  lines.push(`${indent}  unit_of_measurement: "€"`);
  lines.push(`${indent}  decimals: 2`);
}

/**
 * Génère une carte unique power-flow-card-plus.
 *
 * options attendu:
 * - title: string
 * - home: { power_entity: string, cost_entity?: string }
 * - individuals: Array<{ power_entity: string, cost_entity?: string }>
 */
export function build_power_flow_card_plus_yaml(options = {}) {
  const title = (options.title || "").trim();
  const home = options.home || {};
  const individuals = Array.isArray(options.individuals) ? options.individuals : [];

  const home_power_entity = String(home.power_entity || "").trim();
  const home_cost_entity = String(home.cost_entity || "").trim();

  const lines = [];
  lines.push("type: custom:power-flow-card-plus");
  if (title) {
    lines.push(`title: ${yaml_quote(title)}`);
  }

  lines.push("entities:");
  lines.push("  home:");
  lines.push(`    entity: ${home_power_entity}`);
  push_secondary_info(lines, "    ", home_cost_entity);

  lines.push("  individual:");

  const safe_individuals = individuals
    .map((row) => ({
      power_entity: String(row?.power_entity || "").trim(),
      cost_entity: String(row?.cost_entity || "").trim(),
    }))
    .filter((row) => row.power_entity);

  if (safe_individuals.length === 0) {
    lines.push("    []");
    return lines.join("\n") + "\n";
  }

  for (const row of safe_individuals) {
    lines.push("    - entity: " + row.power_entity);
    push_secondary_info(lines, "      ", row.cost_entity);
  }

  return lines.join("\n") + "\n";
}
