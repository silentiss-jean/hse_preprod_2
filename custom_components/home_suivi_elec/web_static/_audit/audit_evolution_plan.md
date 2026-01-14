# Audit Phase 2 — Evolution plan

- Generated at: 2026-01-12T11:15:00.644323+00:00

## Opportunités (non bloquantes)

- Refactor complet theming (tokens + composants + manifest themes) piloté par customisation.
- Ajout d'effets UI (progress, badges, loaders) via variables.

## Contraintes

- Max 10 thèmes (existants inclus).
- Ne pas modifier la logique de calcul des coûts (UI seulement).

## Questions

- [theme-mechanism] Phase 2: mécanisme unique de thème (data-theme vs body class) ? (blocking=False)
- [theme-count] Phase 2: confirmer le nombre max de thèmes = 10 (existants inclus). (blocking=False)
- [no-cost-mutation] Phase 2: confirmer que tous les changements restent dans web_static (aucun Python/calcul). (blocking=False)
