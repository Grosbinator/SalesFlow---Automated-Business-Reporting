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

    # Repérage des abonnements associés à un client inconnu.
    unknown_customers = subscriptions.loc[
        ~subscriptions["customer_id"].isin(
            customers["customer_id"]
        )
    ]
    print("Abonnements avec un customer_id inconnu :")
    print(unknown_customers)

    # Repérage des paiements associés à un abonnement inconnu.
    unknown_subscriptions = payments.loc[
        ~payments["subscription_id"].isin(
            subscriptions["subscription_id"]
        )
    ]
    print("Paiements avec un subscription_id inconnu :")
    print(unknown_subscriptions)

    # Repérage des paiements en double.
    duplicates = payments[
        payments["payment_id"].duplicated(keep=False)
    ]
    print(duplicates)

    # Repérage des dates de paiement invalides.
    payments["payment_date"] = pd.to_datetime(
        payments["payment_date"],
        errors="coerce",
    )
    invalid_dates = payments[
        payments["payment_date"].isna()
    ]
    print(invalid_dates)

    # Repérage des montants manquants ou négatifs.
    payments["amount"] = pd.to_numeric(
        payments["amount"],
        errors="coerce",
    )

    missing_amounts = payments[
        payments["amount"].isna()
    ]
    negative_amounts = payments[
        payments["amount"] < 0
    ]
    print("Montants manquants ou invalides :")
    print(missing_amounts)
    print("Montants négatifs :")
    print(negative_amounts)


if __name__ == "__main__":
    main()