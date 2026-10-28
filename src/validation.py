"""Validation interactive des anomalies, puis écriture de data/processed/.

La console affiche les anomalies une par une (mêmes contrôles que
cleaning.py) avec la ligne complète du CSV, et propose pour chacune :
- modifier la valeur qui pose problème ;
- supprimer la ligne ;
- garder la ligne telle quelle (seulement si l'anomalie n'empêche pas le
  chargement en base, ex. montant négatif = remboursement) ;
- quitter.

Les contrôles sont relancés après chaque décision : une anomalie réglée
indirectement (ex. doublon dont l'autre ligne a été supprimée) disparaît,
et une nouvelle anomalie créée par une modification est proposée à son tour.

Les fichiers de data/raw/ ne sont jamais modifiés. À la fin, après
confirmation, les données corrigées sont écrites dans data/processed/ et
chaque décision est ajoutée au journal anomalies/corrections.csv. Ce journal
est réappliqué à chaque lancement (console ou main.py) : une correction
n'est faite qu'une fois.

Usage : python src/validation.py   (main.py utilise auto_validate())
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

import cleaning

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
CORRECTIONS_FILE = ROOT_DIR / "anomalies" / "corrections.csv"

# Fichier brut -> fichier nettoyé, dans l'ordre des contrôles.
PROCESSED_FILES = {
    "customers.csv": "customers_clean.csv",
    "subscriptions.csv": "subscriptions_clean.csv",
    "payments.csv": "payments_clean.csv",
}

CORRECTION_COLUMNS = [
    "date",
    "file_name",
    "row_number",
    "column_name",
    "error_message",
    "action",
    "old_value",
    "new_value",
]

# Anomalies qu'on peut accepter telles quelles : elles n'empêchent pas le
# chargement en base. Les autres (valeur manquante, doublon, date ou nombre
# illisible, référence inconnue) feraient échouer database.py.
KEEPABLE_PREFIXES = (
    "Montant négatif",
    "Prix négatif",
    "Email invalide",
    "Date de fin antérieure",
)

SEPARATOR = "-" * 64


# ---------------------------------------------------------------------------
# Données et contrôles
# ---------------------------------------------------------------------------

def load_frames():
    """Charge les trois CSV bruts. L'index pandas d'origine est conservé
    jusqu'au bout : il donne toujours le bon numéro de ligne du CSV, même
    après des suppressions."""
    return {name: cleaning.load_csv(name) for name in PROCESSED_FILES}


def run_checks(frames):
    """Relance les contrôles de cleaning.py sur l'état actuel des données."""
    customers = frames["customers.csv"]
    subscriptions = frames["subscriptions.csv"]
    payments = frames["payments.csv"]
    return (
        cleaning.check_customers(customers)
        + cleaning.check_subscriptions(subscriptions, customers)
        + cleaning.check_payments(payments, subscriptions)
    )


def anomaly_key(anomaly):
    return (
        anomaly["file_name"],
        anomaly["row_number"],
        anomaly["column_name"],
        anomaly["error_message"],
    )


def row_index(anomaly):
    """Numéro de ligne du CSV -> index pandas (en-tête = ligne 1)."""
    return anomaly["row_number"] - 2


def can_keep(anomaly):
    return anomaly["error_message"].startswith(KEEPABLE_PREFIXES)


# ---------------------------------------------------------------------------
# Affichage et saisie
# ---------------------------------------------------------------------------

def describe(anomaly, frames, remaining):
    """Texte affiché pour une anomalie : où, quoi, et la ligne complète."""
    df = frames[anomaly["file_name"]]
    index = row_index(anomaly)
    lines = [
        SEPARATOR,
        f"Anomalie ({remaining} restante(s))",
        f"  Fichier : {anomaly['file_name']}   "
        f"Ligne : {anomaly['row_number']}   "
        f"Colonne : {anomaly['column_name']}",
        f"  Problème : {anomaly['error_message']}",
        "  Ligne complète :",
    ]
    width = max(len(column) for column in df.columns)
    for column in df.columns:
        value = df.at[index, column]
        marker = ">" if column == anomaly["column_name"] else " "
        lines.append(f"  {marker} {column:<{width}}  {value if value != '' else '(vide)'}")
    return "\n".join(lines)


def ask_choice(ask, question, choices):
    """Repose la question tant que la réponse n'est pas une des `choices`."""
    menu = "  ".join(f"[{letter}] {label}" for letter, label in choices.items())
    while True:
        answer = ask(f"{menu}\n{question} ").strip().lower()
        if answer in choices:
            return answer


