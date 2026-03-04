from .youtube import fetch_youtube_candidates


def collect_sources():
    """Collect raw candidate items from all configured sources.

    For MVP, only YouTube is wired. Later you can add:
    - TikTok / Instagram (manual queues or APIs)
    - RSS feeds from food blogs / news
    - Manual CSV / JSON seeding
    """
    items = []
    items.extend(fetch_youtube_candidates())
    return items

