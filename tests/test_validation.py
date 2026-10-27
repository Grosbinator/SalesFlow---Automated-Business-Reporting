"""Tests de src/validation.py.

La console est pilotée par une liste de réponses simulées (`answers`) à la
place du clavier, et les données sont de petits DataFrames en mémoire :
data/ et anomalies/ ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import validation  # noqa: E402


# ---------------------------------------------------------------------------
# Jeux de données : des CSV bruts valides, chaque test y ajoute ses erreurs.
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
    overrides = overrides or ({},)
    return pd.DataFrame([{**base, **row} for row in overrides], dtype=str)


def make_frames(customers=None, subscriptions=None, payments=None):
    return {
        "customers.csv": customers if customers is not None else make_df(VALID_CUSTOMER),
        "subscriptions.csv": (
            subscriptions if subscriptions is not None else make_df(VALID_SUBSCRIPTION)
        ),
        "payments.csv": payments if payments is not None else make_df(VALID_PAYMENT),
    }


def answers(*replies):
    """Simule le clavier : renvoie les réponses dans l'ordre."""
    replies = iter(replies)
    return lambda prompt: next(replies)


class Console:
    """Récupère ce que la console affiche."""

    def __init__(self):
        self.lines = []

    def __call__(self, text=""):
        self.lines.append(text)

    @property
    def text(self):
        return "\n".join(self.lines)


# ---------------------------------------------------------------------------
# 1. Affichage
# ---------------------------------------------------------------------------

def test_describe_shows_file_line_column_and_full_row():
    frames = make_frames(payments=make_df(VALID_PAYMENT, {"amount": ""}))
    anomaly = validation.run_checks(frames)[0]
    text = validation.describe(anomaly, frames, remaining=1)
    assert "payments.csv" in text
    assert "Ligne : 2" in text
    assert "Valeur manquante" in text
    assert "> amount" in text and "(vide)" in text
    assert "payment_method" in text  # la ligne complète est affichée


def test_ask_choice_repeats_until_answer_is_valid():
    ask = answers("x", "", "S")
    assert validation.ask_choice(ask, "?", {"s": "Supprimer"}) == "s"


# ---------------------------------------------------------------------------
# 2. Décisions
# ---------------------------------------------------------------------------

def test_modify_value_fixes_the_anomaly():
    frames = make_frames(payments=make_df(VALID_PAYMENT, {"amount": ""}))
    log, kept, completed = validation.review(frames, answers("m", "49.0"), Console())
    assert completed
    assert frames["payments.csv"].at[0, "amount"] == "49.0"
    assert log[0]["action"] == "valeur modifiée"
    assert (log[0]["old_value"], log[0]["new_value"]) == ("", "49.0")


def test_invalid_new_value_is_proposed_again():
    """Une valeur corrigée mais toujours fausse redevient une anomalie."""
    frames = make_frames(payments=make_df(VALID_PAYMENT, {"payment_date": "2026-13-40"}))
    validation.review(frames, answers("m", "2026-14-01", "m", "2026-10-24"), Console())
    assert frames["payments.csv"].at[0, "payment_date"] == "2026-10-24"


def test_delete_row_removes_it_and_keeps_line_numbers():
    """Après une suppression, les lignes suivantes gardent leur numéro du CSV."""
    payments = make_df(
        VALID_PAYMENT,
        {"payment_id": "P001", "subscription_id": "S999"},  # ligne 2
        {"payment_id": "P002", "amount": "abc"},             # ligne 3
    )
    frames = make_frames(payments=payments)
    console = Console()
    validation.review(frames, answers("s", "s"), console)
    assert frames["payments.csv"].empty
    assert "Ligne : 3" in console.text


def test_deleting_one_duplicate_resolves_the_other():
    """Doublon P001 : supprimer une ligne règle aussi l'anomalie de l'autre."""
    payments = make_df(
        VALID_PAYMENT,
        {"payment_id": "P001", "payment_date": "2026-13-40"},
        {"payment_id": "P001"},
    )
    frames = make_frames(payments=payments)
    log, _, completed = validation.review(frames, answers("s"), Console())
    assert completed
    assert len(log) == 1
    assert list(frames["payments.csv"]["payment_date"]) == ["2026-01-12"]


