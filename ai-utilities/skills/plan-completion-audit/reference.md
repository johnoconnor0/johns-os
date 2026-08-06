# Plan Completion Audit — Reference Index

Dense material lives under `references/`. Each file is loaded only when it applies,
which is the same principle the check families themselves run on.

| File | Covers | Loaded when |
|---|---|---|
| [`references/check-families.md`](references/check-families.md) | The family registry, the five outcomes, the two predicates, the stack ladder, and how to add a family. | Always worth reading before changing the audit. |
| [`references/postgres-audit-guide.md`](references/postgres-audit-guide.md) | Schema, functions, row level security, triggers, storage and edge functions — the Postgres and Supabase specifics. | The `data-layer` family applies **and** the detected dialect is Postgres. |

There is deliberately no per-phase index any more. Phases were a fixed list; families
are chosen per repository, so the reference that matters is the registry.

When a new family needs dense reference content, add a file here and a row above.
