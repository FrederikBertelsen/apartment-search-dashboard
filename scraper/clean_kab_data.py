

import pandas as pd


def clean_kab_data(csv_path: str):
    print("\nCleaning KAB data...")
    df_kab = pd.read_csv(csv_path)

    # split rent_interval into rent_min and rent_max, remove dots and convert to numeric
    df_kab["rent_interval"] = df_kab["rent_interval"].str.replace(".", "").str.strip()
    df_kab[["rent_min", "rent_max"]] = df_kab["rent_interval"].str.split(" - ", expand=True)
    df_kab["rent_min"] = pd.to_numeric(df_kab["rent_min"], errors="coerce")
    df_kab["rent_max"] = pd.to_numeric(df_kab["rent_max"], errors="coerce")

    # split area_interval into area_min and area_max, convert to numeric
    df_kab["area_interval"] = df_kab["area_interval"].str.replace(",", ".").str.strip()
    df_kab[["area_min", "area_max"]] = df_kab["area_interval"].str.split(" - ", expand=True)
    df_kab["area_min"] = pd.to_numeric(df_kab["area_min"], errors="coerce")
    df_kab["area_max"] = pd.to_numeric(df_kab["area_max"], errors="coerce")

    # split addresses into array
    df_kab["addresses"] = df_kab["addresses"].str.split("|")

    # remove unwanted column
    df_kab = df_kab.drop(columns=["type_and_address", "rent_interval", "area_interval"])

    clean_csv_path = csv_path.replace(".csv", "_clean.csv")
    print(f"Finished cleaning KAB data, saving to '{clean_csv_path}'")
    df_kab.to_csv(clean_csv_path, index=False)

if __name__ == "__main__":
    clean_kab_data("data/kab_tenancies.csv")