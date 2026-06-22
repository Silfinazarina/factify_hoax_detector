import re
import os
from dotenv import load_dotenv
import requests
from urllib.parse import quote #encode link sumber 
import ollama
from pygooglenews import GoogleNews
from newspaper import Article, Config
from googlenewsdecoder import gnewsdecoder


load_dotenv()

MODEL_NAME="llama3.2:3b"
TURNBACKHOAX_API_KEY = os.getenv("TURNBACKHOAX_API_KEY")
BASE_URL = "https://yudistira.turnbackhoax.id/Antihoax"
API_KEY = TURNBACKHOAX_API_KEY


# REUSABLE FUNCT

# llm response
# def ask_llm(prompt: str):

#     response = ollama.chat(
#         model=MODEL_NAME,
#         messages=[
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]
#     )

#     return response["message"]["content"].strip()





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
    
    claim = ask_llm_v2(prompt)

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
- ambil kata paling umum dan penting
- pertahankan nama, lokasi, atau objek unik jika ada
- jangan tambah informasi baru
- jangan ubah makna
- output hanya 1 keyword singkat tanpa kata pengantar

Klaim:
{claim}
"""

    query = ask_llm(prompt)
    query = re.sub(r"[^\w\s]", "", query)

    print("\nQuery pencarian:")
    print("-------")
    print(query)

    return query



# cek relevansi klaim dengan judul berita terverifikasi
# ---------
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
    hasil = re.sub(r"[^\w\s]", "", hasil).lower()
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
        
        # status = item["status"]

        relevansi = relevance_check(claim, title)

        print("\n-------")
        print("Judul :", title)
        # print("Status :", status) 
        print("Is Relevan? :", relevansi)

        if "ya" in relevansi.lower():
            relevant_articles.append(item)

    return relevant_articles







# LAYER 1 FUNCT

# search in first layer turnbackhoax
# -------------------------
def search_turnbackhoax(query: str):

    # url = f"{BASE_URL}/title/{query}/{API_KEY}" #kenapa harus di encode?
    encoded_query = quote(query)
    url = f"{BASE_URL}/title/{encoded_query}/{API_KEY}"

    response = requests.get(url)

    data = response.json()

    print("\nHASIL TURNBACKHOAX")
    print("-------")

    if not data:
        print("data tidak ditemukan")
        return[]

    return data[:5]



def aggregate_turnbackhoax(relevant_articles):

    valid = 0
    hoax = 0

    for article in relevant_articles:

        status = article["status"]

        if str(status) == "1":
            valid += 1

        elif str(status) == "2":
            hoax += 1

    if valid == 0 and hoax == 0:
        return "Tidak Terverifikasi"

    elif valid > hoax:
        return "Valid"

    elif hoax > valid:
        return "Hoax"

    # else:
    #     return "Belum Konklusif"


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

    final_status = aggregate_turnbackhoax(
        relevant_articles
    )

    reason = generate_reason_layer1(
        claim,
        relevant_articles,
        final_status
    )

    print("\nHASIL VERIFIKASI")
    print("-------")

    final_status = aggregate_turnbackhoax(
        relevant_articles
    )

    print("Status :", final_status)

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



# generate final reason
# -------
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

    reason = ask_llm(prompt)
    return reason






# LAYER 2 FUNCT

def search_google_news(query: str):

    gn = GoogleNews(
        lang="id",
        country="ID"
    )

    hasil = gn.search(query)

    entries = hasil["entries"][:20] #

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

        return {
            "content": artikel.text,
            "url": url_asli
        }

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

        hasil = news_content(
            article["link"]
        )

        if not hasil:
            continue

        if not hasil["content"].strip():

            print(
                "Konten kosong, skip artikel :",
                article["title"]
            )

            continue

        print("JUDUL :", article["title"])

        scraped_articles.append({
            "title": article["title"],
            "link": hasil["url"],
            "content": hasil["content"]
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

mendukung
atau
membantah

"""

    hasil = ask_llm(prompt)
    hasil = re.sub(r"[^\w\s]", "", hasil).lower()

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

    if mendukung == 0 and membantah == 0:
        status = "Tidak Terverifikasi"

    elif mendukung > membantah:
        status = "Valid"

    elif membantah > mendukung:
        status = "Hoax"

    else:
        status = "Belum Konklusif"

    return {
        "status": status,
        "mendukung": mendukung,
        "membantah": membantah
    }



def generate_reason_layer2(
    claim: str,
    articles: list,
    status: str
):

    if status == "Tidak Terverifikasi":

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

    reason = ask_llm(prompt)
    return reason




if __name__ == "__main__":
    berita = input("Masukkan berita: ") 
    claim = extract_claim(berita)
    search_keyword = generate_query(claim) #keyword masih kurang efetif buat pencariannya, cari metode lain ya entah bebeapa query atau gimana
    candidates = search_turnbackhoax(search_keyword) 
    relevant_articles = evaluate_candidates(claim, candidates)
    if relevant_articles:
        generate_verification_result(claim, relevant_articles)

    else:
        print("\nTidak ditemukan artikel relevan di TurnBackHoax")

        news_list = search_google_news(claim)

        relevant_news = evaluate_candidates(
            claim,
            news_list
        )

        if not relevant_news:

            print("\nHASIL VERIFIKASI")
            print("==============")

            print("Status : Tidak Terverifikasi")

            print("\nReason :")
            print(
                "Tidak ditemukan artikel yang relevan untuk memverifikasi klaim. "
                "Informasi ini belum dapat dipastikan benar maupun salah. "
                "Disarankan untuk tidak menyebarkan informasi tersebut "
                "sebelum tersedia sumber yang kredibel."
            )

            exit()

        print("\n\nARTIKEL RELEVAN")
        print("===============")

        for item in relevant_news:

            print("-", item["title"])

        scraped_articles = scrape_relevant_articles(relevant_news)

        print("\nHASIL STANCE")
        print("==============")

        for article in scraped_articles:

            stance = detect_stance(claim, article["content"])

            article["stance"] = stance

            print("\n-------")
            print("Judul :", article["title"])
            print("Stance :", stance)
        
        result = aggregate_stance(
            scraped_articles
        )

        reason = generate_reason_layer2(
            claim,
            scraped_articles,
            result["status"]
        )

        print("\nHASIL VERIFIKASI")
        print("==============")

        print("Status :", result["status"])

        print("\nReason :")
        print(reason)

        print("\nSumber Relevan :")

        for article in scraped_articles:
            print("-", article["link"])
    