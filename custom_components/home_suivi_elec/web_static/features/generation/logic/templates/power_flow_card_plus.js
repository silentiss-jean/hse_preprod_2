"use strict";

function yaml_quote(value) {
  const str = String(value ?? "");
  const escaped = str.replace(/"/g, "\\\"");
  return `"${escaped}"`;
}

function push_cost_secondary_info(lines, indent, entity_id) {
  if (!entity_id) {
    lines.push(`${indent}secondary_info: {}`);
    return;
  }

  lines.push(`${indent}secondary_info:`);
  lines.push(`${indent}  entity: ${entity_id}`);
  lines.push(`${indent}  unit_of_measurement: €`);
  lines.push(`${indent}  decimals: 2`);
}

function push_yaml_block(lines, indent, key, value) {
  if (value === undefined || value === null) return;
  const str = String(value).trim();
  if (!str) return;
  lines.push(`${indent}${key}: ${yaml_quote(str)}`);
}

/**
 * Génère une carte unique power-flow-card-plus alignée sur le modèle fourni.
 *
 * options attendu:
 * - title: string
 * - grid: { power_entity: string }
 * - home: { power_entity?: string, cost_entity?: string }
 * - individuals: Array<{ power_entity: string, cost_entity?: string, name?: string }>
 */
export function build_power_flow_card_plus_yaml(options = {}) {
  const title = (options.title || "").trim();

  const grid = options.grid || {};
  const home = options.home || {};

  const grid_power_entity = String(grid.power_entity || "").trim();
  const home_power_entity = String(home.power_entity || "").trim();
  const home_cost_entity = String(home.cost_entity || "").trim();

  const individuals = Array.isArray(options.individuals) ? options.individuals : [];

  const lines = [];

  lines.push("type: custom:power-flow-card-plus");
  lines.push("entities:");

  // Battery (placeholder)
  lines.push("  battery:");
  lines.push("    entity: \"\"");
  lines.push("    state_of_charge: \"\"");

  // Grid (required)
  lines.push("  grid:");
  lines.push("    secondary_info: {}");
  lines.push("    entity:");
  lines.push(`      consumption: ${grid_power_entity}`);
  lines.push("    invert_state: false");
  lines.push("    name: Compteur");
  lines.push("    icon: mdi:generator-stationary");
  lines.push("    color_icon: true");
  lines.push("    color_circle: production");
  lines.push("    display_state: one_way_no_zero");

  // Home (optional)
  lines.push("  home:");
  push_cost_secondary_info(lines, "    ", home_cost_entity);
  if (title) {
    lines.push(`    name: ${yaml_quote(title)}`);
  }
  lines.push("    icon: mdi:home");
  lines.push(`    entity: ${home_power_entity ? home_power_entity : "\"\""}`);
  lines.push("    subtract_individual: false");
  lines.push("    override_state: true");

  // Individuals
  lines.push("  individual:");

  const safe_individuals = individuals
    .map((row) => ({
      power_entity: String(row?.power_entity || "").trim(),
      cost_entity: String(row?.cost_entity || "").trim(),
      name: String(row?.name || "").trim(),
    }))
    .filter((row) => row.power_entity);

  if (safe_individuals.length === 0) {
    lines.push("    []");
    return lines.join("\n") + "\n";
  }

  for (const row of safe_individuals) {
    lines.push(`    - entity: ${row.power_entity}`);
    push_cost_secondary_info(lines, "      ", row.cost_entity);
    push_yaml_block(lines, "      ", "name", row.name);
    lines.push("      display_zero: true");
    lines.push("      unit_white_space: true");
    lines.push("      calculate_flow_rate: true");
    lines.push("      show_direction: true");
    lines.push("      use_metadata: true");
  }

  return lines.join("\n") + "\n";
}
