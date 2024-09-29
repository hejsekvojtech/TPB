import json
import os
import re
import time
import uuid
from random import randint
from multiprocessing import Pool, Manager
from filelock import FileLock

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

def create_driver():
    options = Options()
    options.add_argument("-headless")
    return webdriver.Firefox(options=options)

def save_article(article_data, session_uuid, directory='data'):
    file_path = os.path.join(directory, f'{session_uuid}.json')
    lock = FileLock(f"{file_path}.lock")

    with lock:
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

        with open(file_path, 'r+', encoding='utf-8') as f:
            try:
                articles = json.load(f)
            except json.JSONDecodeError:
                print("JSON decode error occurred, resetting file.")
                articles = []

            articles.append(article_data)
            f.seek(0)
            f.truncate()  # Clear the file before writing new data
            json.dump(articles, f, ensure_ascii=False, indent=4)

def get_data_size(directory):
    total_size = sum(os.path.getsize(os.path.join(directory, f)) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)))
    return total_size / (1024 * 1024)

def vydridusi_bypass(url):
    driver = create_driver()
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        try:
            wait = WebDriverWait(driver, 2)
            continue_button = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "contentwall_ok")))
            if continue_button:
                time.sleep(randint(1, 3))
                continue_button.click()
                time.sleep(5)
        except Exception:
            pass
        finally:
            page_content = driver.page_source
            return page_content
    except Exception as e:
        print(f"Neco se posralo: {e}")
        return None
    finally:
        driver.quit()

def scrape_article_data(url):
    print(f"Scrapuju: {url}")
    content = vydridusi_bypass(url)
    soup = BeautifulSoup(content, 'html.parser')

    title = soup.select_one("h1[itemprop*=name]").text.strip() if soup.select_one("h1[itemprop*=name]") else None
    date = soup.select_one(".time-date").get("content") if soup.select_one(".time-date") else None

    gallery_count = soup.select_one(".more-gallery b")
    single_images = soup.find_all(class_='opener-foto')
    no_of_photos = gallery_count.text.strip() if gallery_count else len(single_images)

    category = soup.select_one("meta[name*='cXenseParse:qiw-rubrika']").get("content") if soup.select_one("meta[name*='cXenseParse:qiw-rubrika']") else None

    comment_element = soup.select_one(".community-discusion span")
    no_of_comments = re.sub("[^0-9]", "", comment_element.text) if comment_element else 0

    perex = soup.select_one(".opener").text.strip() if soup.select_one(".opener") else ""
    content = soup.select_one("#art-text").text.strip().encode('utf-8', 'ignore').decode("utf-8") if soup.select_one("#art-text") else ""

    return {
        "url": url,
        "title": title,
        "category": category,
        "content": perex + content,
        "no_of_photos": no_of_photos,
        "date": date,
        "no_of_comments": no_of_comments
    }

def scrape_articles(args):
    page_number, session_uuid = args
    url = f"https://www.idnes.cz/zpravy/archiv/{page_number}"
    page_content = vydridusi_bypass(url)

    if page_content:
        soup = BeautifulSoup(page_content, 'html.parser')
        articles = soup.select("#list-art-count .art")

        for article in articles:
            art_img_brisks = article.select_one(".art-img-brisks")
            if not (art_img_brisks and art_img_brisks.select_one(".premlab")):
                link_tag = article.select_one(".art-link")
                if link_tag and "idnes.cz" in link_tag.get("href"):
                    article_data = scrape_article_data(link_tag.get("href"))
                    save_article(article_data, session_uuid)

def main(max_size_mb):
    os.makedirs('data', exist_ok=True)
    session_uuid = str(uuid.uuid4())

    with Manager() as manager:
        page_numbers = range(1, 9999)
        pool = Pool(processes=os.cpu_count())

        while True:
            current_size_mb = get_data_size('data')
            print(f"Current size: {current_size_mb:.2f} MB")
            if current_size_mb >= max_size_mb:
                print(f"Mame hotovo: {current_size_mb:.2f} MB")
                break

            # Prepare arguments for each process
            args = [(page, session_uuid) for page in page_numbers]
            pool.map(scrape_articles, args)

        pool.close()
        pool.join()

if __name__ == "__main__":
    max_size_mb = 250
    main(max_size_mb)
