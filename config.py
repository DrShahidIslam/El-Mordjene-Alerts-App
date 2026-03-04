import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class WordPressConfig:
    base_url: str
    username: str
    application_password: str
    language: str = "en"


@dataclass
class TelegramConfig:
    bot_token: str
    channel_id: str


@dataclass
class AppConfig:
    wordpress: WordPressConfig
    telegram: TelegramConfig


def load_config() -> AppConfig:
    """Load configuration from environment variables.

    On GitHub Actions, these come from repository / environment secrets.
    """
    wp = WordPressConfig(
        base_url=os.environ["WP_BASE_URL"].rstrip("/"),
        username=os.environ["WP_USERNAME"],
        application_password=os.environ["WP_APP_PASSWORD"],
        language=os.environ.get("WP_LANGUAGE", "en"),
    )

    tg = TelegramConfig(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
    )

    return AppConfig(wordpress=wp, telegram=tg)

