import sqlite3

with sqlite3.connect("hw.db") as conn:
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY, name TEXT, writer TEXT, genre TEXT)")

    cursor.execute("DELETE FROM books")

    books = [{'name': "The Alchemist", 'writer': "Paulo Coelho", 'genre': "allegory"},
             {'name': "Dune", 'writer': "Frank Herbert", 'genre': "science fiction"},
             {'name': "Murder on the Orient Express", 'writer': "Agatha Christie", 'genre': "mystery"},
             {'name': "Sapiens: A Brief History of Humankind", 'writer': "Yuval Noah Harari", 'genre': "history"},
             {'name': "Pride and Prejudice", 'writer': "Jane Austen", 'genre': "romance"},
             {'name': "Atomic Habits", 'writer': "James Clear", 'genre': "self-help"}]
    cursor.executemany("INSERT INTO books (name, writer, genre) VALUES (?, ?, ?)", books)

    conn.commit()
