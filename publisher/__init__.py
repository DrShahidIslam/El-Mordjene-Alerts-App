from typing import List

from config import AppConfig
from writer import WrittenItem


def publish_items(items: List[WrittenItem], config: AppConfig) -> List[dict]:
    """Publish items to WordPress and return metadata for notifications.

    MVP: just echo back a minimal structure so notifications can be wired.
    Later:
    - Use requests to POST to WP REST API
    - Respect categories, RankMath fields, Polylang language, etc.
    """
    published = []
    for item in items:
        published.append(
            {
                "title": item.title,
                "url": f"{config.wordpress.base_url}/{item.slug}/",
                "category": item.category,
            }
        )
    return published

