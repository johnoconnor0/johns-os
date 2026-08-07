-- Seed for the SQLite introspection check.
--
-- No container: SQLite is a file, so the harness builds this database in place.
-- The script emits a `.schema` dump and a table list, so a named foreign key is
-- assertable here in a way it is not for MySQL - `.schema` prints the DDL
-- verbatim, constraint name included.
CREATE TABLE authors (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL
);

CREATE TABLE books (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  title     TEXT NOT NULL,
  author_id INTEGER NOT NULL,
  CONSTRAINT fk_books_author FOREIGN KEY (author_id) REFERENCES authors (id)
);

INSERT INTO authors (name) VALUES ('Ursula Le Guin');
INSERT INTO books (title, author_id) VALUES ('A Wizard of Earthsea', 1);