def test_keep_is_offered_only_for_harmless_anomalies():
    """Un montant négatif peut être gardé (remboursement) ; une référence
    inconnue non, car database.py refuserait la ligne."""
    negative = make_frames(payments=make_df(VALID_PAYMENT, {"amount": "-29.0"}))
    log, kept, completed = validation.review(negative, answers("g"), Console())
    assert completed and len(kept) == 1
    assert negative["payments.csv"].at[0, "amount"] == "-29.0"

    unknown = make_frames(payments=make_df(VALID_PAYMENT, {"subscription_id": "S999"}))
    console = Console()
    validation.review(unknown, answers("g", "q"), console)  # « g » refusé
    assert "Garder" not in console.text


def test_quit_stops_the_review():
    frames = make_frames(payments=make_df(VALID_PAYMENT, {"amount": ""}))
    log, _, completed = validation.review(frames, answers("q"), Console())
    assert not completed and log == []


def test_cancel_modification_shows_the_anomaly_again():
    frames = make_frames(payments=make_df(VALID_PAYMENT, {"amount": ""}))
    # m, Entrée (pas de valeur), n (ne pas vider) -> annulé ; puis q.
    validation.review(frames, answers("m", "", "n", "q"), Console())
    assert frames["payments.csv"].at[0, "amount"] == ""


# ---------------------------------------------------------------------------
# 3. Lignes non traitées et enregistrement
# ---------------------------------------------------------------------------

def test_exclude_unresolved_cascades_to_dependent_rows():
    """Écarter un client invalide écarte aussi ses abonnements et paiements."""
    frames = make_frames(customers=make_df(VALID_CUSTOMER, {"company_name": ""}))
    log = validation.exclude_unresolved(frames, kept=set())
    assert all(df.empty for df in frames.values())
    assert {entry["file_name"] for entry in log} == {
        "customers.csv", "subscriptions.csv", "payments.csv",
    }


@pytest.fixture
def output(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(validation, "CORRECTIONS_FILE", tmp_path / "corrections.csv")
    return tmp_path


def test_main_saves_processed_files_and_journal(output, monkeypatch):
    payments = make_df(
        VALID_PAYMENT,
        {"payment_id": "P001"},
        {"payment_id": "P002", "amount": "", "status": "failed"},
    )
    monkeypatch.setattr(validation, "load_frames", lambda: make_frames(payments=payments))

    validation.main(answers("m", "29.0", "o"), Console())

    saved = pd.read_csv(output / "processed" / "payments_clean.csv", dtype=str)
    assert list(saved["amount"]) == ["29.0", "29.0"]
    # Colonnes attendues par database.py :
    assert list(saved["revenue_eligible"]) == ["True", "False"]
    assert list(saved["calculation_eligible"]) == ["True", "True"]
    customers = pd.read_csv(output / "processed" / "customers_clean.csv")
    assert "calculation_eligible" not in customers.columns

    journal = pd.read_csv(output / "corrections.csv", encoding="utf-8-sig")
    assert list(journal["action"]) == ["valeur modifiée"]
    assert journal.loc[0, "row_number"] == 3


def test_main_writes_nothing_if_not_confirmed(output, monkeypatch):
    monkeypatch.setattr(validation, "load_frames", make_frames)
    validation.main(answers("n"), Console())
    assert not (output / "processed").exists()
    assert not (output / "corrections.csv").exists()


def test_journal_is_replayed_and_appended_between_sessions(output, monkeypatch):
    """2e session : la correction de la 1re est réappliquée sans rien
    demander, seule la nouvelle anomalie est proposée, et le journal s'allonge."""
    payments = make_df(VALID_PAYMENT, {"amount": ""})
    monkeypatch.setattr(
        validation, "load_frames", lambda: make_frames(payments=payments.copy())
    )
    validation.main(answers("m", "1", "o"), Console())

    payments.at[0, "payment_method"] = ""  # nouvelle anomalie dans le CSV brut
    console = Console()
    validation.main(answers("m", "card", "o"), console)

    assert "1 décision(s) des sessions précédentes réappliquée(s)" in console.text
    journal = pd.read_csv(output / "corrections.csv", dtype=str, encoding="utf-8-sig")
    assert list(journal["new_value"]) == ["1", "card"]
    saved = pd.read_csv(output / "processed" / "payments_clean.csv", dtype=str)
    assert (saved.at[0, "amount"], saved.at[0, "payment_method"]) == ("1", "card")
