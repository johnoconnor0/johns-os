#!/usr/bin/env python3
"""Run `schema-introspect.sh` against live database servers.

## Why this exists

`create-data-model` advertises five dialects. Two of them had never worked:
`mysql` was handed a URL where the client expects a database *name*, and
`sqlcmd` a URL where `-S` expects a bare server, with no `-U` or `-d` at all.
Both failed into the same silent branch - "Connection failed - provide schema
manually" - so the digest looked plausible, the exit code was 0, and nothing
anywhere said the connection had not happened.

Unit tests cannot catch that. The DSN splitting is verifiable in isolation and
is covered in `test_quality_tools.py`; whether a real client accepts the
resulting flags is only answerable by running a real client against a real
server.

## Why the script runs inside a container

`schema-introspect.sh` gates every dialect on `command -v <client>`. Without the
clients on PATH it falls to "provide schema manually" regardless of whether a
server is up - so a test that started servers but ran the script on a machine
with no clients would pass while proving nothing. The harness image carries the
clients; the script is mounted read-only so the thing under test cannot be
altered by the thing testing it.

## Why PostgreSQL is here

As a **control**, not for coverage. Its path is known to work. If PostgreSQL
passes while MySQL or SQL Server fails, the harness is sound and the failing
dialect is genuinely broken. A red result with no control cannot distinguish
"the script is wrong" from "the test rig is wrong".
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPOSE = HERE / "compose.yaml"

# Fixtures, matching compose.yaml. Not secrets - throwaway containers on a
# private network - and deliberately obvious so nobody mistakes one for real.
MYSQL_DSN = "mysql://fixture:fixture-pw@mysql:3306/introspect"
POSTGRES_DSN = "postgres://fixture:fixture-pw@postgres:5432/introspect"
MSSQL_DSN = "sqlserver://sa:Fixture-pw-1234@mssql:1433/introspect"
# authSource=admin because the seeded root user lives in the admin database.
MONGO_DSN = "mongodb://fixture:fixture-pw@mongo:27017/introspect?authSource=admin"
# No container: SQLite is a file. The harness builds it in setUpClass.
SQLITE_PATH = "/tmp/introspect.db"

# Every password above, for the assertion that none of them reaches stdout.
FIXTURE_PASSWORDS = ("fixture-pw", "Fixture-pw-1234")

STARTUP_TIMEOUT = 600


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    probe = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=60)
    return probe.returncode == 0


def _compose(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@unittest.skipUnless(os.environ.get("RUN_DB_INTEGRATION") == "1", "set RUN_DB_INTEGRATION=1 to run")
class SchemaIntrospectionTests(unittest.TestCase):
    """One class, because the containers are expensive to start and stop."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        if not _docker_available():
            raise unittest.SkipTest("docker is not available or the daemon is not running")

        up = _compose("up", "--build", "--wait", "--quiet-pull", timeout=STARTUP_TIMEOUT)
        if up.returncode != 0:
            _compose("down", "-v")
            raise unittest.SkipTest(f"could not start the database containers:\n{up.stderr[-3000:]}")

        # SQL Server has no docker-entrypoint-initdb.d, so its schema is applied
        # here, once the healthcheck has already proved the server answers.
        # `bash -c`, never `bash -lc`: a login shell re-reads /etc/profile, which
        # rebuilds PATH from scratch and drops the /opt/mssql-tools18/bin that the
        # image's ENV put there. The symptom is "sqlcmd: command not found" on an
        # image where sqlcmd is plainly installed.
        seeded = _compose(
            "exec",
            "-T",
            "harness",
            "bash",
            "-c",
            'sqlcmd -S mssql,1433 -U sa -P "Fixture-pw-1234" -C -b -i /work/seed/mssql.sql',
            timeout=180,
        )
        if seeded.returncode != 0:
            _compose("down", "-v")
            raise unittest.SkipTest(f"could not seed SQL Server:\n{seeded.stdout}\n{seeded.stderr}")

        # SQLite is a file, not a server, so it is built inside the harness. It is
        # in this suite anyway: "no server to get wrong" is a reason to expect it
        # works, not evidence that it does.
        built = _compose(
            "exec",
            "-T",
            "harness",
            "bash",
            "-c",
            f"rm -f {SQLITE_PATH} && sqlite3 {SQLITE_PATH} < /work/seed/sqlite.sql",
            timeout=60,
        )
        if built.returncode != 0:
            _compose("down", "-v")
            raise unittest.SkipTest(f"could not build the SQLite fixture:\n{built.stdout}\n{built.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        _compose("down", "-v", timeout=180)

    def introspect(self, dsn: str, dialect: str) -> str:
        """Run the real script inside the harness and return its digest."""
        result = _compose(
            "exec",
            "-T",
            "-e",
            f"DATABASE_URL={dsn}",
            # The containers present self-signed certificates and sqlcmd 18+
            # validates them by default. Opting in here rather than having the
            # script always pass -C is the point: a dev container should be
            # trusted deliberately, a production server should not be trusted
            # silently.
            "-e",
            "MSSQL_TRUST_SERVER_CERT=1",
            "harness",
            "bash",
            "/work/scripts/schema-introspect.sh",
            "--dialect",
            dialect,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"{dialect}: script exited {result.returncode}\n{result.stderr}")
        return result.stdout

    def assert_real_introspection(
        self,
        digest: str,
        dialect: str,
        source: str,
        objects: tuple[str, ...],
        second_section: str,
        second_marker: str,
    ) -> None:
        """The five assertions, in the order they matter.

        The first is the one that would have caught the original defect: two
        dialects connected to nothing and fell into the manual branch, which is
        indistinguishable from success unless something looks for it.

        Everything after that is parameterised because the digests genuinely
        differ. A relational engine reports tables and foreign keys; Mongo reports
        collections and indexes and has neither of the other two. Forcing one
        shape onto all five would mean asserting whatever the shared subset
        happened to be, which is close to asserting nothing.
        """
        self.assertNotIn(
            "provide schema manually",
            digest,
            f"{dialect}: fell into the manual-paste branch, i.e. it never connected.\n{digest}",
        )
        self.assertNotIn("Connection failed", digest, f"{dialect}: connection failed\n{digest}")
        self.assertNotIn("Could not open database", digest, f"{dialect}: could not open\n{digest}")

        # A script that connects but returns nothing would pass the checks above.
        for name in objects:
            self.assertIn(name, digest, f"{dialect}: seeded object `{name}` missing\n{digest}")

        # The second section is a separate query. An empty one is a different
        # failure from an empty first section, and only the second proves the
        # follow-up query ran at all.
        self.assertIn(second_section, digest, f"{dialect}: no `{second_section}` section\n{digest}")
        self.assertIn(second_marker, digest, f"{dialect}: `{second_marker}` missing from the second section\n{digest}")

        self.assertIn(f"**Source:** {source}", digest, f"{dialect}: wrong source line\n{digest}")

        # The credential fix: the password must not survive into the artifact.
        for password in FIXTURE_PASSWORDS:
            self.assertNotIn(password, digest, f"{dialect}: password leaked into the digest")

    def test_the_script_has_unix_line_endings(self) -> None:
        # The harness mounts the working tree, so a CRLF working copy on Windows
        # reaches container bash as `$'\r': command not found` followed by a
        # syntax error - which reads like a broken script rather than a broken
        # checkout. .gitattributes forces LF for *.sh; this catches a working tree
        # that drifted from it before the failure becomes cryptic.
        script = HERE.parents[1] / "scripts" / "schema-introspect.sh"
        self.assertNotIn(b"\r\n", script.read_bytes(), f"{script.name} has CRLF endings; container bash cannot run it")

    # --- the control -------------------------------------------------------

    def test_postgresql_is_the_control(self) -> None:
        # Known-working. If this fails, the harness is wrong, not the dialect -
        # do not chase the MySQL or SQL Server failures until this is green.
        digest = self.introspect(POSTGRES_DSN, "postgresql")
        self.assertNotIn("provide schema manually", digest, digest)
        self.assertIn("authors", digest)
        self.assertIn("**Source:** psql", digest)
        for password in FIXTURE_PASSWORDS:
            self.assertNotIn(password, digest)

    # --- the two that had never worked -------------------------------------

    def test_mysql_actually_connects(self) -> None:
        # `mysql --table "$DSN"` passed a URL where the client expects a database
        # NAME, so this had never once connected.
        self.assert_real_introspection(
            self.introspect(MYSQL_DSN, "mysql"), "mysql", "mysql", ("authors", "books"), "Foreign keys", "author_id"
        )

    def test_sqlserver_actually_connects(self) -> None:
        # `sqlcmd -S "$DSN"` passed a URL where -S expects a bare server, with no
        # -U and no -d. Same silent failure.
        self.assert_real_introspection(
            self.introspect(MSSQL_DSN, "sqlserver"),
            "sqlserver",
            "sqlcmd",
            ("authors", "books"),
            "Foreign keys",
            "fk_books_author",
        )

    # --- the two that were only ever believed to work ----------------------

    def test_sqlite_actually_reads_the_file(self) -> None:
        # Not among the broken pair, and never verified either. `.schema` prints
        # the DDL verbatim, so unlike MySQL the constraint name IS assertable here.
        self.assert_real_introspection(
            self.introspect(f"file:{SQLITE_PATH}", "sqlite"),
            "sqlite",
            "sqlite3",
            ("authors", "books"),
            "Tables",
            "fk_books_author",
        )

    def test_mongodb_actually_connects(self) -> None:
        # A document store has no tables and no foreign keys, so the digest is
        # collections and indexes instead. `idx_books_title` is a non-default
        # index on purpose: every collection has `_id_`, so asserting on that
        # would pass without the index query having run at all.
        self.assert_real_introspection(
            self.introspect(MONGO_DSN, "mongodb"),
            "mongodb",
            "mongosh",
            ("authors", "books"),
            "Indexes",
            "idx_books_title",
        )

    def test_mongodb_reports_field_names_not_just_collection_names(self) -> None:
        # The collections query prints each collection's first document's keys.
        # An empty collection reports a bare name, which would satisfy a
        # name-only assertion while proving the document read never happened.
        digest = self.introspect(MONGO_DSN, "mongodb")
        self.assertIn("name", digest, f"authors' field names are missing\n{digest}")
        self.assertIn("title", digest, f"books' field names are missing\n{digest}")

    # --- the shape of a failure --------------------------------------------

    def test_an_unreachable_server_says_so_rather_than_inventing_a_schema(self) -> None:
        # The manual branch is correct behaviour when there is genuinely nothing
        # to talk to. What was wrong was reaching it while a healthy server sat
        # on the other end of a well-formed DSN.
        digest = self.introspect("mysql://fixture:fixture-pw@mysql:3306/does_not_exist", "mysql")
        self.assertIn("Connection failed", digest)
        self.assertNotIn("authors", digest)
        for password in FIXTURE_PASSWORDS:
            self.assertNotIn(password, digest)


if __name__ == "__main__":
    if "--report" in sys.argv:
        print(json.dumps({"compose": str(COMPOSE), "docker": _docker_available()}, indent=2))
        raise SystemExit(0)
    unittest.main()
