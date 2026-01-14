# Audit Phase 1 — Fix current

- Generated at: 2026-01-12T11:15:00.644109+00:00

## Bloquants

- missing_css_modules: 0
- undefined_css_variables_strict: 0
- undefined_css_variables_loose: 7
  - --hse-code-bg, --hse-code-text, --hse-scroll-thumb, --hse-scroll-thumb-hov, --hse-scroll-track, --hse-tooltip-bg, --hse-tooltip-text
- broken_index_links: 0

## Warnings

- duplicate_index_links: 0
- unused_css_variables: 34

## Notes

- Phase 1 ne propose que des actions low-risk (créations vides + alias neutres + liens CSS manquants).
- Les variables undefined “loose” sont des candidats faux-positifs (règles CSS potentiellement inatteignables).
