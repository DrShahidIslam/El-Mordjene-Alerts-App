"""
El-Mordjene News Agent — Main orchestrator.
Complete pipeline: Sources → Detection → Writer → Publisher → Notifications.

Usage:
    python main.py              # Continuous loop (scan every SCAN_INTERVAL_MINUTES)
    python main.py --once       # Single scan cycle (for cron/GitHub Actions)
    python main.py --test       # Test all API connections
    python main.py --listen     # Listen-only mode (Telegram commands only)
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime

# Prevent UnicodeEncodeError when printing emojis to standard Windows consoles
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import config
from database.db import (
    get_connection, cleanup_old_data, save_topic_to_cache,
    get_topic_from_cache, record_notification, mark_notified,
    record_published_topic
)
from sources.rss_monitor import fetch_rss_stories
from sources.trends_monitor import fetch_trending_queries
from sources.youtube_monitor import fetch_youtube_videos
from sources.news_api_monitor import fetch_news_headlines
from detection.spike_detector import detect_spikes
from writer.article_generator import generate_article
from publisher.wordpress_client import (
    create_post, update_post_status, test_wordpress_connection,
    LAST_PUBLISH_ERROR
)
from publisher.image_handler import generate_featured_image
from notifications.telegram_bot import (
    send_trending_alert, send_simple_message, send_article_preview,
    send_publish_confirmation, send_generating_status, send_image_preview,
    send_pending_reminder, get_updates, answer_callback_query, test_connection
)

# ── Logging Setup ────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
    ]
)
logger = logging.getLogger("agent")

# ── Global State ─────────────────────────────────────────────────────
STATE_FILE = os.path.join(os.path.dirname(__file__), "agent_state.json")


def _load_state():
    """Load agent state from disk."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "pending_article": None,
        "pending_topic": None,
        "pending_image_paths": None,
        "last_scan": None,
        "scan_count": 0,
        "total_articles": 0,
        "telegram_offset": None,
    }


