import pandas as pd


def preprocess_ports(df: pd.DataFrame):

    df = df.copy()

    df.columns = [c.strip() for c in df.columns]

    required_columns = [
        "UNLocode",
        "name",
        "Latitude",
        "Longitude",
        "CostPerFULL"
    ]

    df = df.dropna(subset=required_columns)

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df["CostPerFULL"] = pd.to_numeric(df["CostPerFULL"], errors="coerce")

    df = df.dropna()

    df = df.reset_index(drop=True)

    return df


def preprocess_demands(df: pd.DataFrame):

    df = df.copy()

    df.columns = [c.strip() for c in df.columns]

    required = [
        "Origin",
        "Destination",
        "FFEPerWeek",
        "Revenue_1"
    ]

    df = df.dropna(subset=required)

    df["FFEPerWeek"] = pd.to_numeric(
        df["FFEPerWeek"],
        errors="coerce"
    )

    df["Revenue_1"] = pd.to_numeric(
        df["Revenue_1"],
        errors="coerce"
    )

    df = df.dropna()

    df = df.reset_index(drop=True)

    return df