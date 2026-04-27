import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Ensure the root project directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import invoke_kaia

load_dotenv()

# --- Configuration ---
# You can set these in your .env or directly here
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    """
    Sends the news summary to your Telegram bot.
    Requires 'requests' library.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n[Telegram] Token/ChatID missing. Printing to console instead:")
        return

    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("[Telegram] News summary sent successfully!")
    except Exception as e:
        print(f"[Telegram] Failed to send message: {e}")

def run_daily_news():
    """
    Invokes Kaia to fetch and summarize news, then sends it to the user.
    """
    print("Kaia: Memulai crawling berita harian untuk Faiz...")
    
    prompt = (
        "Berikan rangkuman berita hari ini tentang: "
        "1. Tech updates (AI, Go/PHP, Backend). "
        "2. Sepakbola (hasil pertandingan/transfer). "
        "3. Isu politik Indonesia (terutama terkait UUD atau regulasi yang berdampak)."
        "\n\nFormat output harus rapi dan siap dikirim via chat."
    )
    
    # We pass empty history since this is a fresh autonomous turn
    try:
        news_summary = invoke_kaia(user_input=prompt, chat_history=[])
        
        # Security check & formatting (optional, handled by clean_response in main.py)
        # For simple cron, we just send it.
        
        full_message = f"🌟 **Kaia Daily News Update** 🌟\n\n{news_summary}"
        
        print("\n--- Summary Result ---")
        print(full_message)
        
        send_telegram_message(full_message)
        
    except Exception as e:
        print(f"Error during news crawling: {e}")

if __name__ == "__main__":
    run_daily_news()
