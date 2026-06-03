"""
Couche base de données unifiée.
- En local (pas de DATABASE_URL) : SQLite
- Sur Render (DATABASE_URL défini) : PostgreSQL
"""
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

if USE_PG:
    import psycopg2
    import psycopg2.extras


def get_db():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        DB_PATH = os.path.join(os.path.dirname(__file__), "fund.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def q(sql):
    """Adapte les ? SQLite en %s PostgreSQL."""
    if USE_PG:
        return sql.replace("?", "%s")
    return sql


def fetchall(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def fetchone(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    row = cur.fetchone()
    return dict(row) if row else None


def execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    return cur


def init_db():
    conn = get_db()
    if USE_PG:
        conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS investisseurs (
                id SERIAL PRIMARY KEY,
                nom TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                depot_total REAL DEFAULT 0,
                part_pct REAL DEFAULT 0,
                role TEXT DEFAULT 'investor',
                date_entree DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS soldes (
                id SERIAL PRIMARY KEY,
                date DATE UNIQUE NOT NULL,
                solde REAL NOT NULL,
                gain_jour REAL DEFAULT 0,
                pct_jour REAL DEFAULT 0,
                gain_total REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS gains_investisseurs (
                id SERIAL PRIMARY KEY,
                solde_id INTEGER REFERENCES soldes(id),
                investisseur_id INTEGER REFERENCES investisseurs(id),
                investisseur_nom TEXT,
                gain REAL DEFAULT 0,
                part_pct REAL DEFAULT 0,
                date DATE NOT NULL
            );
        """)
    else:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS investisseurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                depot_total REAL DEFAULT 0,
                part_pct REAL DEFAULT 0,
                role TEXT DEFAULT 'investor',
                date_entree DATE DEFAULT (date('now')),
                created_at TIMESTAMP DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS soldes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                solde REAL NOT NULL,
                gain_jour REAL DEFAULT 0,
                pct_jour REAL DEFAULT 0,
                gain_total REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS gains_investisseurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solde_id INTEGER REFERENCES soldes(id),
                investisseur_id INTEGER REFERENCES investisseurs(id),
                investisseur_nom TEXT,
                gain REAL DEFAULT 0,
                part_pct REAL DEFAULT 0,
                date DATE NOT NULL
            );
        """)
    conn.commit()
    conn.close()
