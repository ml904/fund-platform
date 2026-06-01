import os
import hashlib
import io
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from dotenv import load_dotenv
from database import init_db, get_db
import fund_logic
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def seed_admin():
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM investisseurs").fetchone()[0]
    if count == 0:
        db.execute(
            "INSERT INTO investisseurs (nom, password_hash, depot_total, role) VALUES (?,?,?,?)",
            ("Malick", hash_password("admin123"), 76.0, "admin")
        )
        db.commit()
        print("Admin créé : Malick / admin123")
    db.close()


# Initialisation au démarrage (gunicorn + dev)
init_db()
seed_admin()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    row = db.execute("SELECT * FROM investisseurs WHERE id=?", (uid,)).fetchone()
    db.close()
    return dict(row) if row else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("role") != "admin":
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM investisseurs WHERE nom=?", (nom,)).fetchone()
        db.close()
        if row and row["password_hash"] == hash_password(password):
            session["user_id"] = row["id"]
            return redirect(url_for("dashboard"))
        error = "Nom ou mot de passe incorrect."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("investor_dashboard"))


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    stats = fund_logic.get_admin_stats()
    today = date.today().isoformat()
    return render_template("dashboard_admin.html", stats=stats, today=today, user=current_user())


@app.route("/investor")
@login_required
def investor_dashboard():
    user = current_user()
    stats = fund_logic.get_investor_stats(user["id"])
    return render_template("dashboard_investor.html", stats=stats, user=user)


# ── Solde ─────────────────────────────────────────────────────────────────────

@app.route("/admin/solde", methods=["POST"])
@login_required
@admin_required
def save_solde():
    date_str = request.form.get("date", date.today().isoformat())
    try:
        solde = float(request.form.get("solde", ""))
    except ValueError:
        flash("Solde invalide.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    existing = db.execute("SELECT id FROM soldes WHERE date=?", (date_str,)).fetchone()
    db.close()
    if existing:
        flash("Un solde existe déjà pour cette date.", "error")
        return redirect(url_for("admin_dashboard"))

    fund_logic.save_solde(date_str, solde)
    flash("Solde enregistré avec succès.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Investisseurs ─────────────────────────────────────────────────────────────

@app.route("/admin/investisseur/ajouter", methods=["POST"])
@login_required
@admin_required
def add_investor():
    nom = request.form.get("nom", "").strip()
    password = request.form.get("password", "")
    try:
        depot = float(request.form.get("depot", 0) or 0)
    except ValueError:
        depot = 0.0

    if not nom or not password:
        flash("Nom et mot de passe requis.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    existing = db.execute("SELECT id FROM investisseurs WHERE nom=?", (nom,)).fetchone()
    if existing:
        db.close()
        flash("Ce nom existe déjà.", "error")
        return redirect(url_for("admin_dashboard"))

    db.execute(
        "INSERT INTO investisseurs (nom, password_hash, depot_total, role) VALUES (?,?,?,?)",
        (nom, hash_password(password), depot, "investor")
    )
    db.commit()
    db.close()
    flash(f"Investisseur {nom} créé.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/investisseur/modifier", methods=["POST"])
@login_required
@admin_required
def edit_investor():
    investor_id = request.form.get("investor_id", "")
    try:
        nouveau_depot = float(request.form.get("depot_total", ""))
    except ValueError:
        flash("Montant invalide.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    db.execute("UPDATE investisseurs SET depot_total=? WHERE id=?", (nouveau_depot, investor_id))
    db.commit()
    db.close()
    flash("Dépôt mis à jour.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/investisseur/fonds", methods=["POST"])
@login_required
@admin_required
def add_funds():
    investor_id = request.form.get("investor_id", "")
    try:
        montant = float(request.form.get("montant", ""))
    except ValueError:
        flash("Montant invalide.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    row = db.execute("SELECT depot_total FROM investisseurs WHERE id=?", (investor_id,)).fetchone()
    if not row:
        db.close()
        flash("Investisseur introuvable.", "error")
        return redirect(url_for("admin_dashboard"))

    db.execute(
        "UPDATE investisseurs SET depot_total=? WHERE id=?",
        (row["depot_total"] + montant, investor_id)
    )
    db.commit()
    db.close()
    flash("Fonds ajoutés.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Export Excel ──────────────────────────────────────────────────────────────

def make_excel(headers, rows, sheet_name="Historique"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    header_fill = PatternFill("solid", fgColor="0d1117")
    header_font = Font(bold=True, color="00e87a")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[cell.column_letter].width = max(len(h) + 4, 14)

    for row in rows:
        ws.append(list(row))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@app.route("/admin/export")
@login_required
@admin_required
def export_admin():
    db = get_db()
    soldes = db.execute("SELECT * FROM soldes ORDER BY date DESC").fetchall()
    investors = db.execute("SELECT * FROM investisseurs").fetchall()
    gains = db.execute("SELECT * FROM gains_investisseurs ORDER BY date DESC").fetchall()
    db.close()

    wb = openpyxl.Workbook()

    # Feuille 1 : Historique soldes
    ws1 = wb.active
    ws1.title = "Soldes"
    h1 = ["Date", "Solde (USDT)", "Gain jour", "% jour", "Gain total"]
    hf = PatternFill("solid", fgColor="0d1117")
    hfont = Font(bold=True, color="00e87a")
    for col, h in enumerate(h1, 1):
        c = ws1.cell(row=1, column=col, value=h)
        c.font = hfont; c.fill = hf
        ws1.column_dimensions[c.column_letter].width = 18
    for s in soldes:
        ws1.append([s["date"], s["solde"], s["gain_jour"], s["pct_jour"], s["gain_total"]])

    # Feuille 2 : Investisseurs
    ws2 = wb.create_sheet("Investisseurs")
    h2 = ["Nom", "Dépôt (USDT)", "Rôle", "Membre depuis"]
    for col, h in enumerate(h2, 1):
        c = ws2.cell(row=1, column=col, value=h)
        c.font = hfont; c.fill = hf
        ws2.column_dimensions[c.column_letter].width = 20
    for inv in investors:
        ws2.append([inv["nom"], inv["depot_total"], inv["role"], inv["date_entree"]])

    # Feuille 3 : Gains par investisseur
    ws3 = wb.create_sheet("Gains")
    h3 = ["Date", "Investisseur", "Part %", "Gain (USDT)"]
    for col, h in enumerate(h3, 1):
        c = ws3.cell(row=1, column=col, value=h)
        c.font = hfont; c.fill = hf
        ws3.column_dimensions[c.column_letter].width = 20
    for g in gains:
        ws3.append([g["date"], g["investisseur_nom"], g["part_pct"], g["gain"]])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, download_name="MO_Capital_historique.xlsx",
                     as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/investor/export")
@login_required
def export_investor():
    user = current_user()
    db = get_db()
    gains = db.execute(
        "SELECT * FROM gains_investisseurs WHERE investisseur_id=? ORDER BY date DESC",
        (user["id"],)
    ).fetchall()
    db.close()

    headers = ["Date", "Part %", "Gain (USDT)"]
    rows = [(g["date"], g["part_pct"], g["gain"]) for g in gains]
    buf = make_excel(headers, rows, "Mes gains")
    return send_file(buf, download_name=f"MO_Capital_{user['nom']}.xlsx",
                     as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
