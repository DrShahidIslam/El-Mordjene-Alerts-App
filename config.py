"""
Central configuration for the El-Mordjene News Agent.
All settings, keywords, RSS feeds, and thresholds are defined here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY") or os.getenv("newsapi_key")

_gemini_keys_env = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in _gemini_keys_env.split(",") if k.strip()]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None

WP_URL = os.getenv("WP_BASE_URL", "https://el-mordjene.info").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
WP_PUBLISH_WEBHOOK_URL = os.getenv("WP_PUBLISH_WEBHOOK_URL", "").strip()
WP_PUBLISH_SECRET = os.getenv("WP_PUBLISH_SECRET", "").strip()

# YouTube Data API (optional — app works without it)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()

# ── RSS Feeds ─────────────────────────────────────────────────────────
# Food, recipe, and dessert blogs/news
RSS_FEEDS = {
    # Major food news & trends
    "Google News Food": "https://news.google.com/rss/search?q=viral+dessert+recipe+OR+dubai+chocolate+OR+homemade+chocolate&hl=en-US&gl=US&ceid=US:en",
    "Google News El Mordjene": "https://news.google.com/rss/search?q=el+mordjene+OR+mordjane+OR+cebon+spread&hl=en-US&gl=US&ceid=US:en",
    "Google News Candy": "https://news.google.com/rss/search?q=candy+making+OR+homemade+candy+OR+chocolate+recipe+2025&hl=en-US&gl=US&ceid=US:en",
    "Google News Food Bans": "https://news.google.com/rss/search?q=food+ban+OR+ingredient+banned+OR+snack+banned&hl=en-US&gl=US&ceid=US:en",
    "Google News TikTok Recipes": "https://news.google.com/rss/search?q=tiktok+recipe+viral+OR+tiktok+food+trend&hl=en-US&gl=US&ceid=US:en",
    # French/Algerian food news
    "Google News Algerian Food": "https://news.google.com/rss/search?q=recette+alg%C3%A9rienne+OR+p%C3%A2tisserie+alg%C3%A9rienne+OR+tamina&hl=fr&gl=FR&ceid=FR:fr",
    "Google News Mordjene FR": "https://news.google.com/rss/search?q=el+mordjene+OR+mordjane+OR+cebon&hl=fr&gl=DZ&ceid=DZ:fr",
    # Food safety & ingredient news
    "Google News Food Safety": "https://news.google.com/rss/search?q=food+safety+recall+OR+FDA+ban+OR+red+40+ban&hl=en-US&gl=US&ceid=US:en",
    # Chocolate & spreads
    "Google News Chocolate": "https://news.google.com/rss/search?q=chocolate+trend+OR+chocolate+recipe+OR+nutella+alternative&hl=en-US&gl=US&ceid=US:en",
}

# ── YouTube Search Queries ────────────────────────────────────────────
# Used to find trending recipe videos when YOUTUBE_API_KEY is set
YOUTUBE_SEARCH_QUERIES = [
    "el mordjene recipe",
    "dubai chocolate recipe",
    "viral dessert recipe 2025",
    "homemade chocolate recipe",
    "angel hair chocolate",
    "candy making at home",
    "french pastry recipe",
    "viral baking trends",
    "gourmet dessert recipe",
    "patisserie francaise recipe",
    "chocolate spread homemade",
    "food ban 2025",
]

# ── Keyword Watchlists ────────────────────────────────────────────────

# Core brand & product keywords
BRAND_KEYWORDS = [
    "el mordjene", "el-mordjene", "mordjene", "mordjane",
    "cebon", "cebon spread", "cebon algeria",
]

# Recipe & food trend keywords
RECIPE_KEYWORDS = [
    "dubai chocolate", "dubai chocolate bar", "dubai chocolate strawberries",
    "angel hair chocolate", "angel hair dessert", "kunafa chocolate",
    "viral dessert", "viral recipe", "viral dessert recipe",
    "tiktok recipe", "tiktok dessert", "tiktok food trend",
    "homemade chocolate", "chocolate recipe", "chocolate from scratch",
    "french pastry", "gourmet dessert", "baking trend", "viral baking",
    "chocolate truffles", "croissant recipe", "macaron recipe", "french dessert",
    "candy making", "homemade candy", "candy recipe",
    "chocolate spread", "homemade nutella", "nutella alternative",
    "kinder bueno spread", "kinder bueno recipe",
    "gourmet spread", "hazelnut spread",
    "homemade chocolate bars", "chocolate cookies recipe",
    "3 ingredient dessert", "no bake dessert", "easy dessert recipe",
]

# Algerian & cultural food keywords
CULTURAL_KEYWORDS = [
    "tamina", "tamina recipe", "algerian dessert",
    "algerian recipe", "algerian food", "algerian pastry",
    "makroud", "baklava recipe", "qalb el louz",
    "chebakia", "north african food", "maghreb cuisine",
    "recette algerienne", "patisserie algerienne",
]

# Food safety, bans, and health keywords
SAFETY_KEYWORDS = [
    "food ban", "ingredient ban", "snack banned",
    "red 40", "red dye 40", "food dye ban",
    "banned snacks", "banned in europe", "fda ban",
    "food recall", "food safety", "food additive",
    "banned ingredients", "american snacks banned",
    "titanium dioxide ban", "brominated vegetable oil",
]

# High-value trigger keywords (boost scoring when found)
HIGH_VALUE_KEYWORDS = [
    "viral", "banned", "recipe hack", "secret recipe",
    "3 ingredient", "no bake", "easy recipe",
    "million views", "trending", "gone viral",
    "copycat recipe", "dupe recipe", "healthier version",
    "calories", "ingredients list", "nutrition facts",
]

# Exclusion keywords — stories/trends containing these are discarded
EXCLUDE_KEYWORDS = [
    # Sports
    "world cup", "fifa", "football", "soccer", "cricket",
    "ipl", "nba", "nfl", "baseball", "tennis", "f1",
    "premier league", "champions league", "rugby",
    # Politics
    "election", "congress", "senate", "parliament",
    "president biden", "president trump", "political",
    # Unrelated tech
    "cryptocurrency", "bitcoin", "ethereum", "stock market",
    "artificial intelligence", "machine learning",
    # Entertainment (non-food)
    "movie review", "box office", "concert tour",
]

# Combined master keyword list (used for matching & filtering)
ALL_KEYWORDS = (
    BRAND_KEYWORDS + RECIPE_KEYWORDS +
    CULTURAL_KEYWORDS + SAFETY_KEYWORDS
)

# ── Seasonal Awareness ───────────────────────────────────────────────
# Month-based keyword boosts (score multiplier applied during detection)
SEASONAL_BOOSTS = {
    1: ["new year dessert", "winter chocolate", "healthy dessert"],
    2: ["valentine chocolate", "valentine dessert", "heart shaped"],
    3: ["ramadan dessert", "ramadan recipe", "iftar dessert", "spring recipe"],
    4: ["ramadan dessert", "eid dessert", "easter chocolate", "easter recipe"],
    5: ["eid dessert", "eid recipe", "mother's day", "spring dessert"],
    6: ["summer dessert", "no bake", "ice cream recipe", "frozen dessert"],
    7: ["summer dessert", "no bake", "ice cream", "popsicle recipe"],
    8: ["back to school snack", "lunchbox treat", "easy snack"],
    9: ["fall dessert", "pumpkin recipe", "autumn baking"],
    10: ["halloween candy", "halloween recipe", "spooky dessert", "pumpkin"],
    11: ["thanksgiving dessert", "pie recipe", "holiday baking"],
    12: ["christmas chocolate", "holiday dessert", "gift chocolate", "advent"],
}

# ── Detection Settings ────────────────────────────────────────────────
SPIKE_THRESHOLD = 1.8          # 1.8x above rolling average = spike
SPIKE_MIN_SCORE = 30           # Minimum spike score to trigger alert
ROLLING_WINDOW_HOURS = 24      # Baseline window for comparison
SCAN_INTERVAL_MINUTES = 60     # How often the agent scans
DEDUP_WINDOW_HOURS = 168       # Don't re-alert same story within 7 days

# ── Google Trends Settings ────────────────────────────────────────────
TRENDS_GEO = ""                # Worldwide (empty = global)
TRENDS_KEYWORDS_PER_BATCH = 5  # pytrends allows max 5 per request

# ── WordPress Settings ────────────────────────────────────────────────
WP_DEFAULT_CATEGORY = "Blog"
WP_DEFAULT_STATUS = "draft"    # 'draft', 'pending', or 'publish'

# ── Article Generation Settings ────────────────────────────────────────
ARTICLE_MIN_WORDS = 800
ARTICLE_MAX_WORDS = 1500
GEMINI_MODEL = "gemini-2.5-flash"
SKIP_AI_IMAGE = os.getenv("SKIP_AI_IMAGE", "false").lower() in ("true", "1", "yes")
USE_GEMINI_IMAGEN = os.getenv("USE_GEMINI_IMAGEN", "false").lower() in ("true", "1", "yes")

# ── Intelligent Features ──────────────────────────────────────────────
# Check existing site content to avoid duplicate topics
CHECK_EXISTING_CONTENT = True
# Max number of existing posts to check against
EXISTING_CONTENT_CHECK_LIMIT = 50
# Minimum Jaccard similarity to consider two topics as duplicates (0.0-1.0)
DUPLICATE_SIMILARITY_THRESHOLD = 0.4

# ── Logging ───────────────────────────────────────────────────────────
LOG_FILE = "agent.log"
LOG_LEVEL = "INFO"
