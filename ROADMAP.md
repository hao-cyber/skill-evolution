# Skill Evolution Roadmap

> Full lifecycle meta-skill: create → reflect → maturity → publish → search → select/merge → iterate.

## Completed

All core phases have been implemented as of 2026-02-25:

**Phase 1 — Core lifecycle loop:**
- Maturity assessment framework (`references/maturity.md`) + SKILL.md routing
- Agent variant selection decision tree (`references/search.md`)
- Fork counter fix — `increment_forks` RPC now called on fork
- `depends_on` populated from SKILL.md frontmatter

**Phase 2 — Supporting capabilities:**
- `merge.py` — download, diff, and publish merged variants
- `review.py` — publisher key authentication on `submit_review`
- `uninstall.py` — preview + delete local skills

**Phase 3 — Production hardening:**
- Search pagination (`--offset` + `has_more`)
- Migration idempotency (`CREATE OR REPLACE`)
- `match_skills` return schema unified (`audited_at`)

**Phase 4 — SKILL.md reshaped** for full lifecycle routing.

## Future Ideas

- Eval integration — hook `prompt-eval` into maturity signals
- Auto-merge suggestions when two variants have high complementarity score
- Popularity-based ranking in search (weighted installs + reviews)
- Skill dependency graph visualization
