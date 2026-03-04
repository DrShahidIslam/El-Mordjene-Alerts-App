from config import load_config
from sources import collect_sources
from detection import detect_new_items
from writer import generate_content
from publisher import publish_items
from notifications import send_notifications


def run_pipeline() -> None:
    """End-to-end run: sources -> detection -> writer -> publisher -> notifications."""
    config = load_config()

    raw_items = collect_sources()
    new_items = detect_new_items(raw_items)
    written_items = generate_content(new_items, config)
    published_items = publish_items(written_items, config)
    send_notifications(published_items, config)


if __name__ == "__main__":
    run_pipeline()

