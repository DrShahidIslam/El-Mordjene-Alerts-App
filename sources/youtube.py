from dataclasses import dataclass
from typing import List


@dataclass
class SourceItem:
    id: str
    title: str
    url: str
    channel: str
    published_at: str
    raw_data: dict


def fetch_youtube_candidates() -> List[SourceItem]:
    """Placeholder for YouTube discovery.

    For now this returns an empty list so the pipeline runs end-to-end.
    Later you can:
    - Call YouTube Data API with your API key
    - Or maintain a small manual JSON list of promising URLs
    """
    return []

