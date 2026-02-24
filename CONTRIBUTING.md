# Contributing to Skill Evolution

## Publishing a Skill

The easiest way to contribute is to publish a skill you've built:

1. Create a skill following the structure in `references/structure.md`
2. Test it in your own project
3. Run `publish.py --skill-name <name>` to preview (default behavior, no upload)
4. Fix any sanitize warnings (secrets, hardcoded paths)
5. Publish with `publish.py --skill-name <name> --yes`

Your skill will be immediately searchable by any agent using the registry.

## Improving an Existing Skill

When you fork and improve someone else's skill:

1. Install the skill: `install.py --name <name>`
2. Modify it locally for your use case
3. Publish as your variant: `publish.py --skill-name <name> --variant <your-name> --yes`

The system automatically tracks lineage via `parent_id`.

## Skill Quality Guidelines

Good skills share these traits:

- **SKILL.md ≤ 300 lines** — routing layer only, details in references/
- **Clear triggers** — description says exactly when the skill should activate
- **Scripts work standalone** — `--help` works, exits with proper codes
- **No hardcoded secrets** — use `requires_env` to declare needed variables
- **Tested in production** — at least one real use before publishing

## Code Contributions

For changes to the scripts themselves (publish.py, search.py, install.py, uninstall.py, merge.py, review.py, audit.py):

1. Fork this repo
2. Make your changes
3. Test: run `--help` on all modified scripts to verify they load
4. Submit a PR with what you changed and why

## Bug Reports

Open an issue with:
- What you tried to do
- What happened instead
- The error message (scripts prefix errors with `ERROR:`)

## Registry Setup

Want to run your own registry? See `setup.sql` — it's one file, takes 5 minutes on Supabase free tier.
