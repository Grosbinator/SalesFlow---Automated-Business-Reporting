"""Stockage des données nettoyées (data/processed/) dans la base SQLite
data/salesflow.db.

La base relie les trois fichiers par des clés étrangères :
customers <- subscriptions (customer_id) <- payments (subscription_id),
ce qui permet de retrouver en SQL les abonnements et paiements d'un client.

Le script peut être relancé autant de fois que voulu : les tables ne sont
créées qu'une fois et chaque ligne est insérée ou mise à jour selon sa clé
primaire (pas de doublons).
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DB_FILE = ROOT_DIR / "data" / "salesflow.db"

# Tables dans l'ordre d'insertion : une table « parent » doit être remplie
# avant les tables qui la référencent, sinon les clés étrangères échouent.
TABLES = {
    "customers": ("customers_clean.csv", "customer_id"),
    "subscriptions": ("subscriptions_clean.csv", "subscription_id"),
    "payments": ("payments_clean.csv", "payment_id"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    signup_date     TEXT NOT NULL,      -- AAAA-MM-JJ
    country         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id      TEXT PRIMARY KEY,
    customer_id          TEXT NOT NULL,
    plan                 TEXT NOT NULL,
    monthly_price        REAL NOT NULL,
    start_date           TEXT NOT NULL,  -- AAAA-MM-JJ
    end_date             TEXT,           -- NULL = abonnement en cours
    status               TEXT NOT NULL,
    calculation_eligible INTEGER NOT NULL,  -- 1 = vrai, 0 = faux
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id           TEXT PRIMARY KEY,
    subscription_id      TEXT NOT NULL,
    payment_date         TEXT NOT NULL,  -- AAAA-MM-JJ
    amount               REAL NOT NULL,
    status               TEXT NOT NULL,
    payment_method       TEXT NOT NULL,
    calculation_eligible INTEGER NOT NULL,
    revenue_eligible     INTEGER NOT NULL,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (subscription_id)
);

-- Index sur les clés étrangères : accélèrent les jointures.
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer_id
    ON subscriptions (customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_subscription_id
    ON payments (subscription_id);
"""


def get_connection():
    """Ouvre la base (créée si absente) avec les clés étrangères activées."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_FILE)
    # SQLite n'applique pas les clés étrangères par défaut :
    # il faut les activer à chaque connexion.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables(connection):
    """Crée les tables et index s'ils n'existent pas encore."""
    connection.executescript(SCHEMA)


def table_columns(connection, table):
    """Renvoie la liste des colonnes d'une table, dans l'ordre du schéma."""
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def load_processed(filename):
    """Charge un CSV nettoyé, tout en texte (une cellule vide vaut "")."""
    path = PROCESSED_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    return pd.read_csv(path, dtype=str, keep_default_na=False)


def to_sql_value(value):
    """Convertit une valeur texte du CSV pour SQLite.

    "" devient NULL et "True"/"False" deviennent 1/0. Les nombres restent
    en texte : SQLite les convertit lui-même grâce au type REAL de la colonne.
    """
    if value == "":
        return None
    if value in ("True", "False"):
        return int(value == "True")
    return value


def upsert(connection, table, df, primary_key):
    """Insère les lignes de `df` dans `table` ; met à jour celles déjà présentes.

    ON CONFLICT ... DO UPDATE évite les doublons quand le script est relancé.
    (INSERT OR REPLACE supprimerait puis réinsérerait la ligne, ce qui
    casserait les clés étrangères des tables enfants.)
    """
    columns = table_columns(connection, table)

    missing_columns = set(columns) - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"{table} : colonnes manquantes : {sorted(missing_columns)}"
        )

    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column != primary_key
    )
    query = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({', '.join('?' * len(columns))}) "
        f"ON CONFLICT ({primary_key}) DO UPDATE SET {updates}"
    )

    rows = [
        tuple(to_sql_value(value) for value in row)
        for row in df[columns].itertuples(index=False)
    ]
    connection.executemany(query, rows)
    return len(rows)


def delete_missing(connection, table, df, primary_key):
    """Supprime de la base les lignes absentes du CSV (ex. ligne écartée par
    la validation), pour que la base reflète exactement data/processed/."""
    keys = set(df[primary_key])
    removed = [
        (key,)
        for (key,) in connection.execute(f"SELECT {primary_key} FROM {table}")
        if key not in keys
    ]
    connection.executemany(
        f"DELETE FROM {table} WHERE {primary_key} = ?", removed
    )
    return len(removed)


def count_rows(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def main():
    connection = get_connection()
    try:
        create_tables(connection)
        frames = {
            table: load_processed(filename)
            for table, (filename, _) in TABLES.items()
        }

        # Une seule transaction : si une ligne est refusée (clé étrangère
        # invalide, valeur manquante...), rien n'est enregistré.
        with connection:
            # Suppressions des enfants vers les parents, puis insertions
            # des parents vers les enfants : les clés étrangères restent valides.
            for table, (_, primary_key) in reversed(TABLES.items()):
                removed = delete_missing(connection, table, frames[table], primary_key)
                if removed:
                    print(f"{table} : {removed} ligne(s) absente(s) du CSV supprimée(s)")
            for table, (filename, primary_key) in TABLES.items():
                inserted = upsert(connection, table, frames[table], primary_key)
                print(f"{table} : {inserted} ligne(s) chargée(s) depuis {filename}")

        print(f"Base à jour : {DB_FILE}")
        for table in TABLES:
            print(f"  {table} : {count_rows(connection, table)} ligne(s)")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
