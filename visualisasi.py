import os
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score
)

# ======================================================
# PATH
# ======================================================

INPUT = "hasil/hasil_pengujian.csv"

OUTPUT_CM = "hasil/confusion_matrix.png"
OUTPUT_METRIC = "hasil/metrik.png"

os.makedirs("hasil", exist_ok=True)

# ======================================================
# LOAD DATA
# ======================================================

df = pd.read_csv(INPUT)

mapping = {
    "Benar": "Valid",
    "Salah": "Hoax"
}

df["ground_truth"] = df["ground_truth"].map(mapping)

# ======================================================
# FILTER
# ======================================================

df_eval = df[
    df["prediction"].isin(["Valid", "Hoax"])
].copy()

y_true = df_eval["ground_truth"]

y_pred = df_eval["prediction"]

# ======================================================
# METRIK
# ======================================================

accuracy = accuracy_score(y_true, y_pred)

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

# ======================================================
# CONFUSION MATRIX
# ======================================================

cm = confusion_matrix(
    y_true,
    y_pred,
    labels=["Valid", "Hoax"]
)

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=["Valid", "Hoax"]
)

plt.figure(figsize=(6,6))

disp.plot()

plt.title("Confusion Matrix")

plt.savefig(
    OUTPUT_CM,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

# ======================================================
# BAR CHART METRIK
# ======================================================

metrics = [
    accuracy,
    precision,
    recall,
    f1
]

labels = [
    "Accuracy",
    "Precision",
    "Recall",
    "F1-Score"
]

plt.figure(figsize=(7,5))

bars = plt.bar(
    labels,
    metrics
)

plt.ylim(0,1)

for bar, value in zip(bars, metrics):

    plt.text(
        bar.get_x() + bar.get_width()/2,
        value + 0.02,
        f"{value:.2f}",
        ha="center"
    )

plt.ylabel("Score")

plt.title("Evaluation Metrics")

plt.savefig(
    OUTPUT_METRIC,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print("="*60)
print("VISUALISASI BERHASIL")
print("="*60)
print()

print("Confusion Matrix :", OUTPUT_CM)
print("Grafik Metrik    :", OUTPUT_METRIC)