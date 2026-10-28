"""Tests de src/validation_gui.py.

Une vraie fenêtre tkinter est créée mais masquée ; les clics sont simulés
en appelant les méthodes des boutons, et les boîtes de confirmation
répondent « Oui ». Les tests sont ignorés si aucun affichage n'existe.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
import tkinter as tk
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import validation  # noqa: E402
import validation_gui  # noqa: E402
from test_validation import (  # noqa: E402, F401
    VALID_PAYMENT,
    journal_entry,
    make_df,
    make_frames,
    output,
    write_journal,
)

# Ligne 2 : montant manquant ; ligne 3 : montant négatif ; ligne 4 :
# abonnement inconnu.
PAYMENTS = [
    {"payment_id": "P001", "amount": ""},
    {"payment_id": "P002", "amount": "-5"},
    {"payment_id": "P003", "subscription_id": "S999"},
]


@pytest.fixture(scope="session")
def tk_root():
    """Une seule fenêtre principale Tk pour toute la session de tests :
    sous Windows, recréer Tk() plusieurs fois échoue par intermittence."""
    try:
        tk_root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"aucun affichage disponible pour tkinter : {error}")
    tk_root.withdraw()
    yield tk_root
    tk_root.destroy()


@pytest.fixture
def root(tk_root):
    """Fenêtre masquée propre à chaque test."""
    root = tk.Toplevel(tk_root)
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass  # déjà fermée par la fenêtre


@pytest.fixture(autouse=True)
def always_yes(monkeypatch):
    monkeypatch.setattr(validation_gui.messagebox, "askyesno", lambda *a, **k: True)


@pytest.fixture
def window(root):
    session = validation.Session(make_frames(payments=make_df(VALID_PAYMENT, *PAYMENTS)))
    return validation_gui.ValidationWindow(root, session)


def amounts(window):
    return list(window.session.frames["payments.csv"]["amount"])


# ---------------------------------------------------------------------------
# 1. Affichage
# ---------------------------------------------------------------------------

def test_window_lists_anomalies_and_shows_the_first(window):
    assert window.listbox.size() == 3
    assert "ligne 2" in window.listbox.get(0)
    assert window.current["column_name"] == "amount"
    assert window.value_var.get() == ""
    # La colonne fautive est surlignée dans la ligne complète.
    faulty = [
        window.row_view.item(item, "values")[0]
        for item in window.row_view.get_children()
        if "fault" in window.row_view.item(item, "tags")
    ]
    assert faulty == ["amount"]


def test_selecting_another_anomaly_shows_it(window):
    window.listbox.selection_clear(0, "end")
    window.listbox.selection_set(2)
    window.on_select()
    assert window.current["column_name"] == "subscription_id"


def test_keep_is_only_enabled_for_harmless_anomalies(window):
    assert window.keep_button.instate(["disabled"])  # montant manquant
    window.show(window.pending[1])                    # montant négatif
    assert window.keep_button.instate(["!disabled"])
    window.show(window.pending[2])                    # abonnement inconnu
    assert window.keep_button.instate(["disabled"])


# ---------------------------------------------------------------------------
# 2. Décisions
# ---------------------------------------------------------------------------

def test_modify_fixes_the_anomaly(window):
    window.value_var.set("29.0")
    window.modify()
    assert amounts(window)[0] == "29.0"
    assert window.listbox.size() == 2


def test_wrong_value_keeps_the_anomaly_in_place(window):
    window.value_var.set("abc")
    window.modify()
    assert window.listbox.size() == 3
    assert "non numérique" in window.current["error_message"]


def test_keep_and_delete(window):
    window.show(window.pending[1])
    window.keep()
    window.show(window.pending[1])  # l'abonnement inconnu est passé 2e
    window.delete()
    assert window.listbox.size() == 1
    assert list(window.session.frames["payments.csv"]["payment_id"]) == ["P001", "P002"]


def test_everything_treated_disables_the_actions(window):
    window.value_var.set("29.0")
    window.modify()
    window.keep()
    window.delete()
    assert window.pending == []
    assert window.modify_button.instate(["disabled"])
    assert "traitées" in window.header.cget("text")


def test_finish_and_cancel_set_the_result(root, tk_root):
    session = validation.Session(make_frames())
    window = validation_gui.ValidationWindow(root, session)
    window.finish()
    assert window.result is True

    other = tk.Toplevel(tk_root)
    other.withdraw()
    window = validation_gui.ValidationWindow(other, session)
    window.cancel()
    assert window.result is False


# ---------------------------------------------------------------------------
# 3. gui_validate (appelé par main.py)
# ---------------------------------------------------------------------------

def test_gui_validate_without_anomaly_opens_no_window(output, monkeypatch):
    monkeypatch.setattr(validation, "load_frames", make_frames)
    monkeypatch.setattr(validation_gui.tk, "Tk", lambda: pytest.fail("fenêtre ouverte"))
    assert validation_gui.gui_validate(show=lambda text="": None) is True
    assert (output / "processed" / "payments_clean.csv").is_file()


def test_gui_validate_saves_the_decisions(output, monkeypatch, root):
    monkeypatch.setattr(
        validation, "load_frames",
        lambda: make_frames(payments=make_df(VALID_PAYMENT, *PAYMENTS)),
    )
    monkeypatch.setattr(validation_gui.tk, "Tk", lambda: root)
    monkeypatch.setattr(validation_gui, "bring_to_front", lambda root: None)

    def user_clicks():
        """Simule l'utilisateur : corrige le montant puis continue."""
        window = opened[0]
        window.value_var.set("29.0")
        window.modify()
        window.finish()

    opened = []
    real_window = validation_gui.ValidationWindow
    monkeypatch.setattr(
        validation_gui, "ValidationWindow",
        lambda root, session, demo=False: opened.append(real_window(root, session, demo)) or opened[0],
    )
    monkeypatch.setattr(root, "mainloop", user_clicks)

    assert validation_gui.gui_validate(show=lambda text="": None) is True

    saved = pd.read_csv(output / "processed" / "payments_clean.csv", dtype=str)
    # P001 corrigé ; P002 et P003, non traités, sont écartés.
    assert list(saved["payment_id"]) == ["P001"]
    assert list(saved["amount"]) == ["29.0"]
    journal = pd.read_csv(output / "corrections.csv", encoding="utf-8-sig")
    assert list(journal["action"])[0] == "valeur modifiée"


