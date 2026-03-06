"""
Article Generator  Uses Gemini to write SEO-optimized articles
from source material gathered by the source fetcher.
"""
import logging
import json
import re
import time

from google import genai

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from writer.source_fetcher import fetch_multiple_sources
from writer.seo_prompt import build_article_prompt
from gemini_client import generate_content_with_fallback

logger = logging.getLogger(__name__)

def _infer_intent(topic):
    """Infer content intent for better prompt shaping."""
    txt = f"{topic.get('topic', '')} {topic.get('matched_keyword', '')}".lower()

    if any(k in txt for k in ["recipe", "how to", "homemade", "ingredients", "make "]):
        return "recipe"
    if any(k in txt for k in ["where to buy", "buy", "price", "availability", "store", "amazon"]):
        return "buyer"
    if any(k in txt for k in ["ban", "recall", "news", "update", "lawsuit"]):
        return "news"
    if any(k in txt for k in ["trend", "rising", "viral", "tiktok", "spike"]):
        return "trend"
    return "explainer"


def _search_news_for_trend(keyword):
    """Search Google News RSS and NewsAPI to find background context for a trending keyword."""
    urls = []

    # 1. Google News RSS
    try:
        import feedparser
        import urllib.parse
        encoded_kw = urllib.parse.quote(keyword)
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
            if entry.link and entry.link not in urls:
                urls.append(entry.link)
    except Exception as e:
        logger.warning(f"Failed to fetch Google News RSS for trend: {e}")

    # 2. NewsAPI
    if config.NEWS_API_KEY:
        try:
            from newsapi import NewsApiClient
            from datetime import datetime, timedelta
            newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
            from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
            results = newsapi.get_everything(
                q=keyword,
                language="en",
                sort_by="relevancy",
                from_param=from_date,
                page_size=5
            )
            if results.get("status") == "ok":
                for article in results.get("articles", [])[:3]:
                    url = article.get("url")
                    if url and url not in urls:
                        urls.append(url)
        except Exception as e:
            logger.warning(f"Failed to fetch NewsAPI for trend: {e}")

    return urls


def generate_article(topic, source_urls=None):
    """
    Generate a complete SEO-optimized article for a trending topic.
    """
    logger.info(f" Generating article for: {topic.get('topic', 'Unknown')}")

    # Step 1: Gather source material
    if source_urls is None:
        source_urls = []
        for story in topic.get("stories", []):
            url = story.get("url", "")
            if url and url.startswith("http"):
                source_urls.append(url)

    top_url = topic.get("top_url", "")
    if top_url and top_url not in source_urls:
        source_urls.insert(0, top_url)

    # Check if this is a pure trend alert (only trends.google.com URLs)
    is_pure_trend = True
    if not source_urls:
        is_pure_trend = True
    else:
        for url in source_urls:
            if "trends.google.com" not in url:
                is_pure_trend = False
                break

    if is_pure_trend:
        keyword = topic.get("matched_keyword") or topic.get("topic", "").replace("Rising search:", "").strip()
        logger.info(f"   Pure trend detected. Searching active news for: '{keyword}'")
        found_urls = _search_news_for_trend(keyword)
        if found_urls:
            source_urls.extend(found_urls)
            logger.info(f"   Found {len(found_urls)} background articles for context.")

    logger.info(f"  Fetching {len(source_urls)} source URLs...")
    source_texts = fetch_multiple_sources(source_urls, max_sources=8)

    if not source_texts:
        logger.warning("   No source material could be extracted. Using topic summary only.")
        source_texts = [{
            "title": topic.get("topic", ""),
            "text": "\n".join(s.get("summary", "") for s in topic.get("stories", [])),
            "source_domain": "aggregated_summaries",
            "url": "",
        }]

    # Step 2: Build the prompt
    intent = _infer_intent(topic)
    prompt = build_article_prompt(
        topic_title=topic.get("topic", "Food & Recipe Update"),
        source_texts=source_texts,
        matched_keyword=topic.get("matched_keyword", ""),
        intent=intent
    )

    # Step 3: Call Gemini
    try:
        logger.info("   Calling Gemini API...")
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        raw_output = response.text
        logger.info(f"   Gemini responded ({len(raw_output)} chars)")

    except Exception as e:
        logger.error(f"   Gemini API error: {e}")
        return None

    # Step 4: Parse structured output
    article = _parse_article_output(raw_output)

    if article:
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article["word_count"] = len(article.get("content", "").split())
        logger.info(f"   Article generated: '{article['title']}' ({article['word_count']} words)")
    else:
        logger.error("   Failed to parse Gemini output")

    return article


