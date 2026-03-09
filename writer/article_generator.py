"""
Article Generator  Uses Gemini to write SEO-optimized articles
from source material gathered by the source fetcher.
"""
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from gemini_client import generate_content_with_fallback
from writer.seo_prompt import build_article_prompt
from writer.source_fetcher import fetch_multiple_sources

logger = logging.getLogger(__name__)

RECIPE_ACF_KEYS = {
    "recipe_name",
    "recipe_description",
    "recipe_yield",
    "prep_time_minutes",
    "cook_time_minutes",
    "total_time_minutes",
    "ingredients",
    "instructions",
    "recipe_image",
    "nutrition_calories",
    "video_url",
    "author_name",
    "recipe_keywords",
    "recipecuisine",
    "recipecategory",
    "video_upload_date",
}

RECIPE_KEY_ALIASES = {
    "recipe_title": "recipe_name",
    "name": "recipe_name",
    "title": "recipe_name",
    "description": "recipe_description",
    "recipe_summary": "recipe_description",
    "summary": "recipe_description",
    "yield": "recipe_yield",
    "servings": "recipe_yield",
    "prep_time": "prep_time_minutes",
    "cook_time": "cook_time_minutes",
    "total_time": "total_time_minutes",
    "recipe_cuisine": "recipecuisine",
    "recipe_category": "recipecategory",
    "keywords": "recipe_keywords",
    "calories": "nutrition_calories",
    "image": "recipe_image",
    "image_url": "recipe_image",
    "video": "video_url",
    "video_date": "video_upload_date",
    "video_upload": "video_upload_date",
}


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

    if config.NEWS_API_KEY:
        try:
            from datetime import datetime, timedelta
            from newsapi import NewsApiClient

            newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
            from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
            results = newsapi.get_everything(
                q=keyword,
                language="en",
                sort_by="relevancy",
                from_param=from_date,
                page_size=5,
            )
            if results.get("status") == "ok":
                for article in results.get("articles", [])[:3]:
                    url = article.get("url")
                    if url and url not in urls:
                        urls.append(url)
        except Exception as e:
            logger.warning(f"Failed to fetch NewsAPI for trend: {e}")

    return urls


