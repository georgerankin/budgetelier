import sqlite3
from flask import redirect, render_template, session
from functools import wraps

# Server-side validation fails will return this apology to the user
def apology(message, code=400):
      """Render message as an apology to user."""

      def escape(s):
            """
            Escape special characters.

            https://github.com/jacebrowning/memegen#special-characters
            """
            for old, new in [
                  ("-", "--"),
                  (" ", "-"),
                  ("_", "__"),
                  ("?", "~q"),
                  ("%", "~p"),
                  ("#", "~h"),
                  ("#", "~s"),
                  ('"', "''"),
            ]:
                s = s.replace(old, new)
            return s

      return render_template("apology.html", top=code, bottom=escape(message)), code

# Decorator function to request user logins before accessing this given page
def login_required(f):
        """
        Decorate routes to require login.

        https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
        """

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("user_id") is None:
                  return redirect("/login")
            return f(*args, **kwargs)

        return decorated_function

# Convert values to euros
def eur(value):
      """Format value as EUR."""
      return f"€{value:,.2f}"

# Claude Assisted as I wasn't familiar with this bug:
# Initialise a fresh database connection. Prevents 'SQLite objects created in a thread' errors.
def get_db():

      db = sqlite3.connect('finances.db')
      db.row_factory = sqlite3.Row

      db.execute("PRAGMA foreign_keys = ON")

      return db

# Checks every field in the dictionary is not empty after value stripping
def validate_required(fields: dict):

      for name, value in fields.items():
            if not value or not str(value).strip():
                  return name
      return None

# Looks up the bank_accounts by name, scoped to the current user. Returns the account id, or None if not found or not owned by user.
def resolve_account(db, account_name, user_id):

    row = db.execute(
        """
        SELECT id
        FROM "bank_accounts"
        WHERE account_name =?
        AND user_id = ?
        """,
        (account_name, user_id)
    ).fetchone()

    return row['id'] if row else None # That SQL query should return Id if match

# When given a db and SQL query parameters, search for a specific value, return the offender if found
def check_duplicate(db, table, field, value, exclude_id=None, extra_conditions=None):
      """
      Parameters:
      db - get_db()
      table - table in db
      field - column inside the table
      value - self-explanatory
      exclude_id - Avoids checking against itself
      extra_conditions - A dict of additional conditions
      """
      query = f'SELECT id FROM "{table}" WHERE "{field}" = ?'
      params = [value]

      if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)

      if extra_conditions:
            for col, val in extra_conditions.items():
                  query += f' AND "{col}" = ?'
                  params.append(val)

      return db.execute(query, params).fetchone()

# Inserts a single row into a table and commits. Returns the new row's id (SQLite LastRowId). The commit() is included here to unify process.
def db_insert(db, table, data: dict):
      """
      Parameters:
      db - get_db()
      table - table in db
      data - a dict mapping column names to values
      """

      columns = ', '.join(f'"{k}"' for k in data.keys())
      placeholders = ', '.join('?' for _ in data)
      sql = f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})'

      cursor = db.execute(sql, list(data.values()))
      db.commit()
      return cursor.lastrowid

# Updates columns in a row and commits.
def db_update(db, table, data: dict, where: dict):
      """
      Parameters:
      db - get_db()
      table - table in db
      data - a dict mapping column names to values
      where - a dict of conditions that identify the row
      """

      set_clause = ', '.join(f'"{k}" = ?' for k in data.keys())
      where_clause = ' AND '.join(f'"{k}" = ?' for k in where.keys())
      sql = f'UPDATE "{table}" SET {set_clause} WHERE {where_clause}'
      params = list(data.values()) + list(where.values())

      db.execute(sql, params)
      db.commit()

# Deletes rows matching the where conditions and commits.
def db_delete(db, table, where: dict):
      """
      Parameters:
      db - get_db()
      table - table in db
      where - a dict of conditions that identify the row
      """

      where_clause = ' AND '.join(f'"{k}" = ?' for k in where.keys()) # Claude Assisted for compression
      sql = f'DELETE FROM "{table}" WHERE {where_clause}' # Claude Assisted for compression

      db.execute(sql, list(where.values()))
      db.commit()

# Claude Assisted: Recalculates the 'balance' column for all transactions for a user.
def recalculate_balances(db, user_id, start_date=None):
      """
      If start_date is provided, only recalculates from that date forward for optimisation purposes.
      Otherwise, recalculate everything from the top.
      """

      # If no date is provided, then start from the very first transaction
      if not start_date:
            #Get the earliest date for this yser
            earliest = db.execute(
                  """
                  SELECT MIN(date)
                  FROM "transactions"
                  WHERE user_id = ?
                  """,
                  (user_id,)
            ).fetchone()

            if not earliest or not earliest[0]:
                  return # No transaction exists

            start_date = earliest[0]

      # Fetch all transactions (sorted by date)

      transactions = db.execute(
            """
            SELECT id, date, transaction_type, amount, balance
            FROM "transactions"
            WHERE user_id = ? AND date >= ?
            ORDER BY date ASC, id ASC
            """,
            (user_id, start_date)
            ).fetchall()

      if not transactions:
            return

      # Fetch the balance "before" the first transaction in the list
      # So we look at the last transaction BEFORE start_date

      prev_row = db.execute(
            """
            SELECT balance
            FROM "transactions"
            WHERE user_id = ?
            AND (date < ? OR (date = ? AND id < ?))
            ORDER BY date DESC, id DESC
            LIMIT 1
            """,
            (user_id, start_date, start_date, transactions[0]['id'])
            ).fetchone()

      # If not previous rows exists then start at 0, otherwise use balance
      current_balance = float(prev_row['balance']) if prev_row else 0.0

      updates = []

      for t in transactions:
            amount = float(t['amount'])

            if t['transaction_type'] == 'income':
                  current_balance += amount
            elif t['transaction_type'] in ['expenses', 'savings']:
                  current_balance -= amount
            else:
                  continue

            # Check if the balance actually changed
            stored_balance = float(t['balance']) if t['balance'] is not None else 0.0

            if round(stored_balance, 2) != round(current_balance, 2):
                  updates.append((round(current_balance, 2), t['id']))

      if not updates:
            return

      # Batch update: Set new balances in the database
      sql = """UPDATE "transactions" SET balance = ? WHERE id = ?"""
      for bal, tid in updates:
            db.execute(sql, (bal, tid))

      db.commit()
