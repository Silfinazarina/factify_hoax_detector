import os
import re
from dotenv import load_dotenv
import requests
import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ollama
from newspaper import Article, Config
from pygooglenews import GoogleNews
from googlenewsdecoder import gnewsdecoder
from fastapi.templating import Jinja2Templates
from fastapi import Request
import time
import emoji
from groq import Groq
import trafilatura

templates = Jinja2Templates(directory="templates")


load_dotenv()

# MODEL_NAME="llama3.2:3b"
# TURNBACKHOAX_API_KEY = os.getenv("TURNBACKHOAX_API_KEY")
# BASE_URL = "https://yudistira.turnbackhoax.id/api/antihoax/search"

MODEL_NAME="openai/gpt-oss-120b"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TURNBACKHOAX_API_KEY = os.getenv("TURNBACKHOAX_API_KEY")
BASE_URL = "https://yudistira.turnbackhoax.id/api/antihoax/search"

client = Groq(
    api_key=GROQ_API_KEY
)

# API_KEY = TURNBACKHOAX_API_KEY


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
            "top_p": 0.1,
            # "seed": 42
        }
    )

    elapsed = time.perf_counter() - start

    print(f"\n----")
    print(f"LLM selesai dalam {elapsed:.2f} detik")

    return response["message"]["content"].strip()

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

    clean_text = emoji.replace_emoji(
        teks,
        replace=""
    ) #hapus emoji

    clean_text = re.sub(
        r'http[s]?://\S+',
        '',
        clean_text
    ) #hapus link

    clean_text = re.sub(
            r'\s+',
            ' ',
            clean_text
        ).strip() #hapus spasi berlebih

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
- output hanya satu kalimat klaim

Teks:
{teks}
"""

    return ask_llm(prompt)


def generate_keyword(claim: str):
    
    prompt = f"""
Buat keyword pencarian berita singkat dari klaim berikut.

Aturan:
- ambil kata paling spesifik dan penting
- pertahankan nama, lokasi, atau objek unik jika ada
- jangan tambah informasi baru
- jangan ubah makna
- output hanya 1 keyword singkat