def _extract_faqpage_json(text):
    """Extract raw FAQPage JSON-LD from text using brace matching."""
    script_match = re.search(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if script_match:
        json_str = script_match.group(1).strip()
        if '"FAQPage"' in json_str or "'FAQPage'" in json_str:
            return json_str

    match = re.search(r'\{\s*["\']@context["\']', text)
    if not match:
        return None

    start = match.start()
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
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    return content


def _downgrade_h1_tags(content):
    """Ensure the article body does not contain an H1 because WordPress title is already the H1."""
    if not content:
        return content
    content = re.sub(r'<h1(\b[^>]*)?>', lambda m: f"<h2{m.group(1) or ''}>", content, flags=re.IGNORECASE)
    content = re.sub(r'</h1>', '</h2>', content, flags=re.IGNORECASE)
    return content


def _strip_code_fences(text):
    if not text:
        return text
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _canonical_recipe_key(key):
    normalized = re.sub(r'[^a-z0-9]+', '_', str(key).strip().lower()).strip('_')
    if normalized in RECIPE_ACF_KEYS:
        return normalized
    return RECIPE_KEY_ALIASES.get(normalized, normalized)


def _parse_minutes(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r'\d+', str(value))
    return int(match.group(0)) if match else ""


def _normalize_multiline_value(value):
    if value in (None, ""):
        return ""
    if isinstance(value, list):
        lines = []
        for item in value:
            item_text = str(item).strip()
            if item_text:
                lines.append(item_text)
        return "\n".join(lines)
    return str(value).strip()


def _normalize_recipe_fields(recipe_data):
    if not isinstance(recipe_data, dict):
        return {}

    normalized = {key: "" for key in RECIPE_ACF_KEYS}
    for raw_key, raw_value in recipe_data.items():
        key = _canonical_recipe_key(raw_key)
        if key not in RECIPE_ACF_KEYS:
            continue
        if key in {"ingredients", "instructions"}:
            normalized[key] = _normalize_multiline_value(raw_value)
        elif key in {"prep_time_minutes", "cook_time_minutes", "total_time_minutes"}:
            normalized[key] = _parse_minutes(raw_value)
        else:
            normalized[key] = str(raw_value).strip() if raw_value is not None else ""

    return {key: value for key, value in normalized.items() if value not in (None, "")}



def _merge_recipe_fields(*field_sets):
    merged = {}
    for field_set in field_sets:
        if not isinstance(field_set, dict):
            continue
        for key, value in field_set.items():
            if value not in (None, ""):
                merged[key] = value
    return merged


def _content_has_recipe_structure(content):
    text = _content_to_line_text(content)
    if not text:
        return False

    has_ingredients = bool(re.search(r'(?im)^(ingredients|ingredients list)\\s*:?\\s*$', text))
    has_instructions = bool(re.search(r'(?im)^(instructions|method|directions|preparation)\\s*:?\\s*$', text))
    return has_ingredients and has_instructions

def _is_recipe_article(result, intent=None):
    if (intent or "").lower() == "recipe":
        return True
    category = str(result.get("category", "")).strip().lower()
    slug = str(result.get("slug", "")).strip().lower()
    title = str(result.get("title", "")).strip().lower()
    tags = " ".join(result.get("tags", [])).lower()
    acf_fields = result.get("acf_fields", {}) or {}
    content = result.get("content", "") or result.get("full_content", "")
    recipe_markers = ["recipe", "how to make", "copycat", "homemade", "ingredients", "instructions"]

    return (
        category == "recipes"
        or "recipe" in slug
        or any(marker in title for marker in recipe_markers)
        or any(marker in tags for marker in recipe_markers)
        or bool(acf_fields.get("ingredients") or acf_fields.get("instructions"))
        or _content_has_recipe_structure(content)
    )

def _recipe_fields_complete(acf_fields):
    if not isinstance(acf_fields, dict):
        return False
    return bool(
        acf_fields.get("recipe_name")
        and acf_fields.get("recipe_description")
        and acf_fields.get("ingredients")
        and acf_fields.get("instructions")
    )


def _build_recipe_extraction_prompt(article):
    return f"""Extract recipe data from the article below and return only one raw JSON object with these exact keys:
recipe_name
recipe_description
recipe_yield
prep_time_minutes
cook_time_minutes
total_time_minutes
ingredients
instructions
recipe_image
nutrition_calories
video_url
author_name
recipe_keywords
recipecuisine
recipecategory
video_upload_date

Rules:
- No markdown fences.
- ingredients must be one ingredient per line in a single string.
- instructions must be one step per line in a single string.
- Use empty string for unknown optional values.
- prep_time_minutes, cook_time_minutes, and total_time_minutes must be numeric when known, otherwise empty string.
- Do not invent facts that are not in the article.

TITLE: {article.get('title', '')}
CATEGORY: {article.get('category', '')}
LANGUAGE: {article.get('language', 'en')}

ARTICLE:
{article.get('content', '')}
"""


def _extract_recipe_fields_via_fallback(article):
    try:
        prompt = _build_recipe_extraction_prompt(article)
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        recipe_json = _strip_code_fences(response.text)
        recipe_data = json.loads(recipe_json)
        normalized = _normalize_recipe_fields(recipe_data)
        if normalized:
            logger.info("   Recovered recipe ACF fields via fallback extraction")
        return normalized
    except Exception as e:
        logger.warning(f"   Failed fallback recipe extraction: {e}")
        return {}


def _strip_html_tags(html):
    if not html:
        return ""
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _extract_intro_text(content, max_words=120):
    plain = _strip_html_tags(content)
    if not plain:
        return ""
    words = plain.split()
    return " ".join(words[:max_words]).strip()


def _extract_heading_texts(content):
    if not content:
        return []
    headings = re.findall(r'<h[2-3][^>]*>(.*?)</h[2-3]>', content, flags=re.IGNORECASE | re.DOTALL)
    return [_strip_html_tags(item).strip() for item in headings if _strip_html_tags(item).strip()]


def _keyword_in_text(keyword, text):
    keyword = (keyword or '').strip().lower()
    text = (text or '').strip().lower()
    if not keyword or not text:
        return False
    return keyword in text


def _compute_keyword_density(keyword, content):
    keyword = (keyword or '').strip().lower()
    plain = _strip_html_tags(content).lower()
    if not keyword or not plain:
        return 0.0
    words = re.findall(r'\b\w+\b', plain)
    if not words:
        return 0.0
    occurrences = plain.count(keyword)
    return round((occurrences / len(words)) * 100, 2)


def _build_generation_checks(article, primary_keyword):
    focus_keyword = (primary_keyword or article.get('title', '')).strip()
    title = article.get('title', '')
    meta = article.get('meta_description', '')
    slug = article.get('slug', '')
    content = article.get('content', '')
    intro = _extract_intro_text(content)
    headings = _extract_heading_texts(content)
    density = _compute_keyword_density(focus_keyword, content)

    checks = {
        'focus_keyword': focus_keyword,
        'title_has_keyword': _keyword_in_text(focus_keyword, title),
        'meta_has_keyword': _keyword_in_text(focus_keyword, meta),
        'slug_has_keyword': _keyword_in_text(focus_keyword.replace(' ', '-'), slug),
        'intro_has_keyword': _keyword_in_text(focus_keyword, intro),
        'has_h2_or_h3': bool(headings),
        'h2_has_keyword': any(_keyword_in_text(focus_keyword, heading) for heading in headings),
        'title_length': len(title),
        'meta_length': len(meta),
        'keyword_density_percent': density,
    }

    warnings = []
    if focus_keyword and not checks['title_has_keyword']:
        warnings.append('Title is missing the focus keyword.')
    if focus_keyword and not checks['meta_has_keyword']:
        warnings.append('Meta description is missing the focus keyword.')
    if focus_keyword and not checks['slug_has_keyword']:
        warnings.append('Slug does not reflect the focus keyword.')
    if focus_keyword and not checks['intro_has_keyword']:
        warnings.append('Opening section does not mention the focus keyword early enough.')
    if not checks['has_h2_or_h3']:
        warnings.append('Article body is missing structured subheadings.')
    elif focus_keyword and not checks['h2_has_keyword']:
        warnings.append('No subheading includes the focus keyword.')
    if checks['title_length'] > 60:
        warnings.append('Title is longer than 60 characters.')
    if checks['meta_length'] < 140 or checks['meta_length'] > 160:
        warnings.append('Meta description is outside the 140-160 character target.')
    if density == 0:
        warnings.append('Focus keyword does not appear in the article body.')
    elif density > 1.5:
        warnings.append('Focus keyword density may be too high.')

    checks['warnings'] = warnings
    return checks


def _content_to_line_text(content):
    if not content:
        return ""
    text = re.sub(r'(?i)<br\s*/?>', "\n", content)
    text = re.sub(r'(?i)</(p|div|li|ul|ol|h2|h3|h4|h5|h6|section)>', "\n", text)
    text = re.sub(r'(?i)<li[^>]*>', "- ", text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\r\n?', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_named_section(text, section_names, stop_names):
    if not text:
        return ""
    start_pattern = "|".join(re.escape(name) for name in section_names)
    stop_pattern = "|".join(re.escape(name) for name in stop_names)
    pattern = rf'(?ims)^(?:{start_pattern})\s*:?\s*\n(.+?)(?=^(?:{stop_pattern})\s*:?[ \t]*$|\Z)'
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _normalize_recipe_lines(section_text):
    if not section_text:
        return ""
    lines = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub("^(?:[-*\\u2022]+|\\d+[\\.)])\\s*", '', line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _extract_recipe_description(content):
    plain = _strip_html_tags(content)
    if not plain:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', plain)
    return " ".join(sentence.strip() for sentence in sentences[:2] if sentence.strip())[:300].strip()


def _extract_recipe_fields_from_article(article):
    content = article.get('content', '')
    text = _content_to_line_text(content)
    ingredients_block = _extract_named_section(
        text,
        ['Ingredients'],
        ['Equipment', 'Instructions', 'Method', 'Directions', 'Practical Tips', 'Outlook', 'Frequently Asked Questions', 'FAQ', 'Post Tags'],
    )
    instructions_block = _extract_named_section(
        text,
        ['Instructions', 'Method', 'Directions'],
        ['Practical Tips', 'Outlook', 'Enjoy', 'Frequently Asked Questions', 'FAQ', 'Post Tags'],
    )

    ingredients = _normalize_recipe_lines(ingredients_block)
    instructions = _normalize_recipe_lines(instructions_block)
    if not ingredients or not instructions:
        return {}

    recipe_name = article.get('title', '').strip()
    fallback = {
        'recipe_name': recipe_name,
        'recipe_description': _extract_recipe_description(content),
        'ingredients': ingredients,
        'instructions': instructions,
        'recipe_keywords': ", ".join(article.get('tags', [])) if article.get('tags') else article.get('slug', '').replace('-', ', '),
        'recipecategory': 'Dessert',
        'recipecuisine': 'International',
    }
    return _normalize_recipe_fields(fallback)


def _parse_article_output(raw_text, intent=None):
    """Parse the structured output from Gemini into article components."""
    try:
        result = {}

        title_match = re.search(r'TITLE:\s*(.+?)(?:\n|META_DESCRIPTION:)', raw_text, re.DOTALL)
        result["title"] = title_match.group(1).strip() if title_match else ""

        meta_match = re.search(r'META_DESCRIPTION:\s*(.+?)(?:\n|SLUG:)', raw_text, re.DOTALL)
        result["meta_description"] = meta_match.group(1).strip() if meta_match else ""

        slug_match = re.search(r'SLUG:\s*(.+?)(?:\n|TAGS:)', raw_text, re.DOTALL)
        result["slug"] = slug_match.group(1).strip() if slug_match else ""

        tags_match = re.search(r'TAGS:\s*(.+?)(?:\n|CATEGORY:)', raw_text, re.DOTALL)
        if tags_match:
            tags_raw = tags_match.group(1).strip()
            result["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            result["tags"] = []

        cat_match = re.search(r'CATEGORY:\s*(.+?)(?:\n|LANGUAGE:)', raw_text, re.DOTALL)
        result["category"] = cat_match.group(1).strip() if cat_match else "Recipes"

        lang_match = re.search(r'LANGUAGE:\s*(en|fr)(?:\n|---)', raw_text, re.IGNORECASE | re.DOTALL)
        result["language"] = lang_match.group(1).strip().lower() if lang_match else "en"

        content_match = re.search(r'---CONTENT_START---(.*?)---CONTENT_END---', raw_text, re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""

        schema_json = _extract_faqpage_json(content)
        content = _strip_faq_and_schema_from_content(content)
        content = _downgrade_h1_tags(content)
        if schema_json:
            schema_block = (
                '<!-- wp:html -->\n'
                '<script type="application/ld+json">\n'
                + schema_json
                + '\n</script>\n'
                '<!-- /wp:html -->'
            )
            content = content.strip() + "\n\n" + schema_block

        result["content"] = content
        result["full_content"] = content
        result["faq_html"] = ""

        recipe_match = re.search(r'---RECIPE_DATA_START---\s*(.*?)\s*---RECIPE_DATA_END---', raw_text, re.DOTALL)
        result["acf_fields"] = {}
        if recipe_match:
            recipe_json_str = _strip_code_fences(recipe_match.group(1).strip())
            try:
                recipe_data = json.loads(recipe_json_str)
                result["acf_fields"] = _normalize_recipe_fields(recipe_data)
                if result["acf_fields"]:
                    logger.info(f"   Parsed ACF recipe fields: {list(result['acf_fields'].keys())}")
            except Exception as e:
                logger.warning(f"   Failed to parse RECIPE_DATA JSON: {e}")

        recipe_like = _is_recipe_article(result, intent=intent)
        if recipe_like and result.get("category", "").strip().lower() != "recipes":
            logger.info("   Recipe structure detected; normalizing category to Recipes")
            result["category"] = "Recipes"

        if not result["title"] or not result["content"]:
            logger.warning("Missing essential fields, attempting raw extraction...")
            if not result["title"]:
                first_line = raw_text.strip().split("\n")[0]
                result["title"] = re.sub(r'^#+\s*', '', first_line)[:60]
            if not result["content"]:
                result["content"] = _downgrade_h1_tags(raw_text)
                result["full_content"] = result["content"]

        if recipe_like and not _recipe_fields_complete(result["acf_fields"]):
            fallback_fields = _extract_recipe_fields_via_fallback(result)
            if fallback_fields:
                result["acf_fields"] = _merge_recipe_fields(result["acf_fields"], fallback_fields)

        if recipe_like and not _recipe_fields_complete(result["acf_fields"]):
            deterministic_fields = _extract_recipe_fields_from_article(result)
            if deterministic_fields:
                logger.info("   Recovered recipe ACF fields from article body structure")
                result["acf_fields"] = _merge_recipe_fields(result.get("acf_fields", {}), deterministic_fields)

        if recipe_like:
            acf_keys = sorted((result.get("acf_fields") or {}).keys())
            logger.info(f"   Recipe article detected with ACF keys: {acf_keys}")

        return result

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None


def generate_article(topic, source_urls=None):
    """
    Generate a complete SEO-optimized article for a trending topic.
    """
    logger.info(f" Generating article for: {topic.get('topic', 'Unknown')}")

    if source_urls is None:
        source_urls = []
        for story in topic.get("stories", []):
            url = story.get("url", "")
            if url and url.startswith("http"):
                source_urls.append(url)

    top_url = topic.get("top_url", "")
    if top_url and top_url not in source_urls:
        source_urls.insert(0, top_url)

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

    intent = _infer_intent(topic)
    prompt = build_article_prompt(
        topic_title=topic.get("topic", "Food & Recipe Update"),
        source_texts=source_texts,
        matched_keyword=topic.get("matched_keyword", ""),
        intent=intent,
    )

    try:
        logger.info("   Calling Gemini API...")
        response = generate_content_with_fallback(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        raw_output = response.text
        logger.info(f"   Gemini responded ({len(raw_output)} chars)")

    except Exception as e:
        logger.error(f"   Gemini API error: {e}")
        return None

    article = _parse_article_output(raw_output, intent=intent)

    if article:
        article["intent"] = intent
        article["sources_used"] = [s.get("source_domain", "") for s in source_texts]
        article["word_count"] = len(article.get("content", "").split())
        article["generation_checks"] = _build_generation_checks(
            article,
            topic.get("matched_keyword", "") or topic.get("topic", ""),
        )
        for warning in article["generation_checks"].get("warnings", []):
            logger.warning(f"   Content quality warning: {warning}")
        logger.info(f"   Article generated: '{article['title']}' ({article['word_count']} words)")
    else:
        logger.error("   Failed to parse Gemini output")

    return article





