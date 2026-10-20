import json
import os
import time
import requests
from bs4 import BeautifulSoup

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://discord.com/api/webhooks/1560949586758205490/0LVVn6YbNweum_EMIGTFr8J0cml5NeZUOl7vsmsNy5wiHgPR2fhmzPNeIwS1lMsfr2IB")  # Замените на ваш URL вебхука Discord
NEWS_URL = "https://deadlock.one/news"
CACHE_FILE = "last_sent_news.json"


def load_last_sent():
    """Загружаем ссылку последней отправленной новости"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_last_sent(url):
    """Сохраняем ссылку как последнюю отправленную"""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(url, f, ensure_ascii=False, indent=2)


def get_article_content(article_url):
    """Получаем текст статьи"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(article_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "Не удалось загрузить текст статьи."

        soup = BeautifulSoup(response.text, "html.parser")

        content_div = soup.find("div", class_="node-content") or soup.find("article") or soup.find("div",
                                                                                                   class_="content")

        if content_div:
            paragraphs = content_div.find_all(["p", "li", "h2", "h3"])
            text_lines = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            full_text = "\n".join(text_lines)
            return full_text
        else:
            return "Текст статьи найден, но структура отличается. Перейдите по ссылке."

    except Exception as e:
        return f"Ошибка при парсинге содержимого: {e}"


def split_text(text, max_length=1700):
    """Разбивает длинный текст на части по абзацам, чтобы не превышать лимиты Discord"""
    lines = text.split('\n')
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += (line + "\n")
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + "\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def check_latest_news():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(NEWS_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Ошибка получения страницы: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("a", href=True)

        latest_item = None

        # Ищем самую первую подходящую новость на странице
        for a in articles:
            href = a['href']
            if "/news/" in href or "/post/" in href:
                full_url = href if href.startswith("http") else f"https://deadlock.one{href}"
                title = a.get_text(strip=True)

                if title and full_url != "https://deadlock.one/news":
                    latest_item = {"title": title, "url": full_url}
                    break  # Первая в списке — самая свежая!

        if not latest_item:
            print("Новостей на странице не найдено.")
            return

        last_sent_url = load_last_sent()

        # Если эта новость еще не отправлялась
        if latest_item["url"] != last_sent_url:
            print(f"Найдена свежая новость: {latest_item['title']}")

            # Получаем текст статьи
            article_text = get_article_content(latest_item["url"])

            # Отправляем в Discord по частям
            send_to_discord_in_parts(latest_item["title"], latest_item["url"], article_text)

            # Запоминаем её как последнюю отправленную
            save_last_sent(latest_item["url"])
        else:
            print("Новых новостей пока нет.")

    except Exception as e:
        print(f"Ошибка при проверке новостей: {e}")


def send_to_discord_in_parts(title, url, text):
    # Делим текст на части
    chunks = split_text(text, max_length=1700)
    total_parts = len(chunks)

    for i, chunk in enumerate(chunks):
        part_num = i + 1

        # Если частей несколько, добавляем подпись к заголовку
        part_title = f"{title} (Часть {part_num} из {total_parts})" if total_parts > 1 else title

        payload = {
            "embeds": [
                {
                    "title": part_title,
                    "url": url if part_num == 1 else None,  # Ссылку крепим только к первой части
                    "description": chunk,
                    "color": 15418782,  # Оранжевый цвет
                    "footer": {
                        "text": f"Новости Deadlock • deadlock.one {f'({part_num}/{total_parts})' if total_parts > 1 else ''}"
                    }
                }
            ]
        }

        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code in [200, 204]:
            print(f"Успешно отправлена часть {part_num}/{total_parts}: {title}")
        else:
            print(f"Ошибка отправки части {part_num}: {response.status_code}, {response.text}")

        # Пауза в 1 секунду между отправкой частей, чтобы Discord не заблокировал за спам (Rate Limit)
        if part_num < total_parts:
            time.sleep(1)


if __name__ == "__main__":
    print("Бот запущен и проверяет последнюю новость (с разделением на части)...")
    while True:
        check_latest_news()
        time.sleep(900)  # Проверка каждые 15 минут
