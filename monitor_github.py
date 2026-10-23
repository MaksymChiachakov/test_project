import os
import json
import re
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CAREERS_URL = os.environ.get("BASICFIT_CAREERS_URL", "https://basicfit.wd103.myworkdayjobs.com/BasicFitCareers")
SEEN_JOBS_FILE = "seen_jobs.json"

def load_seen_jobs():
    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_jobs), f, ensure_ascii=False, indent=2)

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram не налаштовано.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Помилка відправки в Telegram: {e}")

def check_jobs_logic():
    print("Перевірка нових вакансій...")
    seen_jobs = load_seen_jobs()
    new_jobs_found = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(CAREERS_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_selector('a[data-automation-id="jobTitle"]', timeout=30000)
            job_links = page.query_selector_all('a[data-automation-id="jobTitle"]')
            
            for link in job_links:
                href = link.get_attribute("href")
                title = link.inner_text().strip()
                if not href: continue
                
                full_url = f"https://basicfit.wd103.myworkdayjobs.com{href}" if href.startswith("/") else href
                job_id_match = re.search(r'(_JR-\d+)', full_url)
                job_id = job_id_match.group(1) if job_id_match else full_url

                if job_id not in seen_jobs:
                    new_jobs_found = True
                    seen_jobs.add(job_id)
                    message = f"<b>Нова вакансія Basic-Fit!</b>\n\n<b>{title}</b>\n<a href='{full_url}'>Перейти до вакансії</a>"
                    print(f"Знайдено нову вакансію: {title}")
                    send_telegram_message(message)
        except Exception as e:
            print(f"Помилка під час перевірки: {e}")
        finally:
            browser.close()

    if new_jobs_found:
        save_seen_jobs(seen_jobs)
        print(f"Оновлено список. Всього: {len(seen_jobs)}")
    else:
        print("Нових вакансій не знайдено.")

if __name__ == "__main__":
    check_jobs_logic()