def ask_yes_no(ask, question):
    return ask_choice(ask, question, {"o": "Oui", "n": "Non"}) == "o"


def ask_new_value(ask, column, old_value):
    """Demande la nouvelle valeur ; None si l'utilisateur annule."""
    value = ask(
        f"Nouvelle valeur pour {column} "
        f"(actuelle : {old_value or '(vide)'}, Entrée = annuler) : "
    ).strip()
    if value:
        return value
    if ask_yes_no(ask, "Vider la cellule ? (sinon : annuler)"):
        return ""
    return None


# ---------------------------------------------------------------------------
# Revue des anomalies
# ---------------------------------------------------------------------------

def log_entry(anomaly, action, old_value="", new_value=""):
    return {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **anomaly,
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
    }


class Session:
    """Données en cours de correction, anomalies gardées et journal.

    Partagée par la console (review) et la fenêtre (validation_gui.py) :
    les deux appliquent les décisions de la même façon. `frames` est
    modifié sur place.
    """

    def __init__(self, frames, kept=None):
        self.frames = frames
        self.kept = set() if kept is None else kept
        self.log = []

    def pending(self):
        """Anomalies restantes (contrôles relancés sur l'état actuel)."""
        return [a for a in run_checks(self.frames) if anomaly_key(a) not in self.kept]

    def value(self, anomaly):
        """Valeur actuelle de la cellule concernée par l'anomalie."""
        df = self.frames[anomaly["file_name"]]
        return df.at[row_index(anomaly), anomaly["column_name"]]

    def modify(self, anomaly, new_value):
        old_value = self.value(anomaly)
        df = self.frames[anomaly["file_name"]]
        df.at[row_index(anomaly), anomaly["column_name"]] = new_value
        self.log.append(log_entry(anomaly, "valeur modifiée", old_value, new_value))

    def delete(self, anomaly):
        name = anomaly["file_name"]
        self.frames[name] = self.frames[name].drop(row_index(anomaly))
        self.log.append(log_entry(anomaly, "ligne supprimée"))

    def keep(self, anomaly):
        self.kept.add(anomaly_key(anomaly))
        self.log.append(log_entry(anomaly, "gardée telle quelle"))


def review(frames, ask=input, show=print, kept=None):
    """Propose les anomalies une par une et applique les décisions.

    `frames` est modifié sur place. `kept` : anomalies déjà acceptées (ex.
    réappliquées depuis le journal). Renvoie (journal, anomalies gardées,
    True si toutes les anomalies ont été traitées, False si on a quitté).
    `ask` et `show` remplacent input/print dans les tests.
    """
    session = Session(frames, kept)

    while True:
        pending = session.pending()
        if not pending:
            return session.log, session.kept, True

        anomaly = pending[0]
        column = anomaly["column_name"]
        show(describe(anomaly, frames, len(pending)))

        choices = {"m": "Modifier la valeur", "s": "Supprimer la ligne"}
        if can_keep(anomaly):
            choices["g"] = "Garder tel quel"
        choices["q"] = "Quitter"
        action = ask_choice(ask, "Votre choix :", choices)

        if action == "q":
            return session.log, session.kept, False

        if action == "s":
            session.delete(anomaly)
            show("  -> Ligne supprimée.")

        elif action == "g":
            session.keep(anomaly)
            show("  -> Valeur gardée.")

        else:
            old_value = session.value(anomaly)
            new_value = ask_new_value(ask, column, old_value)
            if new_value is None:
                show("  -> Modification annulée.")
                continue
            session.modify(anomaly, new_value)
            show(f"  -> {column} : {old_value or '(vide)'} -> {new_value or '(vide)'}")


def load_journal():
    """Lit anomalies/corrections.csv (liste vide s'il n'existe pas encore)."""
    if not CORRECTIONS_FILE.exists():
        return []
    journal = pd.read_csv(
        CORRECTIONS_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )
    return journal.to_dict("records")


