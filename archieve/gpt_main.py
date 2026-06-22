import os
import re
from urllib.parse import quote
from dotenv import load_dotenv
import requests
import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq 
from newspaper import Article, Config
from pygooglenews import GoogleNews
from googlenewsdecoder import gnewsdecoder
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")

load_dotenv()

MODEL_NAME="openai/gpt-oss-120b"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TURNBACKHOAX_API_KEY = os.getenv("TURNBACKHOAX_API_KEY")
BASE_URL = "https://yudistira.turnbackhoax.id/Antihoax"

client = Groq(
    api_key=GROQ_API_KEY
)

API_KEY = TURNBACKHOAX_API_KEY


app = FastAPI(title="News Verification API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


def preprocessing_berita(teks: str):
    clean_text = teks.encode("ascii", "ignore").decode()
    clean_text = re.sub(r"http[s]?://\S+", "", clean_text)
    # clean_text = re.sub(r"[^\w\s]", " ", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text


def extract_claim(teks: str):
    prompt = f"""
Anda adalah sistem ekstraksi klaim.

Tugas:
Tuliskan kembali klaim utama dari teks berikut dengan sangat singkat tanpa kalimat pengantar

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

    return ask_llm(prompt)


def generate_query(claim: str):
    prompt = f"""
Buat keyword pencarian berita singkat dari klaim berikut.

Aturan:
- ambil kata paling penting
- pertahankan nama, lokasi, atau objek unik jika ada
- jangan tambah informasi baru
- jangan ubah makna
- output hanya 1 keyword singkat
- jangan terlalu umum

Klaim:
{claim}
"""

    query = ask_llm(prompt)
    return re.sub(r"[^\w\s]", "", query).lower()


def relevance_check(claim: str, title: str):
    claim = re.sub(r"[^\w\s]", "", claim).lower()
    title = re.sub(r"[^\w\s]", "", title).lower()

    prompt = f"""
Klaim:
{claim}

Judul Artikel:
{title}

Tugas:
Tentukan apakah judul berita membahas peristiwa yang sama dengan klaim.

Aturan:

- subjek, objek dan aksi atau kejadian utama harus sama.
- Jangan hanya karena memiliki nama orang atau topik yang sama.
- Jika hanya membahas topik yang sama tetapi peristiwanya berbeda, jawab tidak.
- Jika judul mendukung, membantah, atau mengklarifikasi klaim yang sama, jawab ya.

Jawab hanya satu kata

"""
    
    hasil = ask_llm(prompt)
    hasil = re.sub(r"[^\w\s]", "", hasil).lower().strip()

    return hasil


def evaluate_candidates(claim, candidates):
    relevant_articles = []

    for item in candidates:
        title = item["title"]
        title = re.sub(
            r"\[(SALAH|HOAKS|KLARIFIKASI|PENIPUAN)\]",
            "",
            title,
            flags=re.IGNORECASE,
        )

        relevansi = relevance_check(claim, title)

        if "ya" in relevansi.lower():
            relevant_articles.append(item)

    return relevant_articles


def search_turnbackhoax(query: str):
    encoded_query = quote(query)
    url = f"{BASE_URL}/title/{encoded_query}/{API_KEY}"

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()

    if not data:
        return []

    return data[:20]


def aggregate_turnbackhoax(relevant_articles):

    valid = 0
    hoax = 0

    for article in relevant_articles:

        status = str(article.get("status", "")).strip().lower()

        if status in {"1", "benar", "valid", "true", "iya", "Benar"}:
            valid += 1

        elif status in {"2", "salah", "hoax", "hoaks", "false", "tidak", "Salah"}:
            hoax += 1

    if valid == 0 and hoax == 0:
        return "Tidak Diketahui"

    elif valid > hoax:
        return "Valid"

    elif hoax > valid:
        return "Hoax"



def generate_reason_layer1(claim: str, articles: list, status: str):
    evidence_text = ""

    for i, article in enumerate(articles, start=1):
        evidence_text += f"""
Artikel {i}

Narasi:
{article['content']}

Hasil Pemeriksaan Fakta:
{article['fact']}
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


def generate_verification_result(claim, relevant_articles):
    if not relevant_articles:
        return {
            "status": "Tidak Diketahui",
            "reason": "Tidak ditemukan artikel relevan dari TurnBackHoax.",
            "sources": [],
            "layer": "turnbackhoax",
        }

    final_status = aggregate_turnbackhoax(relevant_articles)
    reason = generate_reason_layer1(claim, relevant_articles, final_status)
    sources = [
        {
            "title": item["title"],
            "url": f"https://turnbackhoax.id/articles/{item['id']}"
        }
        for item in relevant_articles
    ]

    return {
        "status": final_status,
        "reason": reason,
        "sources": sources,
        "layer": "turnbackhoax",
    }


def search_google_news(query: str):
    gn = GoogleNews(lang="id", country="ID")
    hasil = gn.search(query)
    entries = hasil["entries"][:20]

    if not entries:
        return []

    news_list = []

    for entry in entries:
        news_list.append({"title": entry.title, "link": entry.link})

    return news_list


def news_content(url_google: str):
    config = Config()
    config.browser_user_agent = "Mozilla/5.0"
    config.request_timeout = 10

    try:
        decoded = gnewsdecoder(url_google)

        if not decoded.get("status"):
            return ""

        url_asli = decoded["decoded_url"]
        artikel = Article(url_asli, config=config)
        artikel.download()
        artikel.parse()

        return {"content": artikel.text, "url": url_asli}
    except Exception:
        return ""


def scrape_relevant_articles(relevant_news):
    scraped_articles = []

    for article in relevant_news:
        hasil = news_content(article["link"])

        if not hasil:
            continue

        if not hasil["content"].strip():
            continue

        scraped_articles.append(
            {
                "title": article["title"],
                "link": hasil["url"],
                "content": hasil["content"],
            }
        )

    return scraped_articles


def detect_stance(claim: str, content: str):
    prompt = f"""
Klaim:
{claim}

Isi Berita:
{content}

Tugas:
Tentukan hubungan isi berita terhadap klaim.

Kategori:

- mendukung
  jika isi berita mendukung atau mengonfirmasi klaim

- membantah
  jika isi berita menyangkal, mengoreksi, atau menunjukkan klaim tidak benar

ATURAN PENTING:
- Jawab hanya satu kata
- Gunakan HANYA informasi dari isi berita.
- Jangan menggunakan pengetahuan luar.
- Jika berita menyatakan hal yang sama dengan klaim,
  jawab mendukung
- Jika berita menyatakan kebalikan dari klaim,
  jawab membantah

"""

    hasil = ask_llm(prompt)
    hasil = re.sub(r"[^\w\s]", "", hasil).lower().strip()

    return hasil


def aggregate_stance(scraped_articles):
    mendukung = 0
    membantah = 0

    for article in scraped_articles:
        stance = article["stance"]

        if stance == "mendukung":
            mendukung += 1
        elif stance == "membantah":
            membantah += 1

    if mendukung == 0 and membantah == 0:
        status = "Tidak Diketahui"
    elif mendukung > membantah:
        status = "Valid"
    elif membantah > mendukung:
        status = "Hoax"
   

    return {"status": status, "mendukung": mendukung, "membantah": membantah}


def generate_reason_layer2(claim: str, articles: list, status: str):
    if status == "Tidak Diketahui":
        return (
            "Tidak ditemukan bukti yang cukup untuk memverifikasi klaim. "
            "Sistem tidak menemukan artikel yang relevan atau bukti yang "
            "dapat digunakan untuk mendukung maupun membantah klaim. "
            "Informasi ini belum dapat dipastikan benar maupun salah. "
            "Disarankan untuk tidak menyebarkan informasi tersebut "
            "sebelum tersedia sumber yang kredibel."
        )

    evidence_text = ""

    for i, article in enumerate(articles, start=1):
        evidence_text += f"""
Bukti {i}

Judul:
{article['title']}

Stance:
{article['stance']}
"""

    prompt = f"""
Klaim:
{claim}

Status Verifikasi:
{status}

Daftar Bukti:
{evidence_text}

Tugas:
Buat alasan verifikasi berdasarkan seluruh bukti.

Aturan:
- Jelaskan mengapa klaim dianggap valid atau hoax.
- Gunakan informasi dari bukti yang tersedia.
- Jangan menambah informasi baru.
- Ringkas dalam satu paragraf.
"""

    return ask_llm(prompt)


def verify_news(berita: str):

    print("Debugging")
    print("----------------")
    print("\nInput:")
    print(berita)

    cleaned = preprocessing_berita(berita)

    print("\nTeks Bersih:")
    print(cleaned)

    claim = extract_claim(cleaned)

    print("\nKlaim Inti Berita:")
    print(claim)

    search_keyword = generate_query(claim)

    print("\nKeyword Pencarian:")
    print(search_keyword)

    try:
        candidates = search_turnbackhoax(search_keyword)
    except Exception:
        candidates = []

    print("\nLayer 1 - TurnBackHoax")
    print("Jumlah kandidat:", len(candidates))

    relevant_articles = evaluate_candidates(claim, candidates)

    print("Artikel relevan:", len(relevant_articles))

    for item in relevant_articles:
        print("-", item["title"])

    if relevant_articles:
        result = generate_verification_result(claim, relevant_articles)
        result.update({"claim": claim, "search_keyword": search_keyword})

        print("\nHASIL AKHIR")
        print("Status :", result["status"])
        print("Layer  :", "turnbackhoax")
        print("-------------------------\n")

        print("\nReason :")
        print(result["reason"])

        print("\nSumber :")
        for source in result["sources"]:
            print("-", source)
            print(" ", source["url"])

        print("-------------------------\n")

        return result
    
    print("\nLayer 1 tidak menemukan hasil.")
    print("Melanjutkan ke Google News...")

    news_list = search_google_news(claim)

    print("\nGoogle News")
    print("Jumlah berita:", len(news_list))

    relevant_news = evaluate_candidates(claim, news_list)

    if not relevant_news:
        return {
            "status": "Tidak Diketahui",
            "reason": (
                "Tidak ditemukan artikel yang relevan untuk memverifikasi klaim. "
                "Informasi ini belum dapat dipastikan benar maupun salah. "
                "Disarankan untuk tidak menyebarkan informasi tersebut "
                "sebelum tersedia sumber yang kredibel."
            ),
            "sources": [],
            "claim": claim,
            "search_keyword": search_keyword,
            "layer": "google_news",
        }

    scraped_articles = scrape_relevant_articles(relevant_news)

    print("Artikel berhasil discrape:", len(scraped_articles))

    if not scraped_articles:
        return {
            "status": "Tidak Diketahui",
            "reason": (
                "Artikel relevan ditemukan, tetapi isi artikel "
                "tidak berhasil diambil sehingga verifikasi "
                "tidak dapat dilakukan."
            ),
            "sources": [],
            "claim": claim,
            "search_keyword": search_keyword,
            "layer": "google_news",
        }

    for article in scraped_articles:
        article["stance"] = detect_stance(claim, article["content"])
        print(article["title"])
        print("->", article["stance"])

    result = aggregate_stance(scraped_articles)
    reason = generate_reason_layer2(claim, scraped_articles, result["status"])

    print("\nHASIL AKHIR")
    print("Status :", result["status"])
    print("Layer  :", "google_news")
    print("-----------------------\n")

    print("\nReason :")
    print(reason)

    print("\nSumber :")
    for article in scraped_articles:
        print("-", article["link"])
        print(" ", article["url"])

    print("-----------------------\n")

    return {
        "status": result["status"],
        "reason": reason,
        "sources": [
            {
                "title": article["title"],
                "url": article["link"]
            }
            for article in scraped_articles
        ],
        "claim": claim,
        "search_keyword": search_keyword,
        "layer": "google_news",
        "articles": scraped_articles,
        "counts": {
            "mendukung": result["mendukung"],
            "membantah": result["membantah"],
        },
    }


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.post("/verifikasi")
def verifikasi(berita: str = Form(...)):
    try:
        return verify_news(berita)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    uvicorn.run("llama_main:app", host="127.0.0.1", port=8000, reload=True)


# masih belum fiks di url source yang ditampilkan di layer 1 ya 
# parameter berita yang diambil masih belum difiks kan 
# model pakai GPT bukan llama 
# cek semua kondisi lagi 
# penamaan label untuk judul relevan namun artikel tidak bisa discrapping atau ada solusi lain?