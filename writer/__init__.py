from dataclasses import dataclass
from typing import List

from config import AppConfig
from sources.youtube import SourceItem


@dataclass
class WrittenItem:
    source: SourceItem
    title: str
    slug: str
    excerpt: str
    body_html: str
    category: str


def generate_content(items: List[SourceItem], config: AppConfig) -> List[WrittenItem]:
    """Turn detected items into structured articles.

    For now this uses a very simple template. Later you can:
    - Call an LLM (Gemini/OpenAI) like the original repos do
    - Generate images
    - Localize for EN/FR
    """
    written: List[WrittenItem] = []
    for item in items:
        slug = item.id  # replace with a proper slug generator
        body = f"<p>Viral dessert: {item.title}</p><p>Source: <a href='{item.url}'>{item.channel}</a></p>"
        written.append(
            WrittenItem(
                source=item,
                title=item.title,
                slug=slug,
                excerpt=item.title,
                body_html=body,
                category="food-news",
            )
        )
    return written

