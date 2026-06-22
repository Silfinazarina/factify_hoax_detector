import re
import os
from pygooglenews import GoogleNews
from newspaper import Article, Config
from googlenewsdecoder import gnewsdecoder
from dotenv import load_dotenv
import time
import ollama

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
            # "top_k": 5,
            # "seed": 42
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


# generate query for serching masih kureng
# ---------
# def generate_query(claim: str):

#     prompt = f"""
# Buat keyword pencarian berita dari klaim berikut.

# Aturan:
# - ambil kata paling spesifik dan penting
# - pertahankan nama, lokasi, atau objek unik jika ada
# - jangan tambah informasi baru
# - jangan ubah makna
# - output hanya 1 keyword singkat

# Klaim:
# {claim}
# """

#     query = ask_llm(prompt)
#     query = query.replace('"', "").replace('.', "").strip()

#     print("\nKeyword pencarian:")
#     print("-------")
#     print(query)

#     return query


def search_google_news(query: str):

    gn = GoogleNews(
        lang="id",
        country="ID"
    )

    hasil = gn.search(query)

    entries = hasil["entries"][:10]

    if not entries:

        print("Berita tidak ditemukan")
        return []

    news_list = []

    for entry in entries:

        title = entry.title
        link = entry.link

        # print("\nJudul :", title)
        # print("Link :", link)
        

        news_list.append({
            "title": title,
            "link": link,
        })

    return news_list

# cek relevansi judul dengan klaim
def relevance_check(claim: str, title: str):

    claim = claim.lower().replace('"', "").strip()
    title = title.lower().replace('"', "").strip()

    prompt = f"""
Klaim:
{claim}

Judul Artikel:
{title}

Tugas:
Tentukan apakah judul artikel membahas peristiwa yang sama dengan klaim.

ATURAN PENTING:
Tidak harus identik kata per kata.
Jangan hanya karena memiliki nama orang atau topik yang sama.
Jika hanya membahas topik yang sama tetapi peristiwanya berbeda, jawab tidak.
Jika subjek, objek, lokasi, atau peristiwa utama sama, jawab ya
Jangan menilai benar atau salah klaim.
Hanya nilai apakah artikel membahas kejadian yang sama.

Jawab hanya satu kata "ya" atau "tidak"

"""

    hasil = ask_llm(prompt)
    hasil = hasil.replace('"', "").replace('.', "").lower() 
    return hasil


# konten berita
def news_content(url_google: str):

    config = Config()
    config.browser_user_agent = "Mozilla/5.0"
    config.request_timeout = 10

    try:

        decoded = gnewsdecoder(url_google)

        if not decoded.get("status"):
            return ""

        url_asli = decoded["decoded_url"]

        # print("\nURL GOOGLE:")
        # print(url_google)

        print("\n")
        print("\n\n===========================")
        print("URL DECODE:")
        print(url_asli)
       

        artikel = Article(
            url_asli,
            config=config
        )

        artikel.download()
        artikel.parse()

        return artikel.text

    except Exception as e:

        print("\nERROR SCRAPING URL:")
        print(url_google)

        print("\nERROR:")
        print(e)

        return ""



# scraping artikel relevan
def scrape_relevant_articles(relevant_news):

    scraped_articles = []

    for article in relevant_news:

        content = news_content(
            article["link"]
        )

        print("JUDUL :", article["title"])

        print(content)

        if not content.strip():

            print("Konten gagal diambil, skip artikel")
            continue

        scraped_articles.append({
            "title": article["title"],
            "link": article["link"],
            "content": content
        })

    return scraped_articles


#  keterkaitan klaim dengan konten berita
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


# agregasi bukti 
def aggregate_stance(scraped_articles):

    mendukung = 0
    membantah = 0

    for article in scraped_articles:

        stance = article["stance"]

        if stance == "mendukung":
            mendukung += 1

        elif stance == "membantah":
            membantah += 1

    print("\nHASIL AGREGASI")
    print("==============")
    print("Mendukung :", mendukung)
    print("Membantah :", membantah)

    if membantah > mendukung:

        status = "Hoax"

    elif mendukung > membantah:

        status = "Valid"

    else:

        status = "Tidak Diketahui"

    return {
        "status": status,
        "mendukung": mendukung,
        "membantah": membantah
    }



def generate_reason(claim: str, articles: list, status: str):
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



def generate_verification_result(
    claim,
    articles
):

    result = aggregate_stance(
        articles
    )

    reason = generate_reason(
        claim,
        articles,
        result["status"]
    )

    print("\nHASIL VERIFIKASI")
    print("================")

    print("Status :",
          result["status"])

    print("\nReason :")
    print(reason)

    print("\nSumber :")

    for article in articles:

        print("-",
              article["title"])




if __name__ == "__main__":

    berita = input("Masukkan berita: ")

    claim = extract_claim(berita)

    # search_keyword = generate_query(claim)

    news_list = search_google_news(claim) # cari sumber berita artikel berdasarkan klaim agar hasiil pencaian tidak terlalu umum

    relevant_news = []

    for item in news_list:

        title = item["title"]

        relevansi = relevance_check(claim, title) # cek relevansi judul berita yang diperoleh dengan klaim berita

        print("\n-------")
        print("Judul :", title)
        print("Relevansi :", relevansi)

        if "ya" in relevansi:

            relevant_news.append(item) # simpan yang relevan (ya) 

    print("\n\nARTIKEL RELEVAN")
    print("===============")

    for item in relevant_news:

        print("-", item["title"])

    print("===============")

    scraped_articles = scrape_relevant_articles(relevant_news) # ambil isi konten sumber artikel yang relevan

    print("\nHASIL STANCE")
    print("==============")

    for article in scraped_articles:

        stance = detect_stance(
            claim,
            article["content"]
        )

        article["stance"] = stance

        print("Judul :", article["title"])
        print("Stance :", stance)


    generate_verification_result(
        claim,
        scraped_articles
    )