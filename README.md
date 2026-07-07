# Budgetelier

#### Video Demo:  <[Budgetelier Video Demo](https://youtu.be/eT9XTjaSbBs)>

#### Description:

Budgetelier is a personal finance web application built with Flask, SQLite, and Bootstrap that allows a user to register an account, log in, record income/expense/savings transactions against their own bank accounts and categories, and automatically keeps a running balance across all of their transactions.

The project grew out of a simple desire to track day-to-day spending without relying on a spreadsheet, but with the guardrails a spreadsheet doesn't give you for free: input validation, per-user data isolation, and automatic recalculation of running balances whenever a transaction is added, edited, or deleted out of chronological order.

**Core features**

- **Accounts & authentication** — users register with a username and password (hashed with Werkzeug's `generate_password_hash`), and all pages under the main navigation require an active session via a `login_required` decorator.
- **Bank accounts & categories** — before tracking transactions, a user sets up their own bank accounts (e.g. "N26 Personal", "Trade Republic") and categories under three fixed types: income, expenses, and savings. Both support inline add/edit/delete directly from the page, using small AJAX calls so the table refreshes without a full page reload.
- **Transaction tracking** — the heart of the app. Users can add a transaction, edit it in place, delete it, or filter the transaction history by any combination of date, type, category, sub-category, amount, details, or account.
- **Running balances** — every transaction stores its own balance-after-transaction. Whenever a transaction is inserted, edited, or deleted, `recalculate_balances()` walks forward from the earliest affected date and recomputes every balance after it, so editing a transaction from three weeks ago correctly ripples forward through everything since.

**File structure and what each file does**

- `app.py` — creates the Flask app, registers each feature's Blueprint, configures filesystem-based sessions (so login state survives server restarts, unlike signed cookies), and disables response caching so a logged-out user can't hit the back button and see stale authenticated pages. It also defines the `/` route, which looks up the logged-in user's name for the dashboard.
- `helpers.py` — shared utilities used across every route. This includes `get_db()` (opens a fresh per-request SQLite connection with foreign keys enabled, which avoids the "SQLite objects created in a thread" error that comes from reusing a single global connection), `login_required` (a decorator function that redirects anonymous visitors to `/login`), `apology()` (renders a memegen-powered error page), and a small set of generic query builders — `db_insert`, `db_update`, and `db_delete` — that build parameterized SQL from a dictionary of column/value pairs, so every route doesn't need to hand-write its own `INSERT`/`UPDATE`/`DELETE` statements. `recalculate_balances()` is the most lenghtly function here: it accepts an optional `start_date` so it only has to recompute balances from the point of change forward, instead of replaying a user's entire transaction history on every edit.
- `routes/auth.py` — registration, login, and logout. Passwords are never stored in plaintext; only their hash is persisted, and the login route checks the hash against the submitted password with `check_password_hash`.
- `routes/budget_tracking.py` — It handles adding, editing, deleting, and filtering transactions. Add and edit share a single `_parse_transaction_form()` helper so the same validation rules (required fields, positive amount, valid category-for-type, valid account ownership) can't silently drift apart between the two code paths. Category and account names are resolved to their database IDs server-side rather than trusted from the form, so a user can't submit a category or account that isn't actually theirs.
- `routes/budget_categories.py` and `routes/budget_bankaccounts.py` — near-identical CRUD routes for the two setup pages, each preventing duplicate names and validating input before writing to the database.
- `routes/budget_planning.py` — a Blueprint referenced in `app.py` for a planning/budgeting view planned alongside tracking.
- `templates/` — Jinja templates extending a shared `layout.html`, which provides the Bootstrap navbar (with links conditional on login state) and a consistent uniform page setup. `budget_tracking.html` includes the inline "edit in place" UI, with the category dropdown data passed from Python to JavaScript via Jinja's `tojson` filter so the same category list doesn't need a second AJAX round-trip.
- `finances.db` — the SQLite database, with `users`, `bank_accounts`, `categories`, and `transactions` tables, tied together with foreign keys (e.g. deleting a bank account cascades to its transactions).

**Design decisions worth calling out**

I initially wrote each route's SQL by hand, but this led to a lot of near-duplicate `INSERT`/`UPDATE` statements that were easy to get subtly wrong (mismatched column counts, forgotten commits). Centralizing that into `db_insert`/`db_update`/`db_delete` in `helpers.py` made every route both shorter and safer, since query parameterization and commits are handled in one place instead of many. Similarly, extracting `_resolve_category()` and `_resolve_account()` meant that "does this category/account actually belong to this user?" is checked identically everywhere it matters, rather than being re-implemented (and potentially forgotten) in each route.
