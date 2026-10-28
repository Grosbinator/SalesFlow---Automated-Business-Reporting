"""Tests de src/import_data.py.

Les CSV sources et data/raw/ sont redirigés vers un dossier temporaire :
les vrais fichiers ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import import_data  # noqa: E402


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    """Redirige data/raw/ et neutralise la variable d'environnement."""
    raw = tmp_path / "raw"
    monkeypatch.setattr(import_data, "RAW_DIR", raw)
    monkeypatch.delenv(import_data.SOURCE_ENV_VAR, raising=False)
    return raw


def make_source(folder):
    """Crée un dossier source contenant les trois CSV."""
    folder.mkdir(parents=True)
    for name in import_data.FILES:
        (folder / name).write_text("id,value\n1,\n", encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# 1. Choix du dossier source
# ---------------------------------------------------------------------------

def test_default_source_is_the_sample_data(raw_dir):
    assert import_data.resolve_source_dir() == import_data.SAMPLE_DIR


def test_environment_variable_overrides_the_default(raw_dir, monkeypatch, tmp_path):
    monkeypatch.setenv(import_data.SOURCE_ENV_VAR, str(tmp_path / "exports"))
    assert import_data.resolve_source_dir() == tmp_path / "exports"


def test_argument_overrides_the_environment_variable(raw_dir, monkeypatch, tmp_path):
    monkeypatch.setenv(import_data.SOURCE_ENV_VAR, str(tmp_path / "exports"))
    assert import_data.resolve_source_dir(tmp_path / "other") == tmp_path / "other"


def test_sample_data_is_shipped_with_the_project():
    """Les données d'exemple doivent exister pour lancer le projet après un clone."""
    for name in import_data.FILES:
        assert (import_data.SAMPLE_DIR / name).is_file()


# ---------------------------------------------------------------------------
# 2. Import
# ---------------------------------------------------------------------------

def test_import_copies_the_three_files(raw_dir, tmp_path):
    source = make_source(tmp_path / "exports")
    import_data.import_csv_files(source)
    for name in import_data.FILES:
        copied = pd.read_csv(raw_dir / name, dtype=str, keep_default_na=False)
        assert copied.to_dict("list") == {"id": ["1"], "value": [""]}


def test_missing_file_names_the_source_folder_and_writes_nothing(raw_dir, tmp_path):
    source = make_source(tmp_path / "exports")
    (source / "payments.csv").unlink()
    with pytest.raises(FileNotFoundError, match="payments.csv"):
        import_data.import_csv_files(source)
    assert not raw_dir.exists()  # aucun import partiel


def test_command_line_source_option(raw_dir, tmp_path):
    source = make_source(tmp_path / "exports")
    import_data.main(["--source", str(source)])
    assert (raw_dir / "customers.csv").is_file()
