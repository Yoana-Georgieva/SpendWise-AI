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

def delete_expense(expense_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

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

def get_period_stats(group_by: str = "day", month: str = None) -> list:
    """Групира разходите по дни, седмици или месеци за графиките по периоди."""
    conn = sqlite3.connect("spendwise.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if group_by == "month":
        period_expr = "substr(date, 1, 7)"
    elif group_by == "week":
        period_expr = "strftime('%Y-W%W', date)"
    else:  # "day"
        period_expr = "date"

    if month and group_by != "month":
        cursor.execute(
            f"""
            SELECT {period_expr} AS period,
                   ROUND(SUM(amount), 2) AS total,
                   COUNT(*) AS count
            FROM expenses
            WHERE date LIKE ?
            GROUP BY period
            ORDER BY period ASC
            """,
            (f"{month}-%",)
        )
    else:
        cursor.execute(
            f"""
            SELECT {period_expr} AS period,
                   ROUND(SUM(amount), 2) AS total,
                   COUNT(*) AS count
            FROM expenses
            GROUP BY period
            ORDER BY period ASC
            """
        )

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_month_habits_data(month: str) -> dict:
    """Събира обобщени статистики за навиците на харчене за конкретен месец."""
    conn = sqlite3.connect("spendwise.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Всички разходи за месеца
    cursor.execute(
        """
        SELECT title, amount, category, date
        FROM expenses
        WHERE date LIKE ?
        ORDER BY amount DESC
        """,
        (f"{month}-%",)
    )
    expenses = [dict(row) for row in cursor.fetchall()]

    # Месечен бюджет (ако има зададен)
    cursor.execute("SELECT limit_amount FROM budgets WHERE month = ?", (month,))
    budget_row = cursor.fetchone()
    limit_amount = float(budget_row["limit_amount"]) if budget_row else 0.0

    # Разбивка по категории
    cursor.execute(
        """
        SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS count
        FROM expenses
        WHERE date LIKE ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (f"{month}-%",)
    )
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()

    total_spent = round(sum(e["amount"] for e in expenses), 2)
    count = len(expenses)
    avg_expense = round(total_spent / count, 2) if count > 0 else 0.0

    # Добавяме процент към всяка категория
    for cat in categories:
        cat["percentage"] = round((cat["total"] / total_spent) * 100, 1) if total_spent > 0 else 0.0

    top_expense = expenses[0] if expenses else None

    return {
        "month": month,
        "limit_amount": limit_amount,
        "total_spent": total_spent,
        "remaining": round(limit_amount - total_spent, 2) if limit_amount > 0 else None,
        "is_exceeded": (limit_amount > 0 and total_spent > limit_amount),
        "transaction_count": count,
        "average_expense": avg_expense,
        "top_expense": top_expense,
        "categories": categories,
    }
