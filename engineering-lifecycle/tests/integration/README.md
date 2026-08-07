# Live database introspection checks

Runs `scripts/schema-introspect.sh` against all five advertised dialects: MySQL,
SQL Server, PostgreSQL and MongoDB in containers, plus a real SQLite file built in
the harness.

```bash
cd engineering-lifecycle/tests/integration
RUN_DB_INTEGRATION=1 python -m unittest test_introspection -v
```

Skips cleanly when `RUN_DB_INTEGRATION` is unset or Docker is unavailable, so it
never blocks `scripts/validate-repo.py`. First run pulls ~2GB of images.

## Why it is not a unit test

Two of the five advertised dialects had never worked. `mysql` was handed a URL
where the client expects a database *name*; `sqlcmd` got a URL where `-S` expects
a bare server, with no `-U` or `-d`. Both failed into the same branch —
"Connection failed — provide schema manually" — so the digest looked plausible and
the exit code was 0.

The DSN splitting is verifiable in isolation and is unit-tested in
`test_quality_tools.py`. Whether a real client accepts the resulting flags is only
answerable by running a real client against a real server.

## Why the script runs inside a container

Every dialect is gated on `command -v <client>`. Without the clients on PATH the
script falls to "provide schema manually" regardless of whether a server is
running — so a test that started servers but ran the script on a machine with no
clients would pass while proving nothing. The harness image carries the clients;
the script is mounted read-only.

This is also the only way the suite runs on a Windows machine without installing
four database clients by hand.

## Why PostgreSQL is here

As a **control**, not for coverage. Its path is known to work. If PostgreSQL
passes while MySQL or SQL Server fails, the harness is sound and the failing
dialect is genuinely broken. A red result with no control cannot distinguish "the
script is wrong" from "the test rig is wrong". Start there when something fails.

## What it asserts, in the order that matters

1. The digest does **not** contain `provide schema manually` — that silent
   fallback was the original bug.
2. The seeded tables appear. A script that connects and returns nothing would
   pass (1) alone.
3. The digest's **second** section is populated. Only that proves the follow-up
   query ran at all, and the marker is per-dialect because the shapes genuinely
   differ: MySQL returns table/column/referenced-column and never the constraint
   name, SQL Server returns `fk.name` and never the column, SQLite's `.schema`
   prints the DDL verbatim, and MongoDB has no foreign keys at all — it reports
   collections and indexes. Forcing one shape onto five would mean asserting
   whatever the shared subset happened to be, which is close to asserting nothing.
4. The `**Source:**` line names the client that actually ran.
5. No fixture password reaches the digest.

For MongoDB there is one extra check: the collections query prints each
collection's first document's field names, and an *empty* collection reports a
bare name — which would satisfy a name-only assertion while proving the document
read never happened. The index marker is a non-default index for the same reason;
every collection has `_id_`.

Plus the inverse: an unreachable server must still say so rather than invent a
schema, and the script must have LF line endings — a CRLF working copy reaches
container bash as a confusing syntax error rather than an obvious checkout problem.

## Things that will bite

- **SQL Server needs `MSSQL_TRUST_SERVER_CERT=1`** against any container.
  sqlcmd 18+ defaults to `Encrypt=yes` and validates the certificate, and a
  container's is self-signed. The script does not pass `-C` automatically:
  trusting a *production* server's certificate silently would be a poor trade in
  a script whose other job is keeping credentials out of `ps`.
- **No arm64 SQL Server image exists.** On Apple Silicon this needs
  `azure-sql-edge` or emulation.
- **The credentials in `compose.yaml` are fixtures**, deliberately obvious, for
  throwaway containers on a private network. They are not secrets and must not be
  moved into a `.env` that someone later treats as one.
