// Seed for the MongoDB introspection check.
//
// The script reports collections with their first document's field names, and
// indexes per collection - so the fixture needs at least one document (an empty
// collection reports a bare name and would pass a name-only assertion) and one
// non-default index (every collection has _id_, so asserting on that would prove
// nothing about the index query).
db = db.getSiblingDB("introspect");

db.authors.insertOne({ name: "Ursula Le Guin", born: 1929 });
db.books.insertOne({ title: "A Wizard of Earthsea", author: "Ursula Le Guin" });

db.books.createIndex({ title: 1 }, { name: "idx_books_title" });
