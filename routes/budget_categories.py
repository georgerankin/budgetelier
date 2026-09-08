from flask import Blueprint, render_template, request, redirect, session, flash
from helpers import (apology, get_db, login_required,
                     validate_required, check_duplicate, db_insert, db_update, db_delete)

budget_categories_bp = Blueprint('budget_categories', __name__)

ADD_ACTION_MAP = {
    'addincomecategory': ('income', 'new_income_category'),
    'addexpensescategory': ('expenses', 'new_expenses_category'),
    'addsavingscategory': ('savings', 'new_savings_category'),
}

# Extract type: "deleteincomecategory" -> "income"
def _extract_type(action, prefix): # Claude assisted for simpler transaction type definition
    return action.replace(prefix, '').replace('category', '')

@budget_categories_bp.route("/budget_categories", methods=["GET", "POST"])
@login_required
def budget_categories():

    # Get a FRESH connection for this request
    db = get_db()

    # --- HANDLE FORM SUBMISSION (POST) ---
    if request.method == "POST":

        action = request.form.get("action")

        # --- DELETE A CATEGORY --- #
        if action and action.startswith("delete"):

            cat_type = _extract_type(action, 'delete')
            cat_id = request.form.get("category_id")

            if not cat_id:
                return apology("No category specified.", 400)

            db_delete(db,
                      table='categories',
                      where={'id': int(cat_id), 'type': cat_type})

            flash(f"{cat_type.capitalize()} category deleted.", "success")
            return redirect("/budget_categories")

        # --- EDITING A CATEGORY --- #
        elif action and action.startswith("edit"):

            cat_type = _extract_type(action, 'edit')
            cat_id = request.form.get("category_id")
            new_name = request.form.get("new_name").strip()

            missing = validate_required({'category ID': cat_id, 'name': new_name})
            if missing:
                return apology(f"{missing} is required.", 400)

            if check_duplicate(db, 'categories', 'name', new_name,
                               exclude_id=int(cat_id),
                               extra_conditions={'type': cat_type}):
                return apology(f"category '{new_name}' already exists.", 400)

            db_update(db,
                      table='categories',
                      data={'name': new_name},
                      where={'id': int(cat_id), 'type': cat_type})

            flash(f"{cat_type.capitalize()} category updated successfully.", "success")
            return redirect("/budget_categories")

        # --- ADDING A CATEGORY --- #
        elif action and action.startswith ("add"):

            if action not in ADD_ACTION_MAP:
                return apology(f"Invalid: Action: {action}", 400)

            cat_type, form_field = ADD_ACTION_MAP[action]
            new_name = request.form.get(form_field, "").strip()

            missing = validate_required({'category name': new_name})
            if missing:
                return apology(f"Category name cannot be empty for {cat_type}.", 400)

            if check_duplicate(db, 'categories', 'name', new_name,
                               extra_conditions={'type': cat_type}):
                return apology(f"Category '{new_name}' already exists in {cat_type}.", 400)

            db_insert(db,
                      table='categories',
                      data={'type': cat_type, 'name': new_name, 'description': ''})

            flash(f"{cat_type.capitalize()} category '{new_name}' added successfully", "success")
            return redirect("/budget_categories")

        else:
            return apology("Invalid action.", 400)

    # User reached route via GET (entering the URL)
    if request.method == "GET":

        all_categories = db.execute(
            """
            SELECT id, type, name
            FROM categories
            ORDER BY type, name
            """
        ).fetchall()

        categories_by_type = {
            'income': [],
            'expenses': [],
            'savings': []
        }

        for cat in all_categories: 
            if cat['type'] in categories_by_type:
                categories_by_type[cat['type']].append({
                    'id' : cat['id'],
                    'name' : cat['name'],
                })

        return render_template("budget_categories.html",
                               categories=categories_by_type)
