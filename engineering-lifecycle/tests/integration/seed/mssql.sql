-- Seed for the SQL Server introspection check.
--
-- The mssql image has no docker-entrypoint-initdb.d equivalent, so unlike MySQL
-- and Postgres this is applied by the harness after the server reports healthy.
IF DB_ID('introspect') IS NULL
  CREATE DATABASE introspect;
GO

USE introspect;
GO

IF OBJECT_ID('dbo.books', 'U') IS NOT NULL DROP TABLE dbo.books;
IF OBJECT_ID('dbo.authors', 'U') IS NOT NULL DROP TABLE dbo.authors;
GO

CREATE TABLE dbo.authors (
  id   INT IDENTITY(1,1) PRIMARY KEY,
  name NVARCHAR(120) NOT NULL
);
GO

CREATE TABLE dbo.books (
  id        INT IDENTITY(1,1) PRIMARY KEY,
  title     NVARCHAR(200) NOT NULL,
  author_id INT NOT NULL,
  CONSTRAINT fk_books_author FOREIGN KEY (author_id) REFERENCES dbo.authors (id)
);
GO

INSERT INTO dbo.authors (name) VALUES ('Ursula Le Guin');
INSERT INTO dbo.books (title, author_id) VALUES ('A Wizard of Earthsea', 1);
GO
