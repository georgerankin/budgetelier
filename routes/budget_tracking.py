from flask import Blueprint, render_template, request, redirect, session, flash
from helpers import (apology, get_db, login_required, recalculate_balances, resolve_account,
                     validate_required, db_insert, db_update, db_delete)

budget_tracking_bp = Blueprint('budget_tracking', __name__)

VALID_TYPES=('income', 'expenses', 'savings')



# Retrieves categories grouped by type, accounts, and transactions to build this page.
def _get_page_data(db, user_id, transactions=None):

    all_categories = db.execute(
        """
        SELECT type, name
        FROM "categories"
        ORDER BY type, name
        """
    ).fetchall()

    categories_by_type = {t: [] for t in VALID_TYPES} # Claude Assisted for compression
    for cat in all_categories:
            if cat['type'] in categories_by_type:
                categories_by_type[cat['type']].append(cat['name'])

    accounts = db.execute(
        """
        SELECT account_name
        FROM "bank_accounts"
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    if transactions is None:
        transactions = db.execute(
            """
            SELECT t.*, c.name as category_name, b.account_name as account_name
            FROM "transactions" t
            JOIN categories c ON t.category_id = c.id
            JOIN bank_accounts b ON t.card_id = b.id
            WHERE t.user_id = ?
            ORDER BY t.date DESC
            """,
            (user_id,)
        ).fetchall()

    return categories_by_type, accounts, transactions


# Looks up a category by name and type. Returns the category id, or None if not found. Avoids repeating thsi lookup in both add and edit.
def _resolve_category(db, category_name, trans_type):

    if not category_name or not trans_type:
        return None

    row = db.execute(
        """
        SELECT id
        FROM "categories"
        WHERE name = ?
        AND type = ?
        """,
        (category_name, trans_type)
    ).fetchone()

    return row['id'] if row else None


#  Validates and resolves a submittde transaction form. Regardless of whether it came from Add or Edit.
def _parse_transaction_form(db, form, user_id):
    """
    Returns (data_dict, None) on success, or (none, error_response) on failure.
    data_dict keys:
    date,
    transaction_type
    category_id,
    sub_category,
    amount,
    details,
    card_id.
    """

    date = form.get("date")
    trans_type = form.get("type")
    category_name = form.get("category")
    sub_category = form.get("sub_category")
    amount_str = form.get("amount")
    details = form.get("details")
    account_name = form.get("card_id")

    missing = validate_required({
        'date': date,
        'type': trans_type,
        'category': category_name,
        'amount': amount_str,
        'details': details,
        'account': account_name,
    })

    if missing:
        return None, apology(f"{missing} is required.", 400)

    if trans_type not in VALID_TYPES:
        return None, apology(f"Invalid transaction type.", 400)

    try:
        amount = float(amount_str)
        if amount <= 0:
            return None, apology("Amount must be greater than zero.", 400)
    except ValueError:
        return None, apology("Invalid amount format.", 400)

    category_id = _resolve_category(db, category_name, trans_type)
    if not category_id:
        return None, apology("Invalid category for this transaction type.", 400)

    card_id = resolve_account(db, account_name, user_id)
    if not card_id:
        return None, apology("Invalid account selection.", 400)

    data = {
        'date': date,
        'transaction_type': trans_type,
        'category_id': category_id,
        'sub_category': sub_category,
        'amount': amount,
        'details': details,
        'card_id': card_id,
    }

    return data, None




@budget_tracking_bp.route("/budget_tracking", methods=["GET", "POST"])
@login_required
def budget_tracking():
    """Track the user's expenditures and add new transactions"""

    # Get a FRESH connection for this request
    db = get_db()

    # --- HANDLE FORM SUBMISSION (POST) ---
    if request.method =="POST":
        action = request.form.get("action")

        # --- ADDING A TRANSACTION --- #
        if action == "addtransaction":

            data, error = _parse_transaction_form(db, request.form, session['user_id'])
            if error:
                return error

            last_transaction = db.execute(
                """
                SELECT balance
                FROM "transactions"
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                LIMIT 1
                """,
                (session['user_id'],)
            ).fetchone()

            # Claude assisted to help build the running balance
            current_balance = float(last_transaction['balance']) if last_transaction else 0.0
            current_balance += data['amount'] if data['transaction_type'] == 'income' else -data['amount']

            db_insert(db, table='transactions', data={
                **data,
                'balance': current_balance,
                'effective_date': None,
                'user_id': session['user_id'],
            })

            recalculate_balances(db, session['user_id'], data['date'])
            flash("Transaction added successfully", "success")
            return redirect("/budget_tracking")

        # --- DELETE A TRANSACTION --- #
        elif action == "deletetransaction":

            transaction_id = request.form.get("transaction_id")
            if not transaction_id:
                return apology("No transaction specified.", 400)

            try:
                transaction_id = int(transaction_id)
            except ValueError:
                return apology("Invalid transaction ID.", 400)

            transaction = db.execute(
                """
                SELECT date
                FROM "transactions"
                WHERE id = ?
                AND user_id = ?
                """,
                (transaction_id, session['user_id'])
            ).fetchone()

            if not transaction:
                return apology("Transaction not found or access denied.", 403)

            deleted_date = transaction['date']

            db_delete(db,
                      table='transactions',
                      where={'id': transaction_id,
                             'user_id': session['user_id']
                             })

            recalculate_balances(db, session['user_id'], deleted_date)
            flash("Transaction deleted successfully", "success")
            return redirect("/budget_tracking")

        # --- EDIT A TRANSACTION --- #
        elif action == "edittransaction":

            transaction_id = request.form.get("transaction_id")
            if not transaction_id:
                return apology("No transaction specified.", 400)

            try:
                transaction_id = int(transaction_id)
            except ValueError:
                return apology("Invalid transaction ID.", 400)

            old_transaction = db.execute(
                """
                SELECT date
                FROM "transactions"
                WHERE id = ? AND user_id = ?
                """,
                (transaction_id, session["user_id"])
            ).fetchone()

            if not old_transaction:
                return apology("Transaction not found or access denied.", 403)

            data, error = _parse_transaction_form(db, request.form, session['user_id'])
            if error:
                return error

            db_update(db,
                      table='transactions',
                      data = data,
                      where={'id': transaction_id,
                             'user_id': session['user_id']
                             })

            recalculate_balances(db, session['user_id'], min(old_transaction['date'], data['date']))
            flash("Transaction updated successfully!", "success")
            return redirect("/budget_tracking")

        # --- SEARCH THROUGH TRANSACTIONS --- #
        elif action == "filtertransaction":

            date_filter = request.form.get("date")
            type_filter = request.form.get("type")
            category_filter = request.form.get("category")
            sub_filter = request.form.get("sub_category")
            amount_filter = request.form.get("amount")
            details_filter = request.form.get("details")
            account_filter = request.form.get("card_id")

            # Claude Assisted to build this concatenation of strings to filter transactions
            query = """
                SELECT t.*, c.name as category_name, b.account_name as account_name
                FROM "transactions" t
                JOIN categories c ON t.category_id = c.id
                JOIN bank_accounts b ON t.card_id = b.id
                WHERE t.user_id = ?
            """
            params = [session['user_id']]

            if date_filter:
                query += " AND t.date = ?"
                params.append(date_filter)

            if type_filter:
                query += " AND t.transaction_type = ?"
                params.append(type_filter)

            if category_filter and type_filter:
                cat_id = _resolve_category(db, category_filter, type_filter)
                if cat_id:
                    query += " AND t.category_id = ?"
                    params.append(cat_id)

            if sub_filter:
                query += " AND t.sub_category LIKE ?"
                params.append(f"%{sub_filter}%")

            if amount_filter:
                try:
                    amt_val = float(amount_filter)
                except ValueError:
                    amt_val = None
                if amt_val is not None:
                    query += " AND t.amount = ?"
                    params.append(amt_val)

            if details_filter:
                query += " AND t.details LIKE ?"
                params.append(f"%{details_filter}%")

            if account_filter:
                acc_id = resolve_account(db, account_filter, session['user_id'])
                if acc_id:
                    query += " AND t.card_id = ?"
                    params.append(acc_id)

            query += " ORDER BY t.date DESC"

            filtered = db.execute(query, params).fetchall()
            categories_by_type, accounts, _ = _get_page_data(db, session['user_id'], transactions=filtered)

            flash("Transactions filtered successfully!", "success")
            return render_template("budget_tracking.html",
                            categories=categories_by_type,
                            accounts=accounts,
                            transactions=filtered)
        else:
            return apology("Invalid action.", 400)


    # --- HANDLE PAGE LOAD (GET) ---
    if request.method =="GET":

        categories_by_type, accounts, transactions = _get_page_data(db, session['user_id'])
        return render_template("budget_tracking.html",
                            categories=categories_by_type,
                            accounts=accounts,
                            transactions=transactions)
