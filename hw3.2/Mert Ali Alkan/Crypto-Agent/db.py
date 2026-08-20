import sqlite3

DB_PATH = 'portfolio.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create balances table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS balances (
            asset TEXT PRIMARY KEY,
            amount REAL
        )
    ''')
    
    # Check if empty, if so, insert initial USD balance of 10,000
    cursor.execute('SELECT COUNT(*) FROM balances')
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO balances (asset, amount) VALUES ('USDT', 10000.0)")
        conn.commit()
        
    conn.close()

def get_portfolio():
    """Reads the current portfolio balances from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT asset, amount FROM balances WHERE amount > 0')
    rows = cursor.fetchall()
    conn.close()
    
    portfolio = {row[0]: row[1] for row in rows}
    return portfolio

def execute_trade(action: str, symbol: str, amount: float, price: float):
    """
    Executes a buy or sell trade. 
    action: 'buy' or 'sell'
    symbol: e.g., 'BTC'
    amount: amount of crypto to buy/sell
    price: current price of the crypto in USDT
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get current USDT
    cursor.execute("SELECT amount FROM balances WHERE asset='USDT'")
    usdt_row = cursor.fetchone()
    current_usdt = usdt_row[0] if usdt_row else 0.0
    
    # Get current Crypto
    cursor.execute("SELECT amount FROM balances WHERE asset=?", (symbol,))
    crypto_row = cursor.fetchone()
    current_crypto = crypto_row[0] if crypto_row else 0.0
    
    total_cost = amount * price
    
    if action == 'buy':
        if current_usdt < total_cost:
            conn.close()
            return {"status": "error", "message": f"Yetersiz bakiye. Gerekli: {total_cost} USDT, Mevcut: {current_usdt} USDT"}
        
        # Deduct USDT, Add Crypto
        new_usdt = current_usdt - total_cost
        new_crypto = current_crypto + amount
        
    elif action == 'sell':
        if current_crypto < amount:
            conn.close()
            return {"status": "error", "message": f"Yetersiz {symbol} bakiyesi. Gerekli: {amount}, Mevcut: {current_crypto}"}
            
        # Add USDT, Deduct Crypto
        new_usdt = current_usdt + total_cost
        new_crypto = current_crypto - amount
    else:
        conn.close()
        return {"status": "error", "message": "Geçersiz işlem tipi. 'buy' veya 'sell' olmalı."}
        
    # Update DB
    cursor.execute("UPDATE balances SET amount=? WHERE asset='USDT'", (new_usdt,))
    
    if crypto_row:
        cursor.execute("UPDATE balances SET amount=? WHERE asset=?", (new_crypto, symbol))
    else:
        cursor.execute("INSERT INTO balances (asset, amount) VALUES (?, ?)", (symbol, new_crypto))
        
    conn.commit()
    conn.close()
    
    return {
        "status": "success", 
        "message": f"İşlem başarılı. Yeni bakiyeler -> USDT: {new_usdt:.2f}, {symbol}: {new_crypto:.4f}"
    }

# Initialize the db when module is imported
init_db()
