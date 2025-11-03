import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")  # Change for production

# --- Admin password setup ---
admin_hash_env = os.environ.get("ADMIN_PASSWORD_HASH")
admin_plain_env = os.environ.get("ADMIN_PASSWORD")

if admin_hash_env:
    app.config["ADMIN_PASSWORD_HASH"] = admin_hash_env
elif admin_plain_env:
    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(admin_plain_env)
else:
    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("admin123")
    print("WARNING: Using default admin password 'admin123'. Set ADMIN_PASSWORD or ADMIN_PASSWORD_HASH in environment for production.")

# --- Login required decorator ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated

# --- Admin required decorator ---
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login", next=request.path))
        if not session.get("is_admin"):
            next_url = request.path
            return redirect(url_for("admin_login", next=next_url))
        return f(*args, **kwargs)
    return decorated

# --- Routes ---
@app.route("/")
def index():
    return "Welcome! <a href='/groups/manage'>Manage Groups</a>"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        if username:
            session["username"] = username
            return redirect(request.args.get("next") or "/")
        flash("Username required")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin/login", methods=["GET", "POST"])
@login_required
def admin_login():
    next_url = request.args.get("next") or url_for("manage_groups")
    if session.get("is_admin"):
        return redirect(next_url)

    if request.method == "POST":
        password = request.form.get("password")
        admin_hash = app.config.get("ADMIN_PASSWORD_HASH")
        if check_password_hash(admin_hash, password):
            session["is_admin"] = True
            return redirect(next_url)
        flash("Invalid admin password")
        return redirect(url_for("admin_login", next=next_url))

    return render_template("admin_login.html", next=next_url)

@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/")

@app.route("/groups/manage")
@admin_required
def manage_groups():
    return "Welcome to the Management Page! Only admins can see this."

# --- Templates ---
# You can place these in `templates/login.html` and `templates/admin_login.html`

# templates/login.html
"""
<!doctype html>
<html>
<head><title>Login</title></head>
<body>
  <h1>Login</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul>
      {% for m in messages %}<li style="color:red;">{{ m }}</li>{% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
  <form method="post">
    <label>Username:</label>
    <input type="text" name="username" required>
    <button type="submit">Login</button>
  </form>
</body>
</html>
"""

# templates/admin_login.html
"""
<!doctype html>
<html>
<head><title>Admin Login</title></head>
<body>
  <h1>Admin Access Required</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul>
      {% for m in messages %}<li style="color:red;">{{ m }}</li>{% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
  <form method="post" action="{{ url_for('admin_login') }}">
    <input type="hidden" name="next" value="{{ next }}">
    <label>Admin Password:</label>
    <input type="password" name="password" autofocus required>
    <button type="submit">Unlock</button>
  </form>
  <p><a href="{{ url_for('logout') }}">Logout</a></p>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)
