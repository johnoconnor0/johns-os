# Data model adapters

`create-data-model` produces one shared model — entities, columns, keys,
relationships, indexes — from whichever database the repository actually uses. The
adapter carries only what genuinely differs between engines. Everything downstream
(`data-model.json`, `erd.mmd`, the backend context hook, the drift check) reads the
shared shape and does not care which adapter produced it.

This mirrors `design-system-adapters.md`: one contract, several surfaces.

## Choosing

The dialect is resolved in this order:

1. An explicit `--dialect` argument.
2. The database recorded in `context/stack.json` by `detect-stack`.
3. PostgreSQL, as the default.

Whichever wins is reported back as `dialect_reason` in the output, so a wrong guess
is visible rather than silently shaping the schema. Say the reason out loud before
designing anything:

> Modelling in **MySQL** (from `context/stack.json` database: MySQL).

If that is wrong, stop and ask rather than proceeding — the dialect decides whether
enums exist, whether row level security is available, and what the migration is
allowed to say.

An ORM in the stack (Prisma, Drizzle, TypeORM, Knex, SQLAlchemy) never decides the
dialect. All of them run on several engines, so an ORM alone tells you nothing
about which one is underneath.

## What an adapter carries

| | |
| --- | --- |
| identifier quoting | `"pg"` · `` `mysql` `` · `[sqlserver]` |
| table prefix | `public.` · `dbo.` · none |
| enums | declared type, inline column type, or none |
| row level security | available or not, and how it is spelled |
| `IF NOT EXISTS` | supported or not |
| adding foreign keys later | supported or not |
| type-terminating keywords | `AUTO_INCREMENT`, `IDENTITY`, `AUTOINCREMENT`, … |
| introspection client | `psql` · `mysql` · `sqlite3` · `sqlcmd` · `mongosh` |

## postgresql

The reference implementation, and what Supabase speaks. Declared enum types
(`CREATE TYPE … AS ENUM`), schemas, and row level security via `ALTER TABLE …
ENABLE ROW LEVEL SECURITY` plus `CREATE POLICY`.

RLS is the one warning the model raises about missing security, because it is the
only engine here where a table can be left readable by default and fixed with one
statement. Enable it, then write the policies — enabling without policies fails
closed, which is the safe direction.

## mysql

No row level security, and no declared enum types. An enum is a column type
(`status ENUM('active','suspended')`), recorded in the model as an inline enum
named `table.column`.

Access control is `GRANT`s on a dedicated application user, with per-row rules
enforced in the application or through views. Do not carry Postgres policy thinking
across: there is nothing to enable.

Watch the type keywords. `UNSIGNED` and `ZEROFILL` are part of the type;
`AUTO_INCREMENT`, `COMMENT`, `CHARACTER SET` and `ON UPDATE` are not.

## sqlite

No enums, no row level security, no schemas, no users. The database is a file, so
access control is filesystem permissions plus whatever the application enforces.

Two constraints shape migrations:

- Foreign keys must be declared inline in `CREATE TABLE`; they cannot be added
  afterwards with `ALTER TABLE … ADD CONSTRAINT`.
- Enforcement requires `PRAGMA foreign_keys = ON` per connection.

Constrain a value set with `CHECK (status IN (…))` where another engine would use
an enum.

## sqlserver

Schema-qualified as `dbo.`, identifiers in `[brackets]`. No `CREATE TABLE IF NOT
EXISTS` — guard with `IF OBJECT_ID(…) IS NULL` instead.

Row level security exists but is built from a predicate function plus a
`CREATE SECURITY POLICY`, not Postgres `CREATE POLICY`. The generated migration
carries the right skeleton for it.

## mongodb

A document store: there is no DDL, so there is no `schema.sql`. Modelling it as SQL
produced an empty model stamped `postgresql`, which was worse than saying nothing.

The model is authored as `schema.json` instead:

```json
{
  "collections": [
    {
      "name": "users",
      "fields": [
        { "name": "_id", "type": "objectId", "primary_key": true },
        { "name": "email", "type": "string", "required": true, "unique": true }
      ],
      "indexes": [{ "name": "users_email_idx", "columns": ["email"] }]
    },
    {
      "name": "orders",
      "fields": [
        { "name": "_id", "type": "objectId", "primary_key": true },
        { "name": "user_id", "type": "objectId", "references": { "table": "users", "column": "_id" } }
      ]
    }
  ]
}
```

That produces the same entities, relationships and ERD as any SQL dialect. Two
things to keep honest about it:

- A reference is a modelling decision, not an enforced constraint. Mongo will not
  stop a dangling `user_id`; say so rather than implying referential integrity.
- Embedding versus referencing is the real design question, and it is driven by
  access patterns. Record which you chose and why, because the model cannot infer
  it from the field list.

Validation belongs in a JSON Schema validator on the collection. Indexes are
created from the driver or a migration script, not from DDL.

## Rules for every adapter

- The model is the same shape regardless of engine. If something cannot be
  expressed for a given database, leave it out — never fabricate a field to make
  the shapes match.
- Never warn about a feature the engine does not have. A row-level-security warning
  on MySQL is noise, and noise is how a warnings list stops being read.
- Normalise to third normal form unless there is a stated reason not to, and record
  the reason when there is. That rule is engine-independent.
- Sensitive-column hints are engine-independent too, and are always a prompt for a
  human to confirm — never a classification asserted as fact.
- A generated migration must be runnable on its engine. If the adapter cannot emit
  a statement that runs, emit a comment explaining what to do instead.