def test_gui_validate_cancelled_saves_nothing(output, monkeypatch, root):
    monkeypatch.setattr(
        validation, "load_frames",
        lambda: make_frames(payments=make_df(VALID_PAYMENT, *PAYMENTS)),
    )
    monkeypatch.setattr(validation_gui.tk, "Tk", lambda: root)
    monkeypatch.setattr(validation_gui, "bring_to_front", lambda root: None)
    monkeypatch.setattr(root, "mainloop", lambda: None)  # fenêtre fermée sans valider

    assert validation_gui.gui_validate(show=lambda text="": None) is False
    assert not (output / "processed").exists()


def test_demo_opens_the_window_even_if_the_journal_fixes_everything(
        output, monkeypatch, root):
    """Mode démo : le journal corrige déjà l'erreur, la fenêtre s'ouvre quand
    même (titre « mode démo ») et le journal n'est pas modifié."""
    monkeypatch.setattr(
        validation, "load_frames",
        lambda: make_frames(payments=make_df(VALID_PAYMENT, {"amount": ""})),
    )
    before = write_journal(output, journal_entry(
        2, "amount", "Valeur manquante", "valeur modifiée", "", "29.0"))
    monkeypatch.setattr(validation_gui.tk, "Tk", lambda: root)
    monkeypatch.setattr(validation_gui, "bring_to_front", lambda root: None)

    def user_clicks():
        window = opened[0]
        assert "mode démo" in root.title()
        window.value_var.set("49.0")
        window.modify()
        window.finish()

    opened = []
    real_window = validation_gui.ValidationWindow
    monkeypatch.setattr(
        validation_gui, "ValidationWindow",
        lambda root, session, demo: opened.append(real_window(root, session, demo)) or opened[0],
    )
    monkeypatch.setattr(root, "mainloop", user_clicks)

    assert validation_gui.gui_validate(show=lambda text="": None, use_journal=False)
    assert opened, "la fenêtre aurait dû s'ouvrir"
    saved = pd.read_csv(output / "processed" / "payments_clean.csv", dtype=str)
    assert list(saved["amount"]) == ["49.0"]
    assert (output / "corrections.csv").read_bytes() == before
