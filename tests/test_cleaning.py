"""Tests de src/cleaning.py.

Principe : on fabrique de petits jeux de données en mémoire (ou dans un
dossier temporaire) dont on connaît à l'avance les erreurs, puis on vérifie
que cleaning.py les détecte, avec le bon fichier, la bonne ligne et la
bonne colonne. Les vrais fichiers de data/ ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cleaning  # noqa: E402


# ---------------------------------------------------------------------------
# Jeux de données de référence : une ligne 100 % valide par fichier.
# Chaque test copie cette ligne et y casse UNE seule valeur.
# ---------------------------------------------------------------------------

VALID_CUSTOMER = {
    "customer_id": "C001",
    "company_name": "NovaTech",
    "email": "contact@novatech.example",
    "signup_date": "2026-01-12",
    "country": "France",
}

VALID_SUBSCRIPTION = {
    "subscription_id": "S001",
    "customer_id": "C001",
    "plan": "Starter",
    "monthly_price": "29.0",
    "start_date": "2026-01-12",
    "end_date": "",
    "status": "active",
}

VALID_PAYMENT = {
    "payment_id": "P001",
    "subscription_id": "S001",
    "payment_date": "2026-01-12",
    "amount": "29.0",
    "status": "success",
    "payment_method": "card",
}


def make_df(base, *overrides):
    """Construit un DataFrame de texte : une ligne par dictionnaire `overrides`,
    complétée avec les valeurs valides de `base`. Sans argument : une ligne valide."""
    overrides = overrides or ({},)
    return pd.DataFrame([{**base, **row} for row in overrides], dtype=str)


def found(anomalies):
    """Réduit les anomalies à (fichier, ligne, colonne) pour comparer simplement."""
    return {
        (a["file_name"], a["row_number"], a["column_name"])
        for a in anomalies
    }


# ---------------------------------------------------------------------------
# 1. Numéro de ligne : la base de tout le fichier d'anomalies
# ---------------------------------------------------------------------------

def test_row_number_matches_line_in_csv_file():
    """Le 1er enregistrement doit être signalé « ligne 2 » (la ligne 1 est
    l'en-tête), pour retrouver l'erreur directement dans le CSV."""
    anomalies = []
    cleaning.add_anomaly(anomalies, "payments.csv", 0, "amount", "x")
    cleaning.add_anomaly(anomalies, "payments.csv", 3, "amount", "x")
    assert [a["row_number"] for a in anomalies] == [2, 5]


# ---------------------------------------------------------------------------
# 2. Contrôles génériques
# ---------------------------------------------------------------------------

def test_check_missing_flags_empty_cells_only():
    df = make_df(VALID_CUSTOMER, {}, {"company_name": ""})
    anomalies = []
    cleaning.check_missing(anomalies, "customers.csv", df, "company_name")
    assert found(anomalies) == {("customers.csv", 3, "company_name")}


def test_check_duplicates_flags_every_occurrence():
    """Les deux lignes en double sont signalées, pas seulement la 2e :
    on ne sait pas laquelle est la bonne."""
    df = make_df(
        VALID_PAYMENT,
        {"payment_id": "P001"},
        {"payment_id": "P002"},
        {"payment_id": "P001"},
    )
    anomalies = []
    cleaning.check_duplicates(anomalies, "payments.csv", df, "payment_id")
    assert found(anomalies) == {
        ("payments.csv", 2, "payment_id"),
        ("payments.csv", 4, "payment_id"),
    }


def test_check_duplicates_ignores_empty_ids():
    """Deux identifiants vides ne sont pas des « doublons » : ils sont déjà
    signalés comme valeurs manquantes, inutile de les compter deux fois."""
    df = make_df(VALID_PAYMENT, {"payment_id": ""}, {"payment_id": ""})
    anomalies = []
    cleaning.check_duplicates(anomalies, "payments.csv", df, "payment_id")
    assert anomalies == []


@pytest.mark.parametrize("bad_date", ["2026-13-40", "2026-02-30", "12/01/2026", "abc"])
def test_check_dates_flags_invalid_dates(bad_date):
    df = make_df(VALID_PAYMENT, {"payment_date": bad_date})
    anomalies = []
    cleaning.check_dates(anomalies, "payments.csv", df, "payment_date")
    assert found(anomalies) == {("payments.csv", 2, "payment_date")}


def test_check_dates_accepts_valid_and_empty_dates():
    """Une date vide n'est pas « invalide » ici (c'est check_missing qui
    décide si le vide est permis) ; une date correcte passe."""
    df = make_df(VALID_PAYMENT, {}, {"payment_date": ""})
    anomalies = []
    cleaning.check_dates(anomalies, "payments.csv", df, "payment_date")
    assert anomalies == []


def test_check_numbers_flags_non_numeric_and_negative():
    df = make_df(
        VALID_PAYMENT,
        {"amount": "49.5"},   # ok
        {"amount": "abc"},    # non numérique
        {"amount": "-29.0"},  # négatif
        {"amount": "0"},      # zéro : accepté
    )
    anomalies = []
    cleaning.check_numbers(anomalies, "payments.csv", df, "amount", "Montant")
    assert found(anomalies) == {
        ("payments.csv", 3, "amount"),
        ("payments.csv", 4, "amount"),
    }


# ---------------------------------------------------------------------------
# 3. Relations entre fichiers
# ---------------------------------------------------------------------------

def test_check_references_flags_unknown_ids_only():
    customers = make_df(VALID_CUSTOMER, {"customer_id": "C001"})
    subscriptions = make_df(
        VALID_SUBSCRIPTION,
        {"customer_id": "C001"},
        {"customer_id": "C999"},
    )
    anomalies = []
    cleaning.check_references(
        anomalies,
        "subscriptions.csv",
        subscriptions,
        "customer_id",
        customers["customer_id"],
        "customers.csv",
    )
    assert found(anomalies) == {("subscriptions.csv", 3, "customer_id")}
    assert "C999" in anomalies[0]["error_message"]
    assert "customers.csv" in anomalies[0]["error_message"]


def test_subscription_with_unknown_customer_is_reported():
    """Cas demandé : un customer_id de subscriptions.csv absent de customers.csv."""
    customers = make_df(VALID_CUSTOMER)
    subscriptions = make_df(VALID_SUBSCRIPTION, {"customer_id": "C999"})
    anomalies = cleaning.check_subscriptions(subscriptions, customers)
    assert found(anomalies) == {("subscriptions.csv", 2, "customer_id")}


def test_payment_with_unknown_subscription_is_reported():
    """Un subscription_id de payments.csv absent de subscriptions.csv."""
    subscriptions = make_df(VALID_SUBSCRIPTION)
    payments = make_df(VALID_PAYMENT, {"subscription_id": "S999"})
    anomalies = cleaning.check_payments(payments, subscriptions)
    assert found(anomalies) == {("payments.csv", 2, "subscription_id")}


# ---------------------------------------------------------------------------
# 4. Règles propres à chaque fichier
# ---------------------------------------------------------------------------

def test_check_customers_flags_invalid_email():
    customers = make_df(
        VALID_CUSTOMER,
        {"customer_id": "C001"},
        {"customer_id": "C002", "email": "pas-un-email"},
    )
    anomalies = cleaning.check_customers(customers)
    assert found(anomalies) == {("customers.csv", 3, "email")}


def test_subscription_end_date_is_optional():
    """Un abonnement en cours n'a pas de date de fin : ce n'est pas une erreur."""
    customers = make_df(VALID_CUSTOMER)
    subscriptions = make_df(VALID_SUBSCRIPTION, {"end_date": ""})
    assert cleaning.check_subscriptions(subscriptions, customers) == []


def test_subscription_end_date_before_start_date_is_reported():
    customers = make_df(VALID_CUSTOMER)
    subscriptions = make_df(
        VALID_SUBSCRIPTION,
        {"start_date": "2026-05-01", "end_date": "2026-01-01"},
    )
    anomalies = cleaning.check_subscriptions(subscriptions, customers)
    assert found(anomalies) == {("subscriptions.csv", 2, "end_date")}


def test_payment_with_missing_amount_is_reported_once():
    """Un montant vide est signalé « manquant » uniquement (pas aussi
    « non numérique »), pour éviter les doublons dans le rapport."""
    subscriptions = make_df(VALID_SUBSCRIPTION)
    payments = make_df(VALID_PAYMENT, {"amount": ""})
    anomalies = cleaning.check_payments(payments, subscriptions)
    assert len(anomalies) == 1
    assert anomalies[0]["error_message"] == "Valeur manquante"


# ---------------------------------------------------------------------------
# 5. Pas de fausse alerte
# ---------------------------------------------------------------------------

def test_clean_data_produces_no_anomaly():
    """Des données correctes ne doivent produire AUCUNE anomalie : sinon le
    rapport serait noyé de fausses alertes et plus personne ne le lirait."""
    customers = make_df(VALID_CUSTOMER)
    subscriptions = make_df(VALID_SUBSCRIPTION)
    payments = make_df(VALID_PAYMENT)

    assert cleaning.check_customers(customers) == []
    assert cleaning.check_subscriptions(subscriptions, customers) == []
    assert cleaning.check_payments(payments, subscriptions) == []


# ---------------------------------------------------------------------------
# 6. Lecture des CSV et écriture du rapport (dans un dossier temporaire)
# ---------------------------------------------------------------------------

def write_csv(folder, name, df):
    df.to_csv(folder / name, index=False)


def test_load_csv_raises_if_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cleaning, "RAW_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        cleaning.load_csv("customers.csv")


def test_load_csv_raises_if_columns_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cleaning, "RAW_DIR", tmp_path)
    write_csv(tmp_path, "customers.csv", make_df(VALID_CUSTOMER).drop(columns=["email"]))
    with pytest.raises(ValueError, match="email"):
        cleaning.load_csv("customers.csv")


def test_load_csv_keeps_empty_cells_as_empty_text(tmp_path, monkeypatch):
    """Les cellules vides doivent rester "" (et pas NaN), sinon les contrôles
    de valeurs manquantes ne fonctionneraient pas."""
    monkeypatch.setattr(cleaning, "RAW_DIR", tmp_path)
    write_csv(tmp_path, "subscriptions.csv", make_df(VALID_SUBSCRIPTION))
    df = cleaning.load_csv("subscriptions.csv")
    assert df.at[0, "end_date"] == ""


@pytest.fixture
def output_dir(tmp_path, monkeypatch):
    """Redirige le rapport vers un dossier temporaire."""
    folder = tmp_path / "anomalies"
    monkeypatch.setattr(cleaning, "ANOMALIES_DIR", folder)
    monkeypatch.setattr(cleaning, "ANOMALIES_FILE", folder / "anomalies.csv")
    return folder


def test_save_anomalies_has_the_four_expected_columns(output_dir):
    anomalies = []
    cleaning.add_anomaly(anomalies, "payments.csv", 0, "amount", "Valeur manquante")
    cleaning.save_anomalies(anomalies)

    saved = pd.read_csv(output_dir / "anomalies.csv")
    assert list(saved.columns) == [
        "file_name", "row_number", "column_name", "error_message",
    ]
    assert saved.loc[0, "row_number"] == 2


def test_save_anomalies_writes_header_only_when_nothing_found(output_dir):
    cleaning.save_anomalies([])
    saved = pd.read_csv(output_dir / "anomalies.csv")
    assert saved.empty
    assert list(saved.columns) == cleaning.ANOMALY_COLUMNS


# ---------------------------------------------------------------------------
# 7. Test de bout en bout : main() sur trois petits CSV
# ---------------------------------------------------------------------------

def test_main_builds_the_anomalies_file(tmp_path, monkeypatch, output_dir):
    """Simule un vrai lancement : trois CSV contenant chacun une erreur
    connue, puis vérifie le contenu exact de anomalies.csv."""
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(cleaning, "RAW_DIR", raw)

    write_csv(raw, "customers.csv", make_df(
        VALID_CUSTOMER,
        {"customer_id": "C001"},
        {"customer_id": "C002", "email": "oups"},
    ))
    write_csv(raw, "subscriptions.csv", make_df(
        VALID_SUBSCRIPTION,
        {"subscription_id": "S001", "customer_id": "C001"},
        {"subscription_id": "S002", "customer_id": "C999"},
    ))
    write_csv(raw, "payments.csv", make_df(
        VALID_PAYMENT,
        {"payment_id": "P001", "subscription_id": "S001"},
        {"payment_id": "P002", "subscription_id": "S001", "amount": "-5"},
    ))

    cleaning.main()

    saved = pd.read_csv(output_dir / "anomalies.csv")
    result = set(zip(saved["file_name"], saved["row_number"], saved["column_name"]))
    assert result == {
        ("customers.csv", 3, "email"),
        ("subscriptions.csv", 3, "customer_id"),
        ("payments.csv", 3, "amount"),
    }