def _save_state(state):
    """Save agent state to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


# ──────────────────────────────────────────────────────────────────────
#                         SCAN PIPELINE
# ──────────────────────────────────────────────────────────────────────

def run_scan(state):
    """Execute the full scan → detect → alert pipeline."""
    logger.info("=" * 60)
    logger.info("🔍 Starting scan cycle...")
    logger.info("=" * 60)

    conn = get_connection()
    cleanup_old_data(conn)
    conn.close()

    # ── Step 1: Collect from all sources ──────────────────────────
    logger.info("📡 Phase 1: Collecting from sources...")
    all_stories = []
    trends_data = []

    # RSS Feeds
    try:
        rss_stories = fetch_rss_stories()
        all_stories.extend(rss_stories)
        logger.info(f"  RSS: {len(rss_stories)} stories")
    except Exception as e:
        logger.error(f"  RSS error: {e}")

    # YouTube
    try:
        yt_stories = fetch_youtube_videos()
        all_stories.extend(yt_stories)
        logger.info(f"  YouTube: {len(yt_stories)} videos")
    except Exception as e:
        logger.error(f"  YouTube error: {e}")

    # NewsAPI
    try:
        news_stories = fetch_news_headlines()
        all_stories.extend(news_stories)
        logger.info(f"  NewsAPI: {len(news_stories)} stories")
    except Exception as e:
        logger.error(f"  NewsAPI error: {e}")

    # Google Trends
    try:
        trends_data = fetch_trending_queries()
        logger.info(f"  Trends: {len(trends_data)} data points, "
                     f"{sum(1 for t in trends_data if t.get('is_rising'))} rising")
    except Exception as e:
        logger.error(f"  Trends error: {e}")

    logger.info(f"📊 Total raw stories: {len(all_stories)}")

    if not all_stories and not trends_data:
        logger.info("No stories or trends found this cycle.")
        state["last_scan"] = datetime.utcnow().isoformat()
        state["scan_count"] = state.get("scan_count", 0) + 1
        return []

    # ── Step 2: Detect spikes ─────────────────────────────────────
    logger.info("🔎 Phase 2: Detecting spikes...")
    trending_topics = detect_spikes(all_stories, trends_data)
    logger.info(f"🔥 Found {len(trending_topics)} trending topics")

    # ── Step 3: Send alerts ───────────────────────────────────────
    if trending_topics:
        logger.info("📢 Phase 3: Sending Telegram alerts...")
        conn = get_connection()
        for topic in trending_topics[:5]:
            # Cache topic for later article generation
            story_hash = None
            for s in topic.get("stories", []):
                story_hash = s.get("story_hash")
                if story_hash:
                    break
            if not story_hash:
                story_hash = hashlib.sha256(
                    topic["topic"].encode()
                ).hexdigest()[:16]

            topic["story_hash"] = story_hash
            save_topic_to_cache(conn, story_hash, topic)

            msg_id = send_trending_alert(topic)
            if msg_id:
                record_notification(conn, story_hash, msg_id)
                mark_notified(conn, story_hash)
                logger.info(f"  ✅ Alert sent: {topic['topic'][:60]}")
            else:
                logger.warning(f"  ⚠️ Alert failed: {topic['topic'][:60]}")

        conn.close()
    else:
        logger.info("No trending topics to alert about.")

    state["last_scan"] = datetime.utcnow().isoformat()
    state["scan_count"] = state.get("scan_count", 0) + 1

    return trending_topics


# ──────────────────────────────────────────────────────────────────────
#                      COMMAND HANDLING
# ──────────────────────────────────────────────────────────────────────

def poll_telegram_commands(state, timeout_seconds=60):
    """Poll Telegram for button presses and text commands."""
    logger.info(f"📡 Listening for Telegram commands ({timeout_seconds}s)...")
    start_time = time.time()
    offset = state.get("telegram_offset")

    while time.time() - start_time < timeout_seconds:
        try:
            updates = get_updates(offset=offset)

            for update in updates:
                offset = update["update_id"] + 1
                state["telegram_offset"] = offset

                # Handle callback queries (inline button presses)
                callback = update.get("callback_query")
                if callback:
                    _handle_callback(callback, state)
                    continue

                # Handle text messages
                message = update.get("message", {})
                text = message.get("text", "")

                if text.startswith("/status"):
                    _handle_status_command(state)
                elif text.startswith("/scan"):
                    send_simple_message("🔍 Starting manual scan...")
                    run_scan(state)
                elif text.startswith("/help"):
                    _handle_help_command()

        except Exception as e:
            logger.error(f"Telegram polling error: {e}")

        time.sleep(2)

    _save_state(state)


def _handle_callback(callback, state):
    """Handle inline button presses from Telegram."""
    data = callback.get("data", "")
    callback_id = callback.get("id", "")

    logger.info(f"  Button pressed: {data}")

    # Acknowledge the callback
    answer_callback_query(callback_id, "Processing...")

    # ── Generate Article ──────────────────────────────────────────
    if data.startswith("write_"):
        _handle_write_article(data, state)

    # ── Approve (save as draft) ───────────────────────────────────
    elif data == "approve":
        _handle_approve(state, status="draft")

    # ── Publish Live ──────────────────────────────────────────────
    elif data == "publish_live":
        _handle_approve(state, status="publish")

    # ── Reject ────────────────────────────────────────────────────
    elif data == "reject":
        state["pending_article"] = None
        state["pending_topic"] = None
        state["pending_image_paths"] = None
        _save_state(state)
        send_simple_message("🗑️ Article rejected and cleared.")

    # ── Ignore trending alert ─────────────────────────────────────
    elif data == "ignore":
        send_simple_message("👍 Ignored.")

    # ── Show pending article ──────────────────────────────────────
    elif data == "show_pending":
        if state.get("pending_article"):
            send_article_preview(state["pending_article"])
        else:
            send_simple_message("No pending article.")

    # ── Clear pending ─────────────────────────────────────────────
    elif data == "clear_pending":
        state["pending_article"] = None
        state["pending_topic"] = None
        state["pending_image_paths"] = None
        _save_state(state)
        send_simple_message("✅ Pending article cleared.")

    # ── Publish draft from Telegram ───────────────────────────────
    elif data.startswith("publish_draft_"):
        post_id = data.replace("publish_draft_", "")
        try:
            post_id = int(post_id)
            url = update_post_status(post_id, "publish")
            if url:
                send_simple_message(f"🚀 Post published live!\n{url}")
            else:
                send_simple_message(f"❌ Failed to publish post {post_id}")
        except Exception as e:
            send_simple_message(f"❌ Error publishing: {e}")


def _handle_write_article(data, state):
    """Handle the 'Generate Article' button press."""
    # Check if there's already a pending article
    if state.get("pending_article"):
        send_pending_reminder(state["pending_article"].get("title", "Unknown"))
        return

    # Find the topic from cache
    story_hash = data.replace("write_", "").replace("write_article", "")

    conn = get_connection()
    topic = get_topic_from_cache(conn, story_hash) if story_hash else None
    conn.close()

    if not topic:
        send_simple_message("⚠️ Topic data not found. It may have expired. Run a new scan first.")
        return

    # Send generating status
    send_generating_status(topic.get("topic", "Unknown topic"))

    # Generate the article
    try:
        article = generate_article(topic)
    except Exception as e:
        logger.error(f"Article generation error: {e}")
        send_simple_message(f"❌ Article generation failed: {str(e)[:200]}")
        return

    if not article:
        send_simple_message("❌ Article generation failed. Check logs for details.")
        return

    article["matched_keyword"] = topic.get("matched_keyword", "")

    # Generate featured image
    try:
        source_url = topic.get("top_url", "")
        webp_path, jpg_path = generate_featured_image(
            article["title"],
            source_url=source_url
        )
        if webp_path and jpg_path:
            state["pending_image_paths"] = {"webp": webp_path, "jpg": jpg_path}
            send_image_preview(jpg_path, article["title"])
        else:
            state["pending_image_paths"] = None
    except Exception as e:
        logger.warning(f"Image generation failed: {e}")
        state["pending_image_paths"] = None

    # Save pending article
    state["pending_article"] = article
    state["pending_topic"] = topic
    _save_state(state)

    # Send preview
    send_article_preview(article)


def _handle_approve(state, status="draft"):
    """Handle article approval (draft or publish)."""
    article = state.get("pending_article")
    if not article:
        send_simple_message("⚠️ No pending article to approve.")
        return

    # Get featured image path
    image_path = None
    image_paths = state.get("pending_image_paths")
    if image_paths:
        image_path = image_paths.get("jpg") or image_paths.get("webp")

    # Publish to WordPress
    send_simple_message(f"⏳ Publishing to WordPress as {status}...")

    try:
        result = create_post(article, featured_image_path=image_path, status=status)
    except Exception as e:
        send_simple_message(f"❌ Publish error: {e}")
        return

    if result:
        post_id = result.get("post_id")
        post_url = result.get("post_url", "")

        # Record in database
        conn = get_connection()
        record_published_topic(
            conn,
            article.get("title", ""),
            article.get("slug", ""),
            ",".join(article.get("tags", []))
        )
        conn.close()

        send_publish_confirmation(
            post_url, article["title"],
            post_id=post_id, status=status
        )

        state["total_articles"] = state.get("total_articles", 0) + 1
        state["pending_article"] = None
        state["pending_topic"] = None
        state["pending_image_paths"] = None
        _save_state(state)

        logger.info(f"✅ Article published: {article['title']} (ID: {post_id})")
    else:
        error_msg = LAST_PUBLISH_ERROR or "Unknown error"
        send_simple_message(f"❌ Publish failed: {error_msg}")


def _handle_status_command(state):
    """Send agent status summary."""
    lines = [
        f"📊 Scans completed: {state.get('scan_count', 0)}",
        f"📝 Articles published: {state.get('total_articles', 0)}",
        f"🕐 Last scan: {state.get('last_scan', 'Never')}",
        f"📌 Pending article: {'Yes' if state.get('pending_article') else 'No'}",
    ]
    if state.get("pending_article"):
        lines.append(f"   Title: {state['pending_article'].get('title', 'Unknown')}")
    send_simple_message("\n".join(lines))


def _handle_help_command():
    """Send help message."""
    help_text = """🤖 El-Mordjene Agent Commands:

