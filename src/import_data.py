"""Importe les CSV sources vers data/raw avec pandas.

Dossier source, par ordre de priorité :
1. l'argument `source_dir` (option --source) ;
2. la variable d'environnement SALESFLOW_SOURCE_DIR ;
3. data/sample/ : données d'exemple fournies avec le projet.

Usage : python src/import_data.py [--source DOSSIER]
"""

import argparse
import os
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
FILES = ("customers.csv", "subscriptions.csv", "payments.csv")
SAMPLE_DIR = ROOT_DIR / "data" / "sample"
RAW_DIR = ROOT_DIR / "data" / "raw"
SOURCE_ENV_VAR = "SALESFLOW_SOURCE_DIR"


def resolve_source_dir(source_dir=None):
    """Dossier source : argument, sinon variable d'environnement, sinon data/sample/."""
    if source_dir:
        return Path(source_dir).expanduser()
    if os.environ.get(SOURCE_ENV_VAR):
        return Path(os.environ[SOURCE_ENV_VAR]).expanduser()
    return SAMPLE_DIR


def import_csv_files(source_dir=None) -> None:
    source = resolve_source_dir(source_dir)

    sources = {name: source / name for name in FILES}
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Fichier(s) CSV introuvable(s) dans {source} :\n"
            + "\n".join(missing)
        )

    # Tout lire avant d'écrire pour éviter un import partiel si un CSV est invalide.
    dataframes = {
        name: pd.read_csv(path, dtype=str, keep_default_na=False)
        for name, path in sources.items()
    }

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, dataframe in dataframes.items():
        target = RAW_DIR / name
        dataframe.to_csv(target, index=False)
        print(f"Importé : {sources[name]} -> {target}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Copie customers.csv, subscriptions.csv et payments.csv "
                    "vers data/raw/."
    )
    parser.add_argument(
        "--source",
        help=f"dossier des CSV (défaut : ${SOURCE_ENV_VAR}, sinon data/sample/)",
    )
    args = parser.parse_args(argv)
    import_csv_files(args.source)


if __name__ == "__main__":
    main()
