import os
import sys
import requests
from dotenv import load_dotenv
from crontab import CronTab

# Load environment variables FIRST
load_dotenv()

# Ensure the root project directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import invoke_kaia

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    """Sends the news summary to your Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n[Telegram] Token/ChatID missing. Skip kirim pesan.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    if len(text) > 4000:
        text = text[:3900] + "...\n\n*Pesan terlalu panjang.*"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("[Telegram] Berhasil! News update terkirim. 🚀")
        else:
            print(f"[Telegram] Error: {response.text}")
    except Exception as e:
        print(f"[Telegram] Failed to send message: {e}")

def run_daily_news():
    """Invokes Kaia to fetch and summarize news."""
    print("Kaia: Memulai crawling berita harian...")
    
    prompt = (
        "Berikan rangkuman berita hari ini tentang: "
        "1. Tech updates (AI, Go/PHP, Backend). "
        "2. Sepakbola (hasil pertandingan/transfer). "
        "3. Isu politik Indonesia (terutama terkait UUD atau regulasi yang berdampak)."
        "\n\nFormat output harus rapi dan siap dikirim via chat."
    )
    
    try:
        news_summary = invoke_kaia(user_input=prompt, chat_history=[])
        full_message = f"🌟 **Kaia Daily News Update** 🌟\n\n{news_summary}"
        send_telegram_message(full_message)
    except Exception as e:
        print(f"Error during news crawling: {e}")

def register_cronjob(hour: int = 8, minute: int = 0):
    """Register this script as a daily cronjob manually via --install flag."""
    os.environ["SKIP_MCP"] = "1"
    try:
        cron = CronTab(user=True)
        python_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "venv/bin/python3")
        script_path = os.path.abspath(__file__)
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/cron.log")
        
        command = f"{python_path} {script_path} >> {log_path} 2>&1"
        
        # Cleanup old jobs with same comment to prevent duplicates
        cron.remove_all(comment="Kaia Daily News")
        
        job = cron.new(command=command, comment="Kaia Daily News")
        job.setall(f"{minute} {hour} * * *")
        cron.write()
        print(f"[Cron] Registrasi berhasil! Jadwal: {hour:02d}:{minute:02d}.")
    except Exception as e:
        print(f"[Cron Error] Gagal mendaftarkan cron: {e}")

if __name__ == "__main__":
    if "--install" in sys.argv:
        register_cronjob()
    else:
        run_daily_news()
