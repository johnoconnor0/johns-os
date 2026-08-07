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

    def assert_real_introspection(self, digest: str, dialect: str, source: str, fk_marker: str) -> None:
        """The five assertions, in the order they matter.

        The first is the one that would have caught the original defect: both
        broken dialects connected to nothing and fell into the manual branch,
        which is indistinguishable from success unless something looks for it.
        """
        self.assertNotIn(
            "provide schema manually",
            digest,
            f"{dialect}: fell into the manual-paste branch, i.e. it never connected.\n{digest}",
        )
        self.assertNotIn("Connection failed", digest, f"{dialect}: connection failed\n{digest}")

        # A script that connects but returns nothing would pass the check above.
        self.assertIn("authors", digest, f"{dialect}: seeded table `authors` missing\n{digest}")
        self.assertIn("books", digest, f"{dialect}: seeded table `books` missing\n{digest}")

        # The digest has a separate foreign-keys section; an empty one is a
        # different failure from an empty tables section.
        #
        # The marker is per-dialect because the two queries genuinely return
        # different shapes: MySQL selects table/column/referenced-column and never
        # the constraint name, SQL Server selects `fk.name` and never the column.
        # One shared assertion cannot hold for both, and forcing one would only
        # mean testing whichever half happened to be asserted.
        self.assertIn("Foreign keys", digest, f"{dialect}: no foreign-keys section\n{digest}")
        self.assertIn(fk_marker, digest, f"{dialect}: the seeded foreign key is missing\n{digest}")

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
        self.assert_real_introspection(self.introspect(MYSQL_DSN, "mysql"), "mysql", "mysql", "author_id")

    def test_sqlserver_actually_connects(self) -> None:
        # `sqlcmd -S "$DSN"` passed a URL where -S expects a bare server, with no
        # -U and no -d. Same silent failure.
        self.assert_real_introspection(
            self.introspect(MSSQL_DSN, "sqlserver"), "sqlserver", "sqlcmd", "fk_books_author"
        )

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
