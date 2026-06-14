import re
import requests
from urllib.parse import quote #encode link sumber
from groq import Groq 
import os
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "openai/gpt-oss-120b"
TURNBACKHOAX_API_KEY = os.getenv("TURNBACKHOAX_API_KEY")
BASE_URL = "https://yudistira.turnbackhoax.id/Antihoax"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(
    api_key=GROQ_API_KEY
)



# llm response
def ask_llm(prompt: str):

    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        top_p=0.1,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content.strip()



# preprocessing
# ----------------
def preprocessing_berita(teks: str):
    clean_text = teks.encode("ascii", "ignore").decode()    # membersihkan karakter yang tidak perlu (emotikon dsb)
    # links = re.findall(r'http[s]?://\S+', clean_text)     # ambil semua link url
    clean_text = re.sub(r'http[s]?://\S+', '',clean_text)   # hapus link yang didapat dari teks
    clean_text = re.sub(r"[^\w\s]", ' ',clean_text)         # hapus tanda baca berlebih
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
Satu kalimat klaim.

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
- output hanya 2 keyword singkat

Klaim:
{claim}
"""

    query = ask_llm(prompt)

    query = re.sub(r"[^\w\s]", "", query)

    print("\nQuery pencarian:")
    print("-------")
    print(query)

    return query



# search in first layer turnbackhoax
# -------------------------
def search_turnbackhoax(query: str):

    # url = f"{BASE_URL}/title/{query}/{API_KEY}"
    encoded_query = quote(query)
    url = f"{BASE_URL}/title/{encoded_query}/{API_KEY}"

    response = requests.get(url)

    data = response.json()

    print("\nHASIL TURNBACKHOAX")
    print("-------")

    if not data:
        print("data tidak ditemukan")
        return[]

    return data[:20]



# cek relevansi klaim dengan judul berita terverifikasi
# ---------
def relevance_check(claim: str, title: str):

    claim = claim.lower()
    title = title.lower()

    claim = re.sub(r"[^\w\s]", "", claim)
    title = re.sub(r"[^\w\s]", "", title)

    prompt = f"""
Klaim:
{claim}

Judul Artikel:
{title}

Tugas:
Tentukan apakah judul artikel membahas peristiwa atau topik yang sama dengan klaim.

Tidak harus identik kata per kata.

Jika subjek, objek, lokasi, atau peristiwa utama sama, jawab YA.

Jawab hanya:
ya
atau
tidak

"""

    hasil = ask_llm(prompt)
    return hasil



# Evaluasi relevansi kandidat
# ---------
def evaluate_candidates(claim, candidates):

    relevant_articles = []

    for item in candidates:

        title = item["title"]
        title = re.sub(
            r"\[(SALAH|HOAKS|KLARIFIKASI|PENIPUAN)\]",
            "",
            title,
            flags=re.IGNORECASE
        )
        
        status = item["status"]

        relevansi = relevance_check(claim, title)

        print("\n-------")
        print("Judul :", title)
        print("Status :", status)
        print("Is Relevan? :", relevansi)

        if "ya" in relevansi.lower():

            relevant_articles.append(item)

    return relevant_articles



# generate final reason
# -------
def generate_reason(claim: str, fact: str, conclusion: str):

    prompt = f"""
Klaim:
{claim}

Hasil Penelusuran:
{fact}

Kesimpulan:
{conclusion}

Tugas:
Jelaskan mengapa hasil penelusuran tersebut relevan terhadap klaim.

Aturan:
- jelaskan dengan beberapa kalimat ringkas yang menjelaskan hubungan antar klaim dan hasil penelusuran
- gunakan hanya informasi yang tersedia
- jangan menyalin mentah isi hasil penelusuran

Output adalah alasan verifikasi.
"""

    reason = ask_llm(prompt)
    return reason



# generate final output (status, reason, link sumber berita)
# ----------
def generate_verification_result(
    claim,
    relevant_articles
):

    if not relevant_articles:

        print("\nHASIL VERIFIKASI")
        print("-------")
        print("Status : Tidak Diketahui")
        print("Reason : Tidak ditemukan artikel relevan dari TurnBackHoax.")
        return

    article = relevant_articles[0]

    reason = generate_reason(
        claim,
        article["content"],
        article["fact"]
    )

    print("\nHASIL VERIFIKASI")
    print("-------")

    print("Status :", article["status"])

    print("\nReason :")
    print(reason)

    print("\nSumber Relevan :")

    for item in relevant_articles:
        print(
            "-",
            # f"https://cekfakta.com/focus/{item['id']}"
            f"https://turnbackhoax.id/articles/{item['id']}"
            # bingung gimana nampilinya karena dikedua sumber ada, satu database yang sama kan kayaknya disebutin dua duanya aja kalo ada gatau caranya hehehe
        )



if __name__ == "__main__":
    # berita = input("Masukkan berita: ")
    # pipeline(berita)
    claim = "Ratusan tentara Israel dilaporkan tewas di wilayah perbatasan Selat Hormuz"

    # search_keyword = "selat hormuz" 
    # search_keyword = generate_query(claim)  #keyword masih kurang efetif buat pencariannya, cari metode lain ya entah bebeapa query atau gimana
    candidates = search_turnbackhoax("selat hormuz") 
    relevance = evaluate_candidates(claim, candidates)
    generate_verification_result(claim, relevance)


    