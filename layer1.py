import re
import requests
from urllib.parse import quote #encode link sumber
import os
from dotenv import load_dotenv
import ollama
import time

load_dotenv()

MODEL_NAME = "llama3.2:3b"
TURNBACKHOAX_API_KEY = os.getenv("TURNBACKHOAX_API_KEY")
BASE_URL = "https://yudistira.turnbackhoax.id/api/antihoax/search"


# llm response
def ask_llm(prompt: str):

    start = time.perf_counter()

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0,
            "top_k": 5,
            "seed": 42
        }
    )

    elapsed = time.perf_counter() - start

    print(f"LLM selesai dalam {elapsed:.2f} detik")

    return response["message"]["content"].strip()



# preprocessing
# ----------------
def preprocessing_berita(teks: str):
    clean_text = teks.encode("ascii", "ignore").decode()    # membersihkan karakter yang tidak perlu (emotikon dsb)
    # links = re.findall(r'http[s]?://\S+', clean_text)     # ambil semua link url
    clean_text = re.sub(r'http[s]?://\S+', '',clean_text)   # hapus link yang didapat dari teks
    # clean_text = re.sub(r"[^\w\s]", ' ',clean_text)         # hapus tanda baca berlebih
    clean_text = re.sub(r'\s+', ' ',clean_text).strip()     # rapikan spasi berlebih
    print("\nTeks Bersih: ")
    print("-------")
    print(clean_text)

    return clean_text



# extract main claim
# ----------------
def extract_claim(teks: str):

    prompt = f"""
Anda adalah sistem ekstraksi klaim.

Tugas:
Tuliskan kembali klaim utama dari teks berikut dengan sangat singkat.

Aturan:
- Jangan menambah kalimat lain selain klaim inti.
- Jangan mengubah subjek.
- Jangan mengubah objek.
- Jangan mengubah lokasi.
- Jangan mengubah waktu.
- Jangan mengganti kata dengan sinonim.
- Jangan menambahkan informasi baru.
- Jangan menambahkan tanda kutip.
- Jika teks sudah berupa klaim, cukup rapikan tata bahasanya.

Output:
Satu kalimat klaim tanpa kalimat pengantar

Teks:
{teks}
"""
    
    claim = ask_llm(prompt)

    print("\nKlaim utama berita:")
    print("-------")
    print(claim)

    return claim



# generate query for serching masih kureng
# ---------
def generate_query(claim: str):

    prompt = f"""
Buat keyword pencarian berita dari klaim berikut.

Aturan:
- ambil kata paling spesifik dan penting
- pertahankan nama, lokasi, atau objek unik jika ada
- jangan tambah informasi baru
- jangan ubah makna
- output hanya 1 keyword singkat

Klaim:
{claim}
"""

    query = ask_llm(prompt)
    query = query.replace('"', "").replace('.', "").strip()

    print("\nKeyword pencarian:")
    print("-------")
    print(query)

    return query



