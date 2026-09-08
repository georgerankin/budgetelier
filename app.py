from flask import Flask, redirect, session, render_template
from flask_session import Session
from helpers import eur, get_db, login_required
from routes.auth import auth_bp
from routes.budget_tracking import budget_tracking_bp
from routes.budget_categories import budget_categories_bp
from routes.budget_bankaccounts import budget_bankaccounts_bp
from routes.budget_planning import budget_planning_bp

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["eur"] = eur

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Registers each blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(budget_tracking_bp)
app.register_blueprint(budget_categories_bp)
app.register_blueprint(budget_bankaccounts_bp)
app.register_blueprint(budget_planning_bp)

# Greets the user if logged in, otherwise requests a sign-in
@app.route("/")
@login_required
def index():

    db = get_db()

    user = db.execute(
        """
        SELECT username
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    username = user["username"]

    return render_template("dashboard.html",
                           username=username)

