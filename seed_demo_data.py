"""
seed_demo_data.py

Populates a fresh finances.db with fictional demo data so the app is
runnable and demonstrable out of the box, without any real user data.

Usage:
    python seed_demo_data.py

Creates finances.db in the current directory (matching the app's real
schema) if it doesn't already exist, then inserts a demo user, bank
accounts, categories, and transactions with a running per-user balance,
matching the logic in helpers.recalculate_balances().

Demo login:
    username: demo
    password: demo1234
"""

import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

DB_PATH = "finances.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('income', 'expenses', 'savings')),
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS "bank_accounts" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "transactions" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('income', 'expenses', 'savings')),
    category_id INTEGER NOT NULL,
    sub_category TEXT,
    amount NUMERIC NOT NULL,
    details TEXT NOT NULL,
    balance NUMERIC NOT NULL,
    effective_date DATE,
    card_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    FOREIGN KEY (card_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "budget" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    target_budget NUMERIC NOT NULL,
    bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL,
    UNIQUE (category_id, year, month),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
);
"""


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    cur = conn.cursor()

    # --- Demo user ---
    cur.execute("SELECT id FROM users WHERE username = 'demo'")
    if cur.fetchone():
        print("Demo user already exists, skipping seed to avoid duplicates.")
        conn.close()
        return

    demo_hash = generate_password_hash("demo1234")
    cur.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("demo", demo_hash),
    )
    user_id = cur.lastrowid

    # --- Bank accounts (card_id in transactions refers to these) ---
    accounts = [
        ("Demo Checking", "checking"),
        ("Demo Savings", "savings"),
    ]
    account_ids = {}
    for name, acc_type in accounts:
        cur.execute(
            "INSERT INTO bank_accounts (user_id, account_name, account_type) VALUES (?, ?, ?)",
            (user_id, name, acc_type),
        )
        account_ids[name] = cur.lastrowid

    # --- Categories (global/unique by name, not per-user, per schema) ---
    categories = [
        ("Salary", "income", "Regular employment income"),
        ("Freelance", "income", "Side project / contract income"),
        ("Groceries", "expenses", "Food and household shopping"),
        ("Rent", "expenses", "Monthly rent payment"),
        ("Utilities", "expenses", "Electricity, gas, water, internet"),
        ("Dining Out", "expenses", "Restaurants and takeaway"),
        ("Emergency Fund", "savings", "Rainy day savings"),
    ]
    category_ids = {}
    for name, ctype, description in categories:
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            category_ids[name] = row[0]
            continue
        cur.execute(
            "INSERT INTO categories (type, name, description) VALUES (?, ?, ?)",
            (ctype, name, description),
        )
        category_ids[name] = cur.lastrowid

    # --- Transactions (fictional, spread over the last ~6 weeks) ---
    # transaction_type values must match the schema CHECK constraint:
    # 'income', 'expenses', 'savings' (note: 'expenses', not 'expense')
    today = date.today()
    demo_transactions = [
        # (days_ago, account, category, type, amount, details)
        (42, "Demo Checking", "Salary", "income", 3200.00, "Monthly salary"),
        (40, "Demo Checking", "Rent", "expenses", 1100.00, "Monthly rent"),
        (38, "Demo Checking", "Groceries", "expenses", 64.20, "Weekly shop"),
        (35, "Demo Checking", "Utilities", "expenses", 85.50, "Electricity & gas"),
        (31, "Demo Checking", "Groceries", "expenses", 58.75, "Weekly shop"),
        (28, "Demo Checking", "Dining Out", "expenses", 42.00, "Dinner with friends"),
        (24, "Demo Checking", "Groceries", "expenses", 71.10, "Weekly shop"),
        (20, "Demo Savings", "Emergency Fund", "savings", 250.00, "Monthly transfer"),
        (14, "Demo Checking", "Freelance", "income", 450.00, "Side project payment"),
        (10, "Demo Checking", "Groceries", "expenses", 66.40, "Weekly shop"),
        (7, "Demo Checking", "Dining Out", "expenses", 28.90, "Lunch out"),
        (3, "Demo Checking", "Groceries", "expenses", 59.30, "Weekly shop"),
    ]

    # Balance is tracked per-user (not per-account), matching
    # helpers.recalculate_balances(), which sums chronologically across
    # ALL of a user's transactions regardless of which card/account.
    running_balance = 0.0

    for days_ago, account_name, category_name, ttype, amount, details in demo_transactions:
        txn_date = today - timedelta(days=days_ago)

        if ttype == "income":
            running_balance += amount
        else:  # expenses or savings both draw down the running balance
            running_balance -= amount

        cur.execute(
            """
            INSERT INTO transactions
                (date, transaction_type, category_id, sub_category, amount,
                 details, balance, effective_date, card_id, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                txn_date.isoformat(),
                ttype,
                category_ids[category_name],
                None,
                amount,
                details,
                round(running_balance, 2),
                txn_date.isoformat(),
                account_ids[account_name],
                user_id,
            ),
        )

    conn.commit()
    conn.close()

    print("Demo data seeded successfully.")
    print("Log in with username 'demo' / password 'demo1234'.")


if __name__ == "__main__":
    seed()
