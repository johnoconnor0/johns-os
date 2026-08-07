-- Seed for the PostgreSQL introspection check.
--
-- Postgres is the CONTROL, not coverage. Its path is known to work, so if it
-- passes while MySQL or SQL Server fails, the harness is sound and the failing
-- dialect is genuinely broken. A red result with no control is ambiguous.
CREATE TABLE authors (
  id   SERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL
);

CREATE TABLE books (
  id        SERIAL PRIMARY KEY,
  title     VARCHAR(200) NOT NULL,
  author_id INTEGER NOT NULL REFERENCES authors (id)
);

INSERT INTO authors (name) VALUES ('Ursula Le Guin');
INSERT INTO books (title, author_id) VALUES ('A Wizard of Earthsea', 1);
