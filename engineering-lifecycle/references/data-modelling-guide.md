# Data Modelling Guide

The deliverable is a schema file, not a description of one. `schema.sql` is the
source of truth; `data-model.json` and `erd.mmd` are generated from it and must
never be hand-edited.

An entity list written only as prose cannot be read back by anything, so later
backend work re-derives the model from whatever code is nearby and the schema
drifts one query at a time.

## Required Considerations

- canonical entity names,
- source of truth,
- lifecycle and status values,
- relationships and cardinality,
- ownership and permissions,
- sensitive fields,
- retention and deletion,
- import/export paths,
- migration and rollback risk.

Use existing schemas and migrations as evidence. Mark unknowns explicitly.

## Design Order

Write the schema in dependency order, because that is also the order it must run:

1. Extensions and enums/types.
2. Tables, parents before children.
3. Constraints (primary keys, foreign keys, unique, check).
4. Indexes for the query patterns that actually exist.
5. Row level security: enable, then write policies.
6. Functions and triggers.
7. Seed data.

## Normalisation

Normalise to third normal form by default. Denormalise only for a measured read
pattern, and record the reason in `entity-model.md`. "It felt faster" is not a
reason; a named query with a known access pattern is.

## Keys And Types

- Prefer `uuid` primary keys for anything exposed to a client. Sequential integer
  ids leak volume and enumerate.
- `timestamptz`, never `timestamp`. A naive timestamp is a bug waiting for a
  daylight-saving boundary.
- `numeric` for money, never `float`.
- `text` over `varchar(n)` in PostgreSQL unless the length limit is a real domain
  rule rather than a guess.
- Enums for closed sets that change rarely; a lookup table when the set is
  user-editable.

## Indexes

Index for the queries you have, not the queries you imagine.

- Every foreign key used in a join or filter.
- Composite indexes in the order the query filters (equality columns first).
- Partial indexes where the query always filters the same subset.
- Every index costs write throughput. An unused index is pure cost.

## Row Level Security

For any table a client can query directly (Supabase and PostgREST especially),
security lives in the database, not the application layer.

- Enable RLS on every client-exposed table.
- RLS enabled with no policy denies everything. That is safe, but unfinished.
- Write separate policies per operation rather than one permissive catch-all.
- Service-role paths bypass RLS. Anything running with that key is trusted code
  and must do its own authorisation.

## Migrations

- Additive first: add nullable, backfill, then enforce `NOT NULL`. A single
  destructive migration has no safe rollback.
- Every migration needs a stated rollback path, even if the path is "restore from
  backup" — say so explicitly rather than leaving it unanswered.
- Renames and drops are two deploys, not one, when a running client depends on
  the old shape.
- Check drift before designing a change: what shipped may not be what was
  designed.

## Sensitive Data

Generated `sensitive_hint` flags are prompts for a human decision, not a
classification. For each flagged column record: whether it is personal data, who
may read it, how long it is retained, and what deletion means (hard delete,
anonymise, or tombstone).