Klaim:
{claim}
"""

    keyword = ask_llm(prompt)
    keyword = keyword.replace('"', "").replace('.', "").strip()
    return keyword


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


def evaluate_candidates(claim, candidates):

    relevant_articles = []

    for item in candidates:
        
        title = item["title"]
        fact = item.get("fact", "")
        title = re.sub(
            r"\[(SALAH|HOAKS|KLARIFIKASI|PENIPUAN)\]",
            "",
            title,
            flags=re.IGNORECASE,
        )

        relevansi = relevance_check(claim, title, fact)

        print("----------------------------------------")
        print("Judul     :", title)
        print("Relevansi :", relevansi)

        if "ya" in relevansi.lower():
            relevant_articles.append(item)

    return relevant_articles


def search_turnbackhoax(keyword: str, offset=0, limit=20):

    for method in ["title", "content"]:

        payload = {
            "key": TURNBACKHOAX_API_KEY,
            "method": method,
            "value": keyword,
            "limit": limit,
            "offset": offset
        }

        try:
            response = requests.post(
                BASE_URL,
                data=payload,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

        except Exception:
            continue

        print("Metode            :", method)
        print("Keyword Pencarian :", keyword)
        print("Kandidat Ditemukan:", len(data))
        # print("----------------------------------------")

        # for i, item in enumerate(data, start=1):
        #     print(f"{i}. {item['title']}")

        if data:
            return data
        
    return []


def aggregate_turnbackhoax(relevant_articles):

    valid = 0
    hoax = 0

    for article in relevant_articles:

        status = str(article.get("status", "")).strip().lower()

        if status in {"1", "benar", "valid", "true"}:
            valid += 1

        elif status in {"2", "salah", "hoax", "hoaks", "false"}:
            hoax += 1

    if valid > hoax:
        status = "Valid"

    elif hoax > valid:
        status = "Hoax"
    else:
        status = "Tidak Diketahui"

    return {
        "status": status,
        "valid": valid,
        "hoax": hoax
    }


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


def generate_verification_result(claim, relevant_articles, generate_reason=True):

    if not relevant_articles:

        return {
            "status": "Tidak Diketahui",
            "reason": "Tidak ditemukan artikel relevan dari TurnBackHoax.",
            "sources": [],
            "layer": "turnbackhoax",
        }

    final_status = aggregate_turnbackhoax(relevant_articles)

    print("\n----------------------------------------")
    print("HASIL AGREGASI")
    print("----------------------------------------")
    print("Valid :", final_status["valid"])
    print("Hoaks :", final_status["hoax"])

    # reason = generate_reason_layer1(claim, relevant_articles, final_status["status"])

    if generate_reason:
        reason = generate_reason_layer1(claim, relevant_articles, final_status["status"])
    else:
        reason = ""

    sources = [
        {
            "title": item["title"],
            "url": f"https://turnbackhoax.id/articles/{item['id']}"
        }
        for item in relevant_articles
    ]

    return {
        "status": final_status["status"],
        "reason": reason,
        "sources": sources,
        "layer": "turnbackhoax",
    }


def search_google_news(keyword: str, start=0, limit=20):
    gn = GoogleNews(lang="id", country="ID")
    hasil = gn.search(keyword)
    
    entries = hasil["entries"][start:start+limit]

    if not entries:
        return []

    news_list = []

    for entry in entries:
        news_list.append({"title": entry.title, "link": entry.link})

    return news_list


def search_google_news_until_relevant(claim, keyword):

    start = 0
    limit = 20
    max_candidate = 100

    while start < max_candidate:

        news_list = search_google_news(
            keyword,
            start=start,
            limit=limit
        )

        if not news_list:
            return []

        print(f"\n=== Batch {start+1}-{start+len(news_list)} ===")

        print("Berita Ditemukan :", len(news_list))
        print("----------------------------------------")

        for i, item in enumerate(news_list, start=start+1):
            print(f"{i}. {item['title']}")

        relevant_news = evaluate_candidates(claim, news_list)

        print("\nHASIL EVALUASI RELEVANSI")
        print("----------------------------------------")
        print("Artikel Relevan :", len(relevant_news))

        if relevant_news:

            for i, item in enumerate(relevant_news, start=1):
                print(f"{i}. {item['title']}")

            return relevant_news

        print("\nTidak ditemukan artikel relevan.")
        print("Melanjutkan ke batch berikutnya...\n")

        start += 10

    return []


def news_content(url_google: str):

    config = Config()
    config.browser_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
    config.request_timeout = 10

    try:

        # Decode URL Google News
        decoded = gnewsdecoder(url_google)

        if not decoded.get("status"):
            return ""

        url_asli = decoded["decoded_url"]

        # Metode 1 : Newspaper3k
        artikel = Article(url_asli, config=config)

        artikel.download()
        artikel.parse()

        if artikel.text.strip():

            return {
                "content": artikel.text,
                "url": url_asli
            }

        print("Newspaper3k gagal, mencoba Trafilatura...")

        # Metode 2 : Trafilatura
        downloaded = trafilatura.fetch_url(url_asli)

        if downloaded:

            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False
            )

            if text and text.strip():

                return {
                    "content": text,
                    "url": url_asli
                }

        print("Trafilatura juga gagal.")

        return ""

    except Exception as e:

        print("SCRAPING ERROR :", e)

        return ""


def scrape_relevant_articles(relevant_news):

    scraped_articles = []

    for article in relevant_news:
        hasil = news_content(article["link"])

        if not hasil:
            continue

        content = preprocessing_berita(hasil["content"])

        if not hasil["content"].strip():
            continue

        scraped_articles.append(
            {
                "title": article["title"],
                "link": hasil["url"],
                "content": content,
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
    hasil = hasil.replace(".","").lower().strip()

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

    if mendukung > membantah:
        status = "Valid"
    elif membantah > mendukung:
        status = "Hoax"
    else:
        status = "Tidak Diketahui"

    return {"status": status, 
            "mendukung": mendukung, 
            "membantah": membantah
            }


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


def verify_news(berita: str, generate_reason=True):

    print("Debugging")
    print("==================================")

    print("\nInput Berita:")
    print("---")
    print(berita)

    cleaned = preprocessing_berita(berita)

    print("\nTeks Bersih:")
    print("-------")
    print(cleaned)

    claim = extract_claim(cleaned)

    print("\nKlaim Inti Berita:")
    print("-------")
    print(claim)

    search_keyword = generate_keyword(claim)

    print("\nKeyword Pencarian:")
    print("-------")
    print(search_keyword)

    print("\nLayer 1 - TurnBackHoax")
    print("==================================")

    relevant_articles = []

    offset = 0

    while offset < 100:

        print(f"\nTurnBackHoax Batch {offset+1}-{offset+20}")

        try:

            candidates = search_turnbackhoax(
                search_keyword,
                offset=offset,
                limit=20
            )

        except Exception:

            candidates = []

        if not candidates:

            break

        relevant_articles = evaluate_candidates(
            claim,
            candidates
        )

        print("\nArtikel relevan:", len(relevant_articles))
        print("-------")
        for item in relevant_articles:
            print("\n-", item["title"])
            print("  ", item["status"])

        if relevant_articles:

            break

        print("Tidak ditemukan artikel relevan.")
        print("Melanjutkan batch berikutnya...")

        offset += 10

    if relevant_articles:

        result = generate_verification_result(
            claim,
            relevant_articles,
            generate_reason
        )

        result.update({
            "claim": claim,
            "search_keyword": search_keyword
        })

        print("\nHASIL LAYER 1")
        print("Status :", result["status"])

        # Kalau sudah konklusif, selesai
        if result["status"] != "Tidak Diketahui":

            print("Layer  :", "turnbackhoax")
            print("-------------------------")

            print("\nReason :")
            print(result["reason"])

            print("\nSumber :")
            for source in result["sources"]:
                print("-", source["title"])
                print(" ", source["url"])

            print("-------------------------")

            return result

        # Kalau hasilnya Tidak Diketahui
        print("\nLayer 1 belum konklusif.")
        print("Melanjutkan ke Google News...")

    if not relevant_articles:

        print("\nLayer 1 tidak menemukan hasil.")
        print("Melanjutkan ke Google News...")

    print("\nLayer 2 - Google News")
    print("==================================")

    # news_list = search_google_news(search_keyword)
    
    relevant_news = search_google_news_until_relevant(
        claim,
        search_keyword
    )

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

    print("\nSCRAPPING")
    print("----------------------------------------")
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

    print("\nHASIL DETEKSI STANCE")
    print("----------------------------------------")

    for article in scraped_articles:

        article["stance"] = detect_stance(claim, article["content"])

        print("\n",article["title"])
        print("->", article["stance"])

    result = aggregate_stance(scraped_articles)

    print("\nHASIL AGREGASI")
    print("----------------------------------------")
    print("Mendukung :", result["mendukung"])
    print("Membantah :", result["membantah"])
    print("Status    :", result["status"])

    if generate_reason:
        reason = generate_reason_layer2(claim, scraped_articles, result["status"])
    else:
        reason = ""

    print("\nHASIL AKHIR")
    print("Status :", result["status"])
    print("Layer  :", "google_news")
    print("-----------------------\n")

    print("\nReason :")
    print(reason)

    print("\nSumber :")
    for article in scraped_articles:
        print("-", article["title"])
        print(" ", article["link"])

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
# cek semua kondisi lagi 