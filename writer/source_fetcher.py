"""
Source Fetcher — Downloads and extracts clean text from news/blog article URLs.
Used to gather factual information before generating AI articles.
"""
import logging
import re
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BLOCKED_DOMAINS = {
    "trends.google.com",
    "www.google.com",
    "google.com",
    "youtube.com",
    "www.youtube.com",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_article_text(url, max_chars=3000):
    """
    Fetch and extract clean text from a news/blog article URL.
    Uses trafilatura as primary extractor, falls back to basic HTML parsing.
    """
    if not url:
        return None

    domain = urlparse(url).netloc.replace("www.", "")

    if domain in BLOCKED_DOMAINS or urlparse(url).netloc in BLOCKED_DOMAINS:
        logger.debug(f"  ⏭️ Skipping blocked domain: {domain}")
        return None

    # Try trafilatura first
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if text and len(text) > 200:
                metadata = trafilatura.extract_metadata(downloaded)
                title = metadata.title if metadata and metadata.title else ""

                return {
                    "title": title,
                    "text": text[:max_chars],
                    "source_domain": domain,
                    "url": url,
                    "method": "trafilatura",
                }
    except ImportError:
        logger.debug("trafilatura not installed, trying fallback")
    except Exception as e:
        logger.warning(f"trafilatura failed for {url}: {e}")

    # Fallback: basic requests + regex extraction
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text

        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)

        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', clean, flags=re.DOTALL | re.IGNORECASE)
        text_parts = []
        for p in paragraphs:
            text = re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 40:
                text_parts.append(text)

        full_text = "\n\n".join(text_parts)

        if full_text and len(full_text) > 200:
            return {
                "title": title,
                "text": full_text[:max_chars],
                "source_domain": domain,
                "url": url,
                "method": "fallback_regex",
            }

    except Exception as e:
        logger.warning(f"Fallback extraction failed for {url}: {e}")

    return None


def fetch_multiple_sources(urls, max_sources=5):
    """Fetch text from multiple source URLs."""
    sources = []

    for url in urls[:max_sources]:
        try:
            result = fetch_article_text(url)
            if result:
                sources.append(result)
                logger.info(f"  ✅ Extracted {len(result['text'])} chars from {result['source_domain']}")
            else:
                logger.warning(f"  ⚠️ Could not extract from: {url[:80]}")
        except Exception as e:
            logger.error(f"  ❌ Error fetching {url[:80]}: {e}")

    return sources