def replay(frames, journal):
    """Réapplique les décisions des sessions précédentes.

    Une décision n'est rejouée que si la même anomalie (fichier, ligne,
    colonne, message) est encore présente et, pour une modification, si la
    valeur d'origine n'a pas changé : un CSV brut réimporté et différent ne
    reçoit pas de corrections qui ne le concernent pas.
    Renvoie (anomalies gardées, nombre de décisions réappliquées).
    """
    kept = set()
    applied = 0
    for entry in journal:
        row_number = int(entry["row_number"])
        key = (
            entry["file_name"], row_number,
            entry["column_name"], entry["error_message"],
        )
        if key not in {anomaly_key(a) for a in run_checks(frames)}:
            continue

        name, column = entry["file_name"], entry["column_name"]
        index = row_number - 2
        action = entry["action"]
        if action == "ligne supprimée":
            frames[name] = frames[name].drop(index)
        elif action == "gardée telle quelle":
            kept.add(key)
        elif (
            action == "valeur modifiée"
            and frames[name].at[index, column] == entry["old_value"]
        ):
            frames[name].at[index, column] = entry["new_value"]
        else:
            continue
        applied += 1
    return kept, applied


def exclude_unresolved(frames, kept):
    """Écarte les lignes qui ont encore une anomalie non acceptée.

    Répété jusqu'à stabilité : écarter un client peut rendre invalides ses
    abonnements, qui sont alors écartés à leur tour. Renvoie le journal.
    """
    log = []
    while True:
        pending = [a for a in run_checks(frames) if anomaly_key(a) not in kept]
        if not pending:
            return log
        for anomaly in pending:
            name, index = anomaly["file_name"], row_index(anomaly)
            if index in frames[name].index:
                frames[name] = frames[name].drop(index)
            log.append(log_entry(anomaly, "ligne écartée (non traitée)"))


# ---------------------------------------------------------------------------
# Écriture des résultats
# ---------------------------------------------------------------------------

def to_processed(name, df):
    """Ajoute les colonnes attendues par database.py dans les fichiers nettoyés."""
    df = df.copy()
    if name != "customers.csv":
        df["calculation_eligible"] = "True"
    if name == "payments.csv":
        df["revenue_eligible"] = (df["status"] == "success").map(str)
    return df


def save(frames, log):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, processed_name in PROCESSED_FILES.items():
        to_processed(name, frames[name]).to_csv(
            PROCESSED_DIR / processed_name, index=False
        )

    # Journal cumulatif : on ajoute à la suite des sessions précédentes.
    CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    journal = pd.DataFrame(log, columns=CORRECTION_COLUMNS)
    is_new = not CORRECTIONS_FILE.exists()
    journal.to_csv(
        CORRECTIONS_FILE,
        mode="w" if is_new else "a",
        header=is_new,
        index=False,
        encoding="utf-8-sig" if is_new else "utf-8",
    )


def show_counts(frames, show):
    for name, df in frames.items():
        show(f"  {name} : {len(df)} ligne(s) conservée(s)")


def auto_validate(show=print):
    """Validation sans console (utilisée par main.py).

    Réapplique les décisions du journal, écarte les lignes encore en
    anomalie, puis enregistre data/processed/. Renvoie les données.
    """
    frames = load_frames()
    kept, applied = replay(frames, load_journal())
    excluded = exclude_unresolved(frames, kept)
    save(frames, [])

    show(f"{applied} décision(s) du journal réappliquée(s).")
    show(f"{len(excluded)} anomalie(s) non traitée(s) : lignes écartées "
         "(python src/validation.py pour les traiter une par une).")
    show_counts(frames, show)
    return frames


def main(ask=input, show=print):
    """Console de validation. Renvoie True si les données ont été enregistrées."""
    frames = load_frames()
    show("Validation des anomalies (data/raw/ n'est jamais modifié).")
    kept, applied = replay(frames, load_journal())
    if applied:
        show(f"{applied} décision(s) des sessions précédentes réappliquée(s).")

    try:
        log, kept, completed = review(frames, ask, show, kept)
    except (KeyboardInterrupt, EOFError):
        show("\nInterrompu : rien n'a été enregistré.")
        return False

    show(SEPARATOR)
    if completed:
        show("Toutes les anomalies ont été traitées.")
    else:
        excluded = exclude_unresolved(frames, kept)
        log += excluded
        show(f"{len(excluded)} anomalie(s) non traitée(s) : "
             "les lignes concernées seront écartées des données nettoyées.")

    show_counts(frames, show)

    if not log:
        show("Aucune modification.")
    if ask_yes_no(ask, f"Enregistrer dans {PROCESSED_DIR} ?"):
        save(frames, log)
        show(f"Données nettoyées enregistrées. Journal : {CORRECTIONS_FILE}")
        return True
    show("Rien n'a été enregistré.")
    return False


if __name__ == "__main__":
    main()
