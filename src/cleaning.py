import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")

REQUIRED_COLUMNS = {
    "customers.csv": [
        "customer_id",
        "company_name",
        "email",
        "signup_date",
        "country",
    ],
    "subscriptions.csv": [
        "subscription_id",
        "customer_id",
        "plan",
        "monthly_price",
        "start_date",
        "end_date",
        "status",
    ],
    "payments.csv": [
        "payment_id",
        "subscription_id",
        "payment_date",
        "amount",
        "status",
        "payment_method",
    ],
}


def load_csv(filename):
    """Charge un CSV et vérifie ses colonnes obligatoires."""
    path = RAW_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    df = pd.read_csv(path)

    missing_columns = (
        set(REQUIRED_COLUMNS[filename]) - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{filename} : colonnes manquantes : "
            f"{sorted(missing_columns)}"
        )

    return df


def main():
    customers = load_csv("customers.csv")
    subscriptions = load_csv("subscriptions.csv")
    payments = load_csv("payments.csv")

    print("Les trois fichiers ont été chargés.")
    print("Customers :", customers.shape)
    print("Subscriptions :", subscriptions.shape)
    print("Payments :", payments.shape)


if __name__ == "__main__":
    main()