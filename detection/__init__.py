from typing import List

from sources.youtube import SourceItem


def detect_new_items(raw_items: List[SourceItem]) -> List[SourceItem]:
    """Very simple detection placeholder.

    In the real app you will:
    - Check against a database / JSON state of already processed IDs
    - Apply rules for what counts as 'viral' or 'important'
    """
    return raw_items

