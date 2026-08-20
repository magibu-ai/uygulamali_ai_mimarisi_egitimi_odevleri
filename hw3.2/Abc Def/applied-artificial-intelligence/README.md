
# Tool Calling

- An implementation where AI can list or buy books from an imaginary bookshop.
- Only actions AI can take is list books and buy books. Buying a book removes it from the DB.

## How to Run
- Download Python 3.13
- Download SQLite Server.
- Run "pip install -r requirements.txt"
- Run create-table.py.
- Run app.py

## Examples

"List me books of AI Book Cafe"

🚀 User Query: List me books of AI Book Cafe
  [Step 1] Calling: 'get_book_list'
  [Step 1] 🔌 Tool Result: [{'id': 1, 'name': 'The Alchemist', 'writer': 'Paulo Coelho', 'genre': 'allegory'}, {'id': 2, 'name': 'Dune', 'writer': 'Frank Herbert', 'genre': 'science fiction'}, {'id': 3, 'name': 'Murder on the Orient Express', 'writer': 'Agatha Christie', 'genre': 'mystery'}, {'id': 4, 'name': 'Sapiens: A Brief History of Humankind', 'writer': 'Yuval Noah Harari', 'genre': 'history'}, {'id': 5, 'name': 'Pride and Prejudice', 'writer': 'Jane Austen', 'genre': 'romance'}, {'id': 6, 'name': 'Atomic Habits', 'writer': 'James Clear', 'genre': 'self-help'}]

📚 AI Book Cafe Catalog

Here is the list of books currently available at the AI Book Cafe:
- The Alchemist
  Author: Paulo Coelho
  Genre: Allegory
- Dune
  Author: Frank Herbert
  Genre: Science Fiction
- Murder on the Orient Express
  Author: Agatha Christie
  Genre: Mystery
- Sapiens: A Brief History of Humankind
  Author: Yuval Noah Harari
  Genre: History
- Pride and Prejudice
  Author: Jane Austen
  Genre: Romance
- Atomic Habits
  Author: James Clear
  Genre: Self-help

"Buy 'Dune' from AI Book Cafe"

🚀 User Query: Buy 'Dune' from AI Book Cafe
  [Step 1] Calling: 'buy_book'
  [Step 1] 🔌 Tool Result: Successfully bought book "Dune"
Successfully bought book "Dune"

## Structure
- Uses SQLite 3 database
- Uses "unsloth/gemma-4-12B-it" model
- I did not create another backend. Instead functions that are called by tool update DB directly. This way application is more lightweight. 