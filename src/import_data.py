"""Importe les CSV du dossier Téléchargements vers data/raw avec pandas."""

from pathlib import Path

import pandas as pd


FILES = ("customers.csv", "subscriptions.csv", "payments.csv")
DOWNLOADS_DIR = Path(r"C:\Users\robin\Downloads")


def import_csv_files() -> None:
    destination = Path(__file__).resolve().parent.parent / "data" / "raw"

    sources = {name: DOWNLOADS_DIR / name for name in FILES}
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Fichier(s) CSV introuvable(s) dans Téléchargements :\n"
            + "\n".join(missing)
        )

    # Tout lire avant d'écrire pour éviter un import partiel si un CSV est invalide.
    dataframes = {
        name: pd.read_csv(path, dtype=str, keep_default_na=False)
        for name, path in sources.items()
    }

    destination.mkdir(parents=True, exist_ok=True)
    for name, dataframe in dataframes.items():
        target = destination / name
        dataframe.to_csv(target, index=False)
        print(f"Importé : {sources[name]} -> {target}")
