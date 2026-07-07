from flask import Blueprint, render_template, request, redirect, session, flash
from helpers import (apology, get_db, login_required, resolve_account)

budget_planning_bp = Blueprint('budget_planning', __name__)

MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

# Define new helper function in simple SQL
def _get_page_data(db):
    """
    Returns
    - categories_by_type - Dicts of Lists: {'income': [{'id': ..., 'name': ...}, ...], ...}
    - accounts - List of Rows: [{'id': ..., 'account_name': ...}, ...]
    """
    rows = db.execute(
        """
        SELECT id, type, name
        FROM "categories"
        ORDER BY type, name
        """
    ).fetchall()

    categories_by_type = { # Creates an empty dictionary for each type
            'income': [],
            'expenses': [],
            'savings': []
        }

    for row in rows: # For each category...
            if row['type'] in categories_by_type: # ... assigns a type if found in list
                categories_by_type[row['type']].append({ # and appends its Id and name
                     'id' : row['id'],
                     'name' : row['name']
                     })

    accounts = db.execute(
        """
        SELECT id, account_name
        FROM "bank_accounts"
        WHERE user_id = ?
        """,
        (session['user_id'],)
    ).fetchall()

    return categories_by_type, accounts


def _get_existing_budgets(db, year):
    """
    Returns
    - existing_budgets = {(category_id, month_number): target_budget}
    It's like a spreadsheet: Column[Category] by Row[Month] = Cell[budget]

    - existing_accounts - {category_id: bank_account_id}
    """
    rows = db.execute(
        """
        SELECT category_id, month, target_budget, bank_account_id
        FROM "budget"
        WHERE year = ?
        """,
        (year,)
    ).fetchall()

    existing_budgets = {}
    existing_accounts = {}

    for row in rows:
        existing_budgets[(row['category_id'], row['month'])] = row['target_budget']
        existing_accounts[row['category_id']] = row['bank_account_id']

    return existing_budgets, existing_accounts


# Returns a flat list of every category_id added to the db
def _collect_category_ids(db):
    rows = db.execute(
        """
        SELECT id
        FROM "categories"
        """
    ).fetchall()

    return [row['id'] for row in rows]


# Read through submitted form, validate every input, returns clean data for db.commit()
def _parse_and_validate(db, category_ids):
    """
    Returns a big tuple:
    - resolved_accounts - {category_id: bank_account_id}
    - data_by_month - {month_abbr: {category_id: float}}
    - active_months - [month_abbr, ...] (Months where every cell is populated)
    """

    # --- 1. Resolve and validate every account dropdown --- #
    resolved_accounts = {}
    for cat_id in category_ids:
        raw_name = request.form.get(f"account_{cat_id}", "").strip()
        if not raw_name:
            return apology(f"Select an account for every category row.", 400), None, None

        account_id = resolve_account(db, raw_name, session['user_id'])
        if account_id is None:
            return apology("Invalid account selected.", 400), None, None

        resolved_accounts[cat_id] = account_id

    # --- 2. Build data_by_month from the budget's user inputted cells --- #
    # For future ref: Each cell is named "budget_<cat_id>_<month_lower>" in HTML
    # Results in {'JAN': {1: '100', 2: '50'}, 'FEB': {1: '75', 2: '150'}, ...}
    data_by_month = {}
    for month in MONTHS:
        for cat_id in category_ids:
            key = f"budget_{cat_id}_{month.lower()}"
            value = request.form.get(key, "").strip()
            data_by_month.setdefault(month, {})[cat_id] = value

    # --- 3. Claude Assisted: Identify active months that have at least one cell populated --- #
    active_months = [
        month for month, cells in data_by_month.items()
        if any(v != "" for v in cells.values())
    ]

    # --- 4. Claude Assisted: Validate active months must be fully populated --- #
    for month in active_months:
        for cat_id, value in data_by_month[month].items():
            if value == "":
                return apology(f"Fill every category for {month} or leave the whole column blank", 400), None, None

    # --- 5. Validate every value must be a non-negative number --- #
    for month in active_months:
        for cat_id, value in data_by_month[month].items():
            try:
                amount = float(value)
                if amount < 0:
                    return apology("Budget values cannot be negative.", 400), None, None
            except ValueError:
                return apology(f"'{value}' is not a valid number in {month}.", 400), None, None

    return resolved_accounts, data_by_month, active_months

# Upserts every validated user entry to database in a single commit.
# INSERT... ON CONFLICT ... DO UPDATE allows re-submission and avoids crashing
def _upsert_budget(db, resolved_accounts, data_by_month, active_months, year):

    for month in active_months:
        month_number = MONTHS.index(month) + 1
        for cat_id, value in data_by_month[month].items():
            db.execute(
                """
                INSERT INTO "budget"
                    (category_id, year, month, target_budget, bank_account_id)
                VALUES
                    (?, ?, ?, ?, ?)
                ON CONFLICT (category_id, year, month) DO UPDATE
                SET target_budget = excluded.target_budget,
                    bank_account_id = excluded.bank_account_id
                """,
                (cat_id, year, month_number, float(value), resolved_accounts[cat_id])
            )
    db.commit()




@budget_planning_bp.route("/budget_planning", methods=["GET", "POST"])
@login_required
def budget_planning():

    # Get a FRESH connection for this request
    db = get_db()
    selected_year = 2026 # Hardcoded year but will adjust later

    #--- HANDLE FORM SUBMISSION(POST) --- #
    if request.method == "POST":

        action = request.form.get("action")

        #--- UPDATING THE BUDGET ---#
        if action == "updatebudget":

            category_ids = _collect_category_ids(db)

            resolved_accounts, data_by_month, active_months = _parse_and_validate(db, category_ids)

            if isinstance(resolved_accounts, tuple):
                return resolved_accounts

            if not active_months: # Claude assisted
                flash("Nothing to save - fill in at least one complete month column.", "warning")
                return redirect("/budget_planning")

            _upsert_budget(db, resolved_accounts, data_by_month, active_months, selected_year)

            flash("Budget updated successfully", "success")
            return redirect("/budget_planning")

    #--- HANDLE PAGE LOAD(GET) --- #
    if request.method == "GET":

        categories_by_type, accounts = _get_page_data(db)
        existing_budgets, existing_accounts = _get_existing_budgets(db, selected_year)
        return render_template("budget_planning.html",
                               months=MONTHS,
                               categories=categories_by_type,
                               accounts=accounts,
                               existing_budgets=existing_budgets,
                               existing_accounts=existing_accounts,
                               selected_year=selected_year)
