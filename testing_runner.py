import time
import pandas as pd
import os
import statistics

from main import verify_news

# ===========================================
# PENGATURAN
# ===========================================

DATASET_PATH = "dataset/csv/dataset_pengujian.csv"
OUTPUT_PATH = "hasil/hasil_pengujian.csv"

# Jika ingin membatasi jumlah data uji
MAX_TEST = 50      #none


# ===========================================

os.makedirs("hasil", exist_ok=True)

dataset = pd.read_csv(DATASET_PATH)

# ===========================================
# Resume Pengujian
# ===========================================

if os.path.exists(OUTPUT_PATH):

    df_hasil = pd.read_csv(OUTPUT_PATH)

    hasil = df_hasil.to_dict("records")

    selesai = set(df_hasil["id"])

    # Ambil latency yang sudah ada
    latencies = (
        df_hasil["latency"]
        .dropna()
        .astype(float)
        .tolist()
    )

    print(f"Melanjutkan pengujian ({len(selesai)} data sudah selesai).")

else:

    hasil = []

    selesai = set()

    latencies = []


if MAX_TEST:

    per_kelas = MAX_TEST // 2

    benar = dataset[
        dataset["status_groundtruth"] == "Benar"
    ].head(per_kelas)

    salah = dataset[
        dataset["status_groundtruth"] == "Salah"
    ].head(per_kelas)

    dataset = pd.concat([benar, salah], ignore_index=True)

print("=" * 60)
print("PENGUJIAN DATASET")
print("=" * 60)

total = len(dataset)

for i, row in dataset.iterrows():

    if row["id"] in selesai:
        continue

    print(f"\n[{i+1}/{total}]")

    berita = f"{row['content']}"

    ground_truth = row["status_groundtruth"]

    print("Ground Truth :", ground_truth)
    print("Judul        :", row["title"])

    start = time.perf_counter()

    try:

        result = verify_news(berita)

        end = time.perf_counter()

        latency = end - start

        latencies.append(latency)

        prediction = result["status"]

        layer = result["layer"]

        reason = result["reason"]

        keyword = result.get("search_keyword", "")

        claim = result.get("claim", "")

        print("Prediksi     :", prediction)
        print("Layer        :", layer)
        print(f"Latency      : {latency:.2f} detik")

    except Exception as e:

        latency = None

        prediction = "ERROR"

        layer = "-"

        keyword = ""

        claim = ""

        reason = str(e)

        print("ERROR :", e)

    hasil.append({

        "id": row["id"],

        "title": row["title"],

        "ground_truth": ground_truth,

        "prediction": prediction,

        "layer": layer,

        "latency": latency,

        "claim": claim,

        "search_keyword": keyword,

        "reason": reason

    })

    # Simpan progres
    pd.DataFrame(hasil).to_csv(

        OUTPUT_PATH,

        index=False,

        encoding="utf-8-sig"

    )

    
    print(f"Progress disimpan ({len(hasil)} data).")

df = pd.DataFrame(hasil)

# df.to_csv(

#     OUTPUT_PATH,

#     index=False,

#     encoding="utf-8-sig"

# )

print("\n")
print("=" * 60)
print("PENGUJIAN SELESAI")
print("=" * 60)
print("Total Data :", len(df))
print("Output :", OUTPUT_PATH)

valid = (df["prediction"] == "Valid").sum()
hoax = (df["prediction"] == "Hoax").sum()
unknown = (df["prediction"] == "Tidak Diketahui").sum()

layer_turnbackhoax = (df["layer"] == "turnbackhoax").sum()
layer_google_news = (df["layer"] == "google_news").sum()

summary = f"""
============================================================
STATISTIK PENGUJIAN
============================================================

Jumlah Data            : {len(df)}

Prediksi Valid         : {valid}
Prediksi Hoax          : {hoax}
Tidak Diketahui        : {unknown}

Layer TurnBackHoax     : {layer_turnbackhoax}
Layer Google News      : {layer_google_news}

Minimum Latency        : {min(latencies):.3f} detik
Maksimum Latency       : {max(latencies):.3f} detik
Rata-rata Latency      : {statistics.mean(latencies):.3f} detik
Median Latency         : {statistics.median(latencies):.3f} detik
"""

if len(latencies) > 1:
    summary += (
        f"Standar Deviasi      : "
        f"{statistics.stdev(latencies):.3f} detik\n"
    )

if latencies:

    summary += f"""
Minimum Latency : {min(latencies):.3f}
Maksimum Latency : {max(latencies):.3f}
Rata-rata Latency : {statistics.mean(latencies):.3f}
Median Latency : {statistics.median(latencies):.3f}
"""

print(summary)

with open(
    "hasil/statistik_pengujian.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write(summary)