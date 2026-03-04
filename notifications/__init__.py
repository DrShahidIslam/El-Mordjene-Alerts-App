from typing import List

import requests

from config import AppConfig


def send_notifications(published_items: List[dict], config: AppConfig) -> None:
    """Send simple Telegram messages for each published item."""
    if not published_items:
        return

    base_url = f"https://api.telegram.org/bot{config.telegram.bot_token}/sendMessage"
    for item in published_items:
        text = f"New on El-Mordjene: {item['title']}\n{item['url']}"
        payload = {
            "chat_id": config.telegram.channel_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        try:
            requests.post(base_url, json=payload, timeout=10)
        except Exception:
            # In MVP we ignore failures; later log them properly
            continue

