from database import get_db, fetchall, fetchone, execute


def get_all_investors():
    conn = get_db()
    rows = fetchall(conn, "SELECT * FROM investisseurs")
    conn.close()
    return rows


def get_total_deposits():
    return sum(i["depot_total"] for i in get_all_investors())


def get_last_solde():
    conn = get_db()
    row = fetchone(conn, "SELECT * FROM soldes ORDER BY date DESC LIMIT 1")
    conn.close()
    return row


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

    conn = get_db()
    cur = execute(conn,
        "INSERT INTO soldes (date, solde, gain_jour, pct_jour, gain_total) VALUES (?,?,?,?,?)",
        (date_str, nouveau_solde, gain_jour, pct_jour, gain_total)
    )
    # Récupérer l'id inséré
    from database import USE_PG
    if USE_PG:
        cur.execute("SELECT lastval()")
        solde_id = cur.fetchone()["lastval"]
    else:
        solde_id = cur.lastrowid

    investors = get_all_investors()
    total = sum(i["depot_total"] for i in investors)
    for inv in investors:
        part_pct = round(inv["depot_total"] / total * 100, 4) if total else 0
        gain_inv = round(gain_total * part_pct / 100, 4)
        execute(conn,
            "INSERT INTO gains_investisseurs (solde_id, investisseur_id, investisseur_nom, gain, part_pct, date) VALUES (?,?,?,?,?,?)",
            (solde_id, inv["id"], inv["nom"], gain_inv, part_pct, date_str)
        )

    conn.commit()
    conn.close()


def get_investor_stats(investor_id):
    conn = get_db()
    inv = fetchone(conn, "SELECT * FROM investisseurs WHERE id=?", (investor_id,))
    last = fetchone(conn, "SELECT * FROM soldes ORDER BY date DESC LIMIT 1")
    conn.close()

    total_depot = get_total_deposits()
    part_pct = round(inv["depot_total"] / total_depot * 100, 4) if total_depot else 0
    valeur_actuelle = round(last["solde"] * part_pct / 100, 4) if last else inv["depot_total"]
    gain_total = round(valeur_actuelle - inv["depot_total"], 4)

    gain_jour = 0.0
    if last:
        conn2 = get_db()
        row = fetchone(conn2,
            "SELECT gain FROM gains_investisseurs WHERE investisseur_id=? AND date=?",
            (investor_id, last["date"])
        )
        conn2.close()
        if row:
            gain_jour = row["gain"]

    conn3 = get_db()
    historique = fetchall(conn3,
        "SELECT * FROM gains_investisseurs WHERE investisseur_id=? ORDER BY date DESC LIMIT 30",
        (investor_id,)
    )
    conn3.close()

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

    conn = get_db()
    historique = fetchall(conn, "SELECT * FROM soldes ORDER BY date DESC LIMIT 30")
    conn.close()

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
