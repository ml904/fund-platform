import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "fund.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
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
