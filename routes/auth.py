from flask import Blueprint, render_template, request, redirect, session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Get a FRESH connection for this request
    db = get_db()

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return apology("must provide credentials", 403)

        # Query database for username (whilst also checking for multiple)
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchall()

        # Ensure exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["password_hash"], password
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect any user to login form
    return redirect("/")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Get a FRESH connection for this request
    db = get_db()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        username = username.strip()
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure confirmation was also submitted
        elif not confirmation:
            return apology("must repeat password", 400)

        # Ensure that password and confirmation match
        elif password != confirmation:
            return apology("must match password and confirmation", 400)

        # Checks database whether username exists in database
        rows = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchall()

        # Check if that username is already duplicated in database
        if len(rows) != 0:
            return apology("username already exists", 400)

        # Otherwise insert username and password into database
        db.execute(
            """
            INSERT INTO users
            (username, password_hash)
            VALUES
            (?, ?)
            """,
            (username, generate_password_hash(password))
        )

        db.commit()

        # Return user to login page to start login flow
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
