from database import get_db


def get_all_investors():
    db = get_db()
    rows = db.execute("SELECT * FROM investisseurs").fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_total_deposits():
    investors = get_all_investors()
    return sum(i["depot_total"] for i in investors)


def get_last_solde():
    db = get_db()
    row = db.execute("SELECT * FROM soldes ORDER BY date DESC LIMIT 1").fetchone()
    db.close()
    return dict(row) if row else None


def save_solde(date_str, nouveau_solde):
    last = get_last_solde()
    total_depot = get_total_deposits()

    if last:
        gain_jour = round(nouveau_solde - last["solde"], 4)
        pct_jour = round(gain_jour / last["solde"] * 100, 4) if last["solde"] else 0
    else:
        gain_jour = 0.0
        pct_jour = 0.0

    gain_total = round(nouveau_solde - total_depot, 4)

    db = get_db()
    cur = db.execute(
        "INSERT INTO soldes (date, solde, gain_jour, pct_jour, gain_total) VALUES (?,?,?,?,?)",
        (date_str, nouveau_solde, gain_jour, pct_jour, gain_total)
    )
    solde_id = cur.lastrowid

    investors = get_all_investors()
    total = sum(i["depot_total"] for i in investors)
    for inv in investors:
        part_pct = round(inv["depot_total"] / total * 100, 4) if total else 0
        gain_inv = round(gain_total * part_pct / 100, 4)
        db.execute(
            "INSERT INTO gains_investisseurs (solde_id, investisseur_id, investisseur_nom, gain, part_pct, date) VALUES (?,?,?,?,?,?)",
            (solde_id, inv["id"], inv["nom"], gain_inv, part_pct, date_str)
        )

    db.commit()
    db.close()


def get_investor_stats(investor_id):
    db = get_db()
    inv = dict(db.execute("SELECT * FROM investisseurs WHERE id=?", (investor_id,)).fetchone())
    last_row = db.execute("SELECT * FROM soldes ORDER BY date DESC LIMIT 1").fetchone()
    last = dict(last_row) if last_row else None

    total_depot = get_total_deposits()
    part_pct = round(inv["depot_total"] / total_depot * 100, 4) if total_depot else 0
    valeur_actuelle = round(last["solde"] * part_pct / 100, 4) if last else inv["depot_total"]
    gain_total = round(valeur_actuelle - inv["depot_total"], 4)

    gain_jour = 0.0
    if last:
        row = db.execute(
            "SELECT gain FROM gains_investisseurs WHERE investisseur_id=? AND date=?",
            (investor_id, last["date"])
        ).fetchone()
        if row:
            gain_jour = row["gain"]

    historique = [dict(r) for r in db.execute(
        "SELECT * FROM gains_investisseurs WHERE investisseur_id=? ORDER BY date DESC LIMIT 30",
        (investor_id,)
    ).fetchall()]

    db.close()
    return {
        "investor": inv,
        "part_pct": part_pct,
        "valeur_actuelle": valeur_actuelle,
        "gain_total": gain_total,
        "gain_jour": gain_jour,
        "historique": historique,
        "solde_actuel": last["solde"] if last else 0,
    }


def get_admin_stats():
    last = get_last_solde()
    investors = get_all_investors()
    total_depot = sum(i["depot_total"] for i in investors)

    solde_actuel = last["solde"] if last else 0
    gain_jour = last["gain_jour"] if last else 0
    pct_jour = last["pct_jour"] if last else 0
    gain_total = last["gain_total"] if last else 0

    for inv in investors:
        part = round(inv["depot_total"] / total_depot * 100, 4) if total_depot else 0
        inv["part_pct"] = part
        inv["valeur_actuelle"] = round(solde_actuel * part / 100, 4)
        inv["gain_total_inv"] = round(inv["valeur_actuelle"] - inv["depot_total"], 4)

    db = get_db()
    historique = [dict(r) for r in db.execute(
        "SELECT * FROM soldes ORDER BY date DESC LIMIT 30"
    ).fetchall()]
    db.close()

    return {
        "solde_actuel": solde_actuel,
        "gain_jour": gain_jour,
        "pct_jour": pct_jour,
        "gain_total": gain_total,
        "nb_investisseurs": len(investors),
        "total_depot": total_depot,
        "investors": investors,
        "historique": historique,
    }
