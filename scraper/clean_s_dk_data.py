

import pandas as pd


def clean_s_dk_data(csv_path: str):
    print("\nCleaning s.dk data...")
    df_s_dk = pd.read_csv(csv_path)

    df_s_dk[["place_in_queue_min", "place_in_queue_max"]] = df_s_dk["place_in_queue"].str.split("-", expand=True)

    df_s_dk["place_in_queue_min"] = pd.to_numeric(df_s_dk["place_in_queue_min"], errors="coerce")
    df_s_dk["place_in_queue_max"] = pd.to_numeric(df_s_dk["place_in_queue_max"], errors="coerce")

    clean_csv_path = csv_path.replace(".csv", "_clean.csv")
    print(f"Finished cleaning s.dk data, saving to '{clean_csv_path}'")
    df_s_dk.to_csv(clean_csv_path, index=False)

if __name__ == "__main__":
    clean_s_dk_data("data/s_dk_tenancies.csv")