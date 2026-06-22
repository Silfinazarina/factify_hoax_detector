import os
import re
import json
import time
import requests
import pandas as pd
from dotenv import load_dotenv
import re
from html import unescape
from datetime import datetime, timedelta

load_dotenv()


API_KEY = os.getenv("TURNBACKHOAX_API_KEY")

URL = "https://yudistira.turnbackhoax.id/api/antihoax/search"

LIMIT = 20
END_DATE = datetime.today()
# START_DATE = END_DATE - timedelta(days=365)

TARGET = {
    "Benar": 100,
    "Salah": 100
}

VALID_STATUS = {"benar", "salah", "Benar", "Salah"}
BATAS_TANGGAL = datetime.today() - timedelta(days=365*3)

def clean_html(text):
    if not text:
        return ""

    # Decode HTML entity
    text = unescape(text)

    # Hapus tag HTML
    text = re.sub(r"<[^>]+>", "", text)

    # Rapikan spasi
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_valid_news(item):

    title = clean_html(item.get("title", "")).lower()
    content = clean_html(item.get("content", "")).lower()

    text = f"{title} {content}"

    # ==========================
    # 1. Nomor telepon / WhatsApp
    # ==========================
    if re.search(r'(\+62|62|08)\d{7,15}', text):
        return False

    # ==========================
    # 2. Kata-kata iklan / broadcast
    # ==========================
    blacklist = [

        "whatsapp",
        "hubungi",
        "call center",
        "customer service",
        "cs",
        "admin",
        "promo",
        "diskon",
        "giveaway",
        "klik link",
        "klik disini",
        "hubungi kami",

    ]

    if any(word in text for word in blacklist):
        return False
    
    return True





os.makedirs("dataset/raw", exist_ok=True)
os.makedirs("dataset/csv", exist_ok=True)

# Hapus file lama
# ==========================

files = [
    "dataset/raw/benar.json",
    "dataset/raw/salah.json",
    "dataset/csv/dataset_benar.csv",
    "dataset/csv/dataset_salah.csv",
    "dataset/csv/dataset_pengujian.csv"
]

for file in files:
    if os.path.exists(file):
        os.remove(file)
        print(f"Menghapus file lama: {file}")

def download_status(status, target):

    print("=" * 60)
    print(f"DOWNLOAD STATUS : {status}")
    print("=" * 60)

    hasil = []
    id_terambil = set()

    offset = 0
    selesai = False

    while len(hasil) < target and not selesai:

        body = {
            "key": API_KEY,
            "method": "status",
            "value": status,
            "limit": LIMIT,
            "offset": offset
        }

        try:

            response = requests.post(
                URL,
                data=body,
                timeout=20
            )

            response.raise_for_status()

            data = response.json()

            print("=" * 40)
            print("OFFSET :", offset)

            for item in data:
                print(
                    item["status"],
                    item["tanggal"],
                    item["title"][:60]
                )

            print("=" * 40)

        except Exception as e:

            print("ERROR :", e)
            break

        if not data:
            break

        jumlah_sebelum = len(hasil)

        for item in data:

            status_item = item.get("status", "").strip().lower()

            if status_item not in VALID_STATUS:
                continue

            if status_item != status.lower():
                continue

            try:
                tanggal = datetime.strptime(
                    item["tanggal"],
                    "%Y-%m-%d"
                )
            except:
                continue

            # berhenti jika berita sudah lebih lama dari 1 tahun
            if tanggal < BATAS_TANGGAL:
                continue

            if item["id"] in id_terambil:
                continue

            if not item.get("title") or not item.get("content"):
                continue

            if not is_valid_news(item):
                continue

            id_terambil.add(item["id"])

            hasil.append({

                "id": item["id"],
                "status_groundtruth": item["status"],
                "title": clean_html(item["title"]),
                "content": clean_html(item["content"]),
                "tanggal": item["tanggal"]

            })

            if len(hasil) >= target:
                break

        print(
            f"Offset {offset:<4} | +{len(hasil)-jumlah_sebelum:<2} | Total : {len(hasil)}"
        )

        offset += LIMIT

        time.sleep(0.2)

    print()

    with open(
        f"dataset/raw/{status.lower()}.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            hasil,
            f,
            ensure_ascii=False,
            indent=4
        )

    df = pd.DataFrame(hasil)

    df.to_csv(

        f"dataset/csv/dataset_{status.lower()}.csv",

        index=False,

        encoding="utf-8-sig"

    )

    return df

#####################################################

semua = []

for status, jumlah in TARGET.items():

    df = download_status(status, jumlah)

    semua.append(df)

#####################################################

dataset = pd.concat(semua, ignore_index=True)

dataset.to_csv(

    "dataset/csv/dataset_pengujian.csv",

    index=False,

    encoding="utf-8-sig"

)

print("=" * 60)
print("SELESAI")
print("=" * 60)
print()

for status in TARGET:

    print(f"dataset/csv/dataset_{status.lower()}.csv")

print()

print("dataset/csv/dataset_pengujian.csv")