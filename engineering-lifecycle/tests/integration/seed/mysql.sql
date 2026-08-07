-- Seed for the MySQL introspection check.
--
-- Two tables and one foreign key, deliberately: the digest has a "Tables"
-- section and a "Foreign keys" section, and a script that connects but emits an
-- empty second section would otherwise pass a table-name-only assertion.
CREATE TABLE authors (
  id   INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL
);

CREATE TABLE books (
  id        INT PRIMARY KEY AUTO_INCREMENT,
  title     VARCHAR(200) NOT NULL,
  author_id INT NOT NULL,
  CONSTRAINT fk_books_author FOREIGN KEY (author_id) REFERENCES authors (id)
);

INSERT INTO authors (name) VALUES ('Ursula Le Guin');
INSERT INTO books (title, author_id) VALUES ('A Wizard of Earthsea', 1);
