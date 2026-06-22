import os
import pandas as pd

from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)

# =====================================================
# PATH
# =====================================================

INPUT = "hasil/hasil_pengujian.csv"

OUTPUT_CM = "hasil/confusion_matrix.csv"

OUTPUT_TXT = "hasil/evaluasi.txt"

os.makedirs("hasil", exist_ok=True)

# =====================================================
# LOAD DATA
# =====================================================

df = pd.read_csv(INPUT)

print("=" * 60)
print("EVALUASI HASIL PENGUJIAN")
print("=" * 60)

print("Jumlah Data :", len(df))

# =====================================================
# MAPPING GROUND TRUTH
# =====================================================

mapping = {
    "Benar": "Valid",
    "Salah": "Hoax"
}

df["ground_truth"] = df["ground_truth"].map(mapping)

# =====================================================
# HITUNG TIDAK DIKETAHUI
# =====================================================

unknown = (df["prediction"] == "Tidak Diketahui").sum()

# =====================================================
# FILTER HANYA VALID & HOAX
# =====================================================

df_eval = df[
    df["prediction"].isin(["Valid", "Hoax"])
].copy()

print("Data Dievaluasi :", len(df_eval))
print("Tidak Diketahui :", unknown)

# =====================================================
# LABEL
# =====================================================

y_true = df_eval["ground_truth"]

y_pred = df_eval["prediction"]

# =====================================================
# CONFUSION MATRIX
# =====================================================

cm = confusion_matrix(
    y_true,
    y_pred,
    labels=["Valid", "Hoax"]
)

cm_df = pd.DataFrame(
    cm,
    index=["GT Valid", "GT Hoax"],
    columns=["Pred Valid", "Pred Hoax"]
)

cm_df.to_csv(
    OUTPUT_CM,
    encoding="utf-8-sig"
)

# =====================================================
# METRIK
# =====================================================

accuracy = accuracy_score(
    y_true,
    y_pred
)

precision = precision_score(
    y_true,
    y_pred,
    pos_label="Hoax"
)

recall = recall_score(
    y_true,
    y_pred,
    pos_label="Hoax"
)

f1 = f1_score(
    y_true,
    y_pred,
    pos_label="Hoax"
)

# coverage = len(df_eval) / len(df) * 100

# =====================================================
# OUTPUT
# =====================================================

summary = f"""
============================================================
HASIL EVALUASI
============================================================

Jumlah Dataset        : {len(df)}

Data Dievaluasi       : {len(df_eval)}

Tidak Diketahui       : {unknown}

Accuracy              : {accuracy:.4f}
Precision             : {precision:.4f}
Recall                : {recall:.4f}
F1-Score              : {f1:.4f}

============================================================
CONFUSION MATRIX
============================================================

{cm_df}
"""

print(summary)

with open(
    OUTPUT_TXT,
    "w",
    encoding="utf-8"
) as f:

    f.write(summary)

print("Confusion Matrix :", OUTPUT_CM)
print("Ringkasan        :", OUTPUT_TXT)