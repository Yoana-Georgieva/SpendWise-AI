import sqlite3

DB_NAME = "spendwise.db"

def get_db_connection():
    """Помощна функция, която отваря връзка и прави редовете да приличат на речници."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            source TEXT DEFAULT 'manual'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT UNIQUE NOT NULL,
            limit_amount REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("Базата данни и таблиците са създадени успешно!")

def add_expense(title: str, amount: float, category: str, date: str, source: str = 'manual'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (title, amount, category, date, source)
        VALUES (?, ?, ?, ?, ?)
    """, (title, amount, category, date, source))
    conn.commit()
    new_id = cursor.lastrowid  
    conn.close()
    return new_id

def get_all_expenses():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC")
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]

def set_budget(month: str, limit_amount: float):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO budgets (month, limit_amount)
        VALUES (?, ?)
    """, (month, limit_amount))
    
    conn.commit()
    conn.close()

def get_budget_status(month: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT limit_amount FROM budgets WHERE month = ?", (month,))
    budget_row = cursor.fetchone()
    limit_amount = budget_row["limit_amount"] if budget_row else 0.0

    cursor.execute("""
        SELECT SUM(amount) as total_spent 
        FROM expenses 
        WHERE date LIKE ?
    """, (f"{month}%",))
    
    spent_row = cursor.fetchone()
    total_spent = spent_row["total_spent"] if spent_row["total_spent"] is not None else 0.0
    
    conn.close()

    remaining = round(limit_amount - total_spent, 2)
    
    return {
        "month": month,
        "limit_amount": limit_amount,
        "total_spent": round(total_spent, 2),
        "remaining": remaining,
        "is_exceeded": remaining < 0 and limit_amount > 0  
    }


def get_category_stats(month: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, ROUND(SUM(amount), 2) as total
        FROM expenses
        WHERE date LIKE ?
        GROUP BY category
        ORDER BY total DESC
    """, (f"{month}%",))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()

    set_budget("2026-11", 500.00)
    
    print("--- Статус на бюджета ---")
    print(get_budget_status("2026-11"))
    
    print("--- Статистика по категории (за графиките) ---")
    print(get_category_stats("2026-11"))