# search in first layer turnbackhoax
# -------------------------
def search_turnbackhoax(query: str):

    for method in ["title", "content"]:

        payload = {
            "key": TURNBACKHOAX_API_KEY,
            "method": method,
            "value": query,
            "limit": 5
        }

        try:

            response = requests.post(
                BASE_URL,
                data=payload,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

        except Exception as e:

            print(f"\nERROR ({method}) :", e)
            continue

        if not data:
            continue

        print("\n========================================")
        print("HASIL TURNBACKHOAX")
        print("========================================")
        print("Metode :", method)
        print("Query  :", query)
        print("Jumlah :", len(data))
        print("----------------------------------------")

        for i, item in enumerate(data, start=1):

            print(f"{i}. {item['title']}")
            print(f"   Status : {item['status']}")
            print(f"   Tanggal: {item['tanggal']}")
            print()

        return data

    print("\nHASIL TURNBACKHOAX")
    print("========================================")
    print("Tidak ditemukan kandidat.")

    return []


# cek relevansi klaim dengan judul berita terverifikasi
# ---------
# def relevance_check(claim: str, title: str):

#     claim = claim.lower().replace('"', "").strip()
#     title = title.lower().replace('"', "").strip()

#     prompt = f"""
# Klaim:
# {claim}

# Judul Artikel:
# {title}

# Tugas:
# Tentukan apakah judul artikel membahas peristiwa atau topik yang sama dengan klaim.

# Tidak harus identik kata per kata.
# Jangan hanya karena memiliki nama orang atau topik yang sama.
# Jika hanya membahas topik yang sama tetapi peristiwanya berbeda, jawab tidak.
# Jika subjek, objek, lokasi, atau peristiwa utama sama, jawab ya

# Jawab hanya satu kata "ya" atau "tidak"

# """

#     hasil = ask_llm(prompt)
#     hasil = hasil.replace('"', "").replace('.', "").lower() 
#     return hasil

def relevance_check(claim: str, title: str, fact: str):

    prompt = f"""
Klaim Pengguna:
{claim}

Judul Artikel:
{title}

Hasil Pemeriksaan Fakta:
{fact}

Tugas:
Tentukan apakah artikel di atas memverifikasi klaim yang sama dengan klaim pengguna.

Aturan:
- Fokus pada klaim yang diperiksa, bukan hanya topik yang dibahas.
- Klaim dianggap sama apabila subjek, objek, aksi/kejadian, serta konteks utama merujuk pada informasi yang sama.
- Perbedaan pilihan kata diperbolehkan selama maknanya tetap sama.
- Jika artikel hanya membahas topik yang sama tetapi memeriksa klaim, angka, waktu, konteks, atau pernyataan yang berbeda, jawab "tidak".
- Jika artikel memverifikasi, mengklarifikasi, membenarkan, atau membantah klaim yang sama, jawab "ya".
- Jangan menilai apakah klaim benar atau salah. Nilailah hanya apakah klaim yang diperiksa sama.

Jawab hanya satu kata "ya" atau "tidak"
"""

    hasil = ask_llm(prompt)
    return hasil.replace('"', "").replace(".", "").strip().lower()



# Evaluasi relevansi kandidat
# ---------
def evaluate_candidates(claim, candidates):

    relevant_articles = []

    for item in candidates:

        title = item["title"]
        fact = item["fact"]
        title = re.sub(
            r"\[(SALAH|HOAKS|KLARIFIKASI|PENIPUAN)\]",
            "",
            title,
            flags=re.IGNORECASE
        )

        relevansi = relevance_check(
            claim,
            title,
            fact
        )

        print("\n-------")
        print("Judul :", title)
        print("Status :", item["status"])
        print("Is Relevan? :", relevansi)

        if "ya" in relevansi.lower():

            relevant_articles.append(item)

    return relevant_articles


def aggregate_turnbackhoax(relevant_articles):

    valid = 0
    hoax = 0

    for article in relevant_articles:

        status = str(article.get("status", "")).strip().lower()

        if status in {"1", "benar", "valid", "true", "iya"}:
            valid += 1

        elif status in {"2", "salah", "hoax", "hoaks", "false", "tidak"}:
            hoax += 1

    if valid == 0 and hoax == 0:
        return "Tidak Diketahui"

    elif valid > hoax:
        return "Valid"

    elif hoax > valid:
        return "Hoax"
    else:
        return "Tidak Diketahui"


# generate final reason
# -------
# def generate_reason(claim: str, fact: str, conclusion: str):

#     prompt = f"""
# Klaim:
# {claim}

# Hasil Penelusuran:
# {fact}

# Kesimpulan:
# {conclusion}

# Tugas:
# Jelaskan mengapa hasil penelusuran tersebut relevan terhadap klaim.

# Aturan:
# - jelaskan dengan beberapa kalimat ringkas yang menjelaskan hubungan antar klaim dan hasil penelusuran
# - gunakan hanya informasi yang tersedia
# - jangan menyalin mentah isi hasil penelusuran

# Output adalah hasil analisi verifikasi.
# """

#     reason = ask_llm(prompt)
#     return reason


def generate_reason_layer1(claim: str, articles: list, status: str):
    evidence_text = ""

    for i, article in enumerate(articles, start=1):
        evidence_text += f"""
Artikel {i}

Narasi:
{article.get("content", "")}

Hasil Pemeriksaan Fakta:
{article.get("fact", "")}
"""

    prompt = f"""
Klaim:
{claim}

Status Verifikasi:
{status}

Daftar Bukti:
{evidence_text}

Tugas:
Buat alasan verifikasi berdasarkan seluruh bukti yang ditemukan.

Aturan:
- Gunakan semua bukti yang tersedia.
- Jelaskan mengapa klaim dikategorikan sebagai {status}.
- Jangan menambah informasi baru.
- Ringkas dalam satu paragraf.
- gunakan hanya informasi yang tersedia
- jangan menyalin mentah isi hasil penelusuran

Output adalah alasan verifikasi.
"""

    return ask_llm(prompt)



# generate final output (status, reason, link sumber berita)
# ----------
def generate_verification_result(claim, relevant_articles):

    if not relevant_articles:

        print("\nHASIL VERIFIKASI")
        print("-------")
        print("Status : Tidak Diketahui")
        print("Reason : Tidak ditemukan artikel relevan dari TurnBackHoax.")

        return {
            "status": "Tidak Diketahui",
            "reason": "Tidak ditemukan artikel relevan dari TurnBackHoax.",
            "sources": []
        }

    final_status = aggregate_turnbackhoax(relevant_articles)
    reason = generate_reason_layer1(claim, relevant_articles, final_status)

    print("\nHASIL VERIFIKASI")
    print("-------")
    print("Status :", final_status)

    print("\nReason :")
    print(reason)

    print("\nSumber Relevan :")

    sources = []

    for item in relevant_articles:

        url = f"https://turnbackhoax.id/articles/{item['id']}"

        print(f"- {item['title']}")
        # print(f"  Status  : {item['status']}")
        # print(f"  Tanggal : {item['tanggal']}")
        print(f"  URL     : {url}")
        print()

        sources.append({
            "title": item["title"],
            "url": url
        })

    return {
        "status": final_status,
        "reason": reason,
        "sources": sources
    }



if __name__ == "__main__":
    berita = input("Masukkan berita: ")
    # pipeline(berita)
    # claim = "Ratusan tentara israel dkabarkan tewas di perbatasan selat hormuz"
    claim = extract_claim(berita)
    search_keyword = generate_query(claim)  #keyword masih kurang efetif buat pencariannya, cari metode lain ya entah bebeapa query atau gimana
    candidates = search_turnbackhoax(search_keyword) 
    relevance = evaluate_candidates(claim, candidates)
    generate_verification_result(claim, relevance)


    