def _extract_faqpage_json(text):
    """Extract raw FAQPage JSON-LD from text using brace matching."""
    for start_marker in ('{"@context"', '{ "@context"', "{'@context'"):
        start = text.find(start_marker)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        quote = None
        i = start
        while i < len(text):
            c = text[i]
            if escape:
                escape = False
                i += 1
                continue
            if c == '\\' and in_string:
                escape = True
                i += 1
                continue
            if in_string:
                if c == quote:
                    in_string = False
                i += 1
                continue
            if c in ('"', "'"):
                in_string = True
                quote = c
                i += 1
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1].strip()
            i += 1
    return None


def _strip_faq_and_schema_from_content(content):
    """Remove FAQ section and JSON-LD schema if the model wrongly put them inside CONTENT."""
    if not content:
        return content
    while True:
        json_str = _extract_faqpage_json(content)
        if not json_str:
            break
        content = content.replace(json_str, "", 1).strip()
    content = re.sub(
        r'<script\s+type=["\']application/ld\+json["\']\s*>.*?</script>\s*',
        '',
        content, flags=re.DOTALL | re.IGNORECASE
    )
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    return content


def _parse_article_output(raw_text):
    """Parse the structured output from Gemini into article components."""
    try:
        result = {}

        # Extract TITLE
        title_match = re.search(r'TITLE:\s*(.+?)(?:\n|META_DESCRIPTION:)', raw_text, re.DOTALL)
        result["title"] = title_match.group(1).strip() if title_match else ""

        # Extract META_DESCRIPTION
        meta_match = re.search(r'META_DESCRIPTION:\s*(.+?)(?:\n|SLUG:)', raw_text, re.DOTALL)
        result["meta_description"] = meta_match.group(1).strip() if meta_match else ""

        # Extract SLUG
        slug_match = re.search(r'SLUG:\s*(.+?)(?:\n|TAGS:)', raw_text, re.DOTALL)
        result["slug"] = slug_match.group(1).strip() if slug_match else ""

        # Extract TAGS
        tags_match = re.search(r'TAGS:\s*(.+?)(?:\n|CATEGORY:)', raw_text, re.DOTALL)
        if tags_match:
            tags_raw = tags_match.group(1).strip()
            result["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            result["tags"] = []

        # Extract CATEGORY
        cat_match = re.search(r'CATEGORY:\s*(.+?)(?:\n|LANGUAGE:)', raw_text, re.DOTALL)
        result["category"] = cat_match.group(1).strip() if cat_match else "Recipes"

        # Extract LANGUAGE
        lang_match = re.search(r'LANGUAGE:\s*(en|fr)(?:\n|---)', raw_text, re.IGNORECASE | re.DOTALL)
        result["language"] = lang_match.group(1).strip().lower() if lang_match else "en"

        # Extract CONTENT
        content_match = re.search(r'---CONTENT_START---(.*?)---CONTENT_END---', raw_text, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""

        # Post-process: ensure FAQ schema is in <script> tags
        schema_json = _extract_faqpage_json(content)
        content = _strip_faq_and_schema_from_content(content)
        if schema_json:
            schema_block = (
                '<!-- wp:html -->\n'
                '<script type="application/ld+json">\n'
                + schema_json +
                '\n</script>\n'
                '<!-- /wp:html -->'
            )
            content = content.strip() + "\n\n" + schema_block

        result["content"] = content
        result["full_content"] = content
        result["faq_html"] = ""

        # Extract RECIPE_DATA
        recipe_match = re.search(r'---RECIPE_DATA_START---\s*(.*?)\s*---RECIPE_DATA_END---', raw_text, re.DOTALL)
        result["acf_fields"] = {}
        if recipe_match:
            recipe_json_str = recipe_match.group(1).strip()
            
            # 1. Clean up potential markdown formatting around the JSON
            if recipe_json_str.startswith("```json"):
                recipe_json_str = recipe_json_str[7:].strip()
            elif recipe_json_str.startswith("```"):
                recipe_json_str = recipe_json_str[3:].strip()
                
            if recipe_json_str.endswith("```"):
                recipe_json_str = recipe_json_str[:-3].strip()

            # Try to parse it
            try:
                recipe_data = json.loads(recipe_json_str)
                if isinstance(recipe_data, dict) and recipe_data:
                    # Filter out empty fields if desired, but here we just attach it
                    result["acf_fields"] = recipe_data
                    logger.info(f"   Parsed ACF recipe fields: {list(recipe_data.keys())}")
            except Exception as e:
                logger.warning(f"   Failed to parse RECIPE_DATA JSON: {e}")

        # Validate essential fields
        if not result["title"] or not result["content"]:
            logger.warning("Missing essential fields, attempting raw extraction...")
            if not result["title"]:
                first_line = raw_text.strip().split("\n")[0]
                result["title"] = re.sub(r'^#+\s*', '', first_line)[:60]
            if not result["content"]:
                result["content"] = raw_text
                result["full_content"] = raw_text

        return result

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None