/status — Show agent status
/scan — Trigger a manual scan
/help — Show this help message

Button actions:
✍️ Generate Article — Create article from trending topic
✅ Approve Draft — Save as WordPress draft
🚀 Publish Live — Publish immediately
🔄 Regenerate — Generate a new version
🗑️ Reject — Discard the article"""
    send_simple_message(help_text)


# ──────────────────────────────────────────────────────────────────────
#                         TEST MODE
# ──────────────────────────────────────────────────────────────────────

def test_connections():
    """Test all API connections."""
    print("\n" + "=" * 60)
    print("🔧 El-Mordjene Agent — Connection Test")
    print("=" * 60)

    results = {}

    # Telegram
    print("\n1️⃣  Telegram Bot...")
    ok, name = test_connection()
    results["telegram"] = ok
    if ok:
        print(f"   ✅ Connected: @{name}")
        mid = send_simple_message("🤖 El-Mordjene Agent connection test. All systems go!")
        if mid:
            print(f"   ✅ Test message sent (ID: {mid})")
        else:
            print("   ⚠️  Connected but couldn't send message. Check TELEGRAM_CHAT_ID.")
    else:
        print("   ❌ Failed. Check TELEGRAM_BOT_TOKEN.")

    # WordPress
    print("\n2️⃣  WordPress...")
    ok = test_wordpress_connection()
    results["wordpress"] = ok
    if ok:
        print("   ✅ Connected")
    else:
        print("   ❌ Failed. Check WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD.")

    # Gemini
    print("\n3️⃣  Gemini API...")
    try:
        from gemini_client import generate_content_with_fallback
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents="Reply with exactly: CONNECTED"
        )
        if "CONNECTED" in response.text.upper():
            print(f"   ✅ Connected (model: {config.GEMINI_MODEL})")
            results["gemini"] = True
        else:
            print(f"   ✅ Connected but unexpected response")
            results["gemini"] = True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        results["gemini"] = False

    # RSS Feeds
    print("\n4️⃣  RSS Feeds...")
    try:
        stories = fetch_rss_stories()
        print(f"   ✅ Fetched {len(stories)} stories from {len(config.RSS_FEEDS)} feeds")
        results["rss"] = True
        if stories:
            print(f"   📰 Sample: {stories[0]['title'][:80]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        results["rss"] = False

    # YouTube (optional)
    print("\n5️⃣  YouTube API...")
    if config.YOUTUBE_API_KEY:
        try:
            videos = fetch_youtube_videos()
            print(f"   ✅ Found {len(videos)} videos")
            results["youtube"] = True
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results["youtube"] = False
    else:
        print("   ⏭️  Skipped (no YOUTUBE_API_KEY configured)")
        results["youtube"] = None

    # NewsAPI (optional)
    print("\n6️⃣  NewsAPI...")
    if config.NEWS_API_KEY:
        try:
            headlines = fetch_news_headlines()
            print(f"   ✅ Found {len(headlines)} headlines")
            results["newsapi"] = True
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results["newsapi"] = False
    else:
        print("   ⏭️  Skipped (no NEWS_API_KEY configured)")
        results["newsapi"] = None

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    print(f"✅ {passed} passed | ❌ {failed} failed | ⏭️ {skipped} skipped")
    print("=" * 60 + "\n")

    return failed == 0


# ──────────────────────────────────────────────────────────────────────
#                           MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="El-Mordjene News Agent — Automated food trend detection and article generation"
    )
    parser.add_argument("--test", action="store_true", help="Test all API connections")
    parser.add_argument("--once", action="store_true", help="Single scan cycle (for cron/CI)")
    parser.add_argument("--listen", action="store_true", help="Listen-only mode (no scanning)")
    args = parser.parse_args()

    state = _load_state()

    if args.test:
        success = test_connections()
        sys.exit(0 if success else 1)

    if args.once:
        logger.info("Running single scan cycle (--once mode)")

        # Pre-scan: check for pending commands
        poll_telegram_commands(state, timeout_seconds=10)

        # Run scan
        topics = run_scan(state)

        # Post-scan: listen for button presses
        if topics:
            logger.info("Waiting for Telegram commands after scan...")
            poll_telegram_commands(state, timeout_seconds=420)

        _save_state(state)
        logger.info("Single scan complete. Exiting.")
        return

    if args.listen:
        logger.info("Listen-only mode (--listen). No scanning.")
        send_simple_message("🤖 El-Mordjene Agent is online (listen mode).")
        while True:
            try:
                poll_telegram_commands(state, timeout_seconds=300)
                _save_state(state)
            except KeyboardInterrupt:
                logger.info("Interrupted. Saving state and exiting.")
                _save_state(state)
                break

    # Default: continuous loop
    logger.info("=" * 60)
    logger.info("🚀 El-Mordjene Agent starting (continuous mode)")
    logger.info(f"   Scan interval: {config.SCAN_INTERVAL_MINUTES} minutes")
    logger.info("=" * 60)

    send_simple_message(
        f"🤖 El-Mordjene Agent is online!\n"
        f"Scanning every {config.SCAN_INTERVAL_MINUTES} min.\n"
        f"Use /help for commands."
    )

    while True:
        try:
            # Run scan
            run_scan(state)
            _save_state(state)

            # Listen for commands until next scan
            logger.info(f"⏰ Next scan in {config.SCAN_INTERVAL_MINUTES} minutes. Listening for commands...")
            poll_telegram_commands(state, timeout_seconds=config.SCAN_INTERVAL_MINUTES * 60)
            _save_state(state)

        except KeyboardInterrupt:
            logger.info("Interrupted. Saving state and exiting.")
            _save_state(state)
            send_simple_message("🤖 El-Mordjene Agent shutting down.")
            break
        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
