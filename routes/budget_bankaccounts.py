from flask import Blueprint, render_template, request, redirect, session, flash
from helpers import (apology, get_db, login_required,
                     validate_required, check_duplicate, db_insert, db_update, db_delete)

budget_bankaccounts_bp = Blueprint('budget_bankaccounts', __name__)

@budget_bankaccounts_bp.route("/budget_bankaccounts", methods=["GET", "POST"])
@login_required
def budget_bankaccounts():

    # Get a FRESH connection for this request
    db = get_db()

    # --- HANDLE FORM SUBMISSION (POST) ---
    if request.method == "POST":

        action = request.form.get("action")

        #--- EDIT A BANK ACCOUNT ---#
        if action == "editbankaccount":

            bank_account_id = request.form.get("bank_account_id")
            new_name = request.form.get("new_name", "").strip()

            missing = validate_required({'bank account ID': bank_account_id, 'name': new_name})
            if missing:
                return apology(f"{missing} is required.", 400)

            if check_duplicate(db, 'bank_accounts', 'account_name', new_name,
                               exclude_id=bank_account_id):
                return apology(f"Bank Account: '{new_name}' already exists.", 400)

            db_update(db,
                      table='bank_accounts',
                      data={'account_name': new_name},
                      where={'id': bank_account_id})

            flash(f"{new_name.capitalize()} bank account updated successfully.", "success")
            return redirect("/budget_bankaccounts")

        #--- DELETE A BANK ACCOUNT ---#
        elif action == "deletebankaccount":

            bank_account_id = request.form.get("bank_account_id")

            if not bank_account_id:
                return apology("Invalid bank account ID.", 400)

            db_delete(db,
                      table='bank_accounts',
                      where={'id': bank_account_id, 'user_id': session['user_id']})

            flash("Bank account deleted.", "success")
            return redirect("/budget_bankaccounts")

        #--- ADD A BANK ACCOUNT ---#
        elif action == "addbankaccount":

            new_name = request.form.get("new_bank_card", "").strip()

            missing = validate_required({'bank account name': new_name})
            if missing:
                return apology("New Bank Account Name cannot be empty", 400)

            if check_duplicate(db, 'bank_accounts', 'account_name', new_name):
                return apology(f"Bank account '{new_name}' already exists.", 400)

            db_insert(db,
                      table='bank_accounts',
                      data={'user_id': session['user_id'],
                            'account_name': new_name,
                            'account_type': ''})

            flash(f"{new_name.capitalize()} added successfully", "success")
            return redirect("/budget_bankaccounts")

        else:
            return apology("Invalid action.", 400)

    # User reached route via GET (entering the URL)
    if request.method == "GET":

        all_bank_accounts = db.execute(
            """
            SELECT id, account_name, account_type
            FROM "bank_accounts"
            WHERE user_id = ?
            """,
            (session['user_id'],)
        ).fetchall()


        return render_template("budget_bankaccounts.html",
                               bank_accounts=all_bank_accounts)
