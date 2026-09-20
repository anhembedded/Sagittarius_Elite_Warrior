---
description: Naming rules revealing intent and preserving domain contract clarity.
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

# SYSTEM PROMPT: CODE NAMING RULES

1. **Reveal Intent:** Names MUST clearly reveal intent; avoid vague, generic, or misleading identifiers. `[eye]`
2. **Domain Contract Alignment:** Use canonical domain terms matching vocabulary definitions (`Docs/VOCABULARY/README.md`); avoid inventing alternative terminology. `[review: A1]`
3. **Parts of Speech:** Class names must be nouns or noun phrases (`OrderBook`, `FillPricing`); method and function names must be verbs or verb phrases (`calculate_fee`, `submit_order`). `[review: A1]`
4. **Single Vocabulary per Concept:** Choose one word for one abstract concept across the codebase (e.g. do not mix `fetch`, `retrieve`, `get` for the same operational semantic). `[review: A1]`


