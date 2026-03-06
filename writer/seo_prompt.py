"""
SEO Prompt Template — Master prompt for Gemini article generation.
Tailored for el-mordjene.info: food, recipes, chocolate, desserts, spreads.
"""

# Real internal links only — from existing published pages on el-mordjene.info
INTERNAL_LINKS = {
    "home": {"url": "https://el-mordjene.info/", "anchor": "El-Mordjene.info"},
    "what_is": {"url": "https://el-mordjene.info/what-is-el-mordjene/", "anchor": "What is El Mordjene?"},
    "banned": {"url": "https://el-mordjene.info/why-is-el-mordjene-banned/", "anchor": "Why is El Mordjene banned?"},
    "ingredients": {"url": "https://el-mordjene.info/el-mordjene-ingredients/", "anchor": "El Mordjene calories and ingredients"},
    "homemade_spread": {"url": "https://el-mordjene.info/how-to-make-el-mordjene-spread/", "anchor": "homemade El Mordjene spread recipe"},
    "cebon": {"url": "https://el-mordjene.info/cebon/", "anchor": "Cebon: the company behind El Mordjene"},
    "candy_making": {"url": "https://el-mordjene.info/candy-making-home/", "anchor": "candy making at home"},
    "dubai_strawberries": {"url": "https://el-mordjene.info/dubai-chocolate-strawberries/", "anchor": "Dubai Chocolate Strawberries recipe"},
    "chocolate_spread": {"url": "https://el-mordjene.info/chocolate-spread-recipes/", "anchor": "chocolate spread recipes from scratch"},
    "homemade_chocolate": {"url": "https://el-mordjene.info/homemade-chocolate-recipes/", "anchor": "homemade chocolate recipes"},
    "kinder_bueno": {"url": "https://el-mordjene.info/kinder-bueno-spread/", "anchor": "Kinder Bueno spread alternatives"},
    "tamina": {"url": "https://el-mordjene.info/tamina-algerian-postpartum-recipe/", "anchor": "Tamina: ancient Algerian superfood"},
    "banned_snacks": {"url": "https://el-mordjene.info/2027-banned-snacks-list-red-40-update/", "anchor": "banned snacks list and Red 40 update"},
    "american_snacks_banned": {"url": "https://el-mordjene.info/american-snacks-banned-in-europe/", "anchor": "American snacks banned in Europe"},
    "tiktok": {"url": "https://el-mordjene.info/el-mordjene-tiktok/", "anchor": "El Mordjene on TikTok"},
}


def build_article_prompt(topic_title, source_texts, matched_keyword=""):
    """
    Build the master SEO prompt for Gemini article generation.
    """
    sources_block = ""
    for i, src in enumerate(source_texts[:5], 1):
        sources_block += f"""
--- SOURCE {i} ({src.get('source_domain', 'Unknown')}) ---
{src.get('text', '')[:2000]}
"""

    links_suggestion = "\n".join([
        f"  - [{info['anchor']}]({info['url']})"
        for key, info in INTERNAL_LINKS.items()
    ])

    prompt = f"""You are an expert food journalist, recipe developer, and master of Semantic Search, AEO (Answer Engine Optimization), and GEO (Generative Engine Optimization) for el-mordjene.info.
Your articles must be engineered to rank instantly by providing high information density, clear entity relationships, and direct answers.

TASK: Write a complete, publish-ready article about the following trending food/recipe topic.

TRENDING TOPIC: {topic_title}
PRIMARY KEYWORD: {matched_keyword or topic_title}

─── SOURCE MATERIAL (use ONLY these facts, do NOT fabricate) ───
{sources_block}

─── ADVANCED OPTIMIZATION RULES (NON-NEGOTIABLE) ───

**1. KEYWORD DENSITY:** Ensure the primary keyword density is **strictly below 0.8%** in the paragraph text. Avoid keyword stuffing. Use synonyms and related entities instead.

**2. AEO & GEO OPTIMIZATION:**
- Use **Answer Language Processing (ALP)**: Provide direct, factual, and concise answers to the core questions implied by the topic.
- **Entity-Focused Writing**: Explicitly mention and connect key entities (ingredients, brands, regions, techniques). Use full names.
- Structure data for **Generative Search Engines**: Use clear, declarative sentences that are easy for AI models to parse and cite.
- **EEAT**: Demonstrate expert-level insight by synthesizing source facts into a cohesive, helpful narrative.

**3. LANGUAGE DETECTION & TRANSLATION:**
- If the primary topic, keyword, or source material is in French (like "recette algérienne" or "pâtisserie algérienne"), write the ENTIRE article in French.
- Otherwise, write the article in English.
- NEVER mix the languages within the content body (except for proper nouns).

**4. STYLE CONSTRAINTS:**
- **NO EMOJIS**: Strictly prohibited in the article body and headings.
- **NO DASHES**: Do not use dashes (—) for punctuation. Use commas, colons, or periods instead.
- **Short Paragraphs**: 2 sentences max per <p> tag to ensure high readability scores.
- **Warm & instructional tone**: Write like a passionate home chef sharing secrets with a friend, not a textbook.

**4. SCHEMA TAGS (CRITICAL):** The JSON-LD FAQ schema MUST be strictly wrapped in `<script type="application/ld+json">` and `</script>` tags. Without these tags, the schema will display visibly as text, which ruins the page layout. Do not forget the script tags!

─── ARTICLE STRUCTURE ───

1. TITLE: SEO-optimized, under 60 chars.
2. META_DESCRIPTION: 150-155 characters. Start with an action verb.
3. SLUG: Keyword-rich, lowercase, hyphens only.
4. ARTICLE BODY: Magazine-quality HTML (design details below).
5. FAQ: 3-4 schema-ready questions with food-specific, helpful answers.

**1. NO WORDPRESS BLOCK COMMENTS**: Do NOT output any `<!-- wp:... -->` comments. Produce strictly raw HTML.

**2. FOLLOW THIS EXACT HTML TEMPLATE** (Copy the structure and inline styles exactly):

<div class="wp-block-group" style="padding:1.5rem 2rem 2.5rem 2rem">

<h2 class="wp-block-heading">[Your Main Heading]</h2>
<p>[Engaging intro that hooks the reader with a question or surprising fact...]</p>
<p>[More text establishing context and why this matters now...]</p>

<div style="border-left: 4px solid #d4a574;padding: 1rem 1.25rem;margin: 1.5rem 0;border-radius: 0 8px 8px 0;background-color:#fdf6f0;color:#000000;">
<h3 style="margin: 0 0 0.75rem 0;font-size: 1.1rem;color:#000000;">Key Facts</h3>
<ul style="margin: 0;padding-left: 1.25rem;line-height: 1.6;color:#000000;">
<li>[Fact 1]</li>
<li>[Fact 2]</li>
<li>[Fact 3]</li>
</ul>
</div>

<h2>[Next Section Heading]</h2>
<p>[Section text... example internal link: <a href="https://el-mordjene.info/homemade-chocolate-recipes/">homemade chocolate recipes</a>...]</p>

<div style="padding: 1rem 1.25rem;margin: 1.5rem 0;border: 1px solid #d4a574;border-radius: 8px;background-color:#fdf6f0;color:#000000;">
<strong>Pro Tip:</strong> [A practical cooking tip, ingredient substitution, or time-saver related to the recipe/topic.]
</div>

<h2>[Another Section Heading]</h2>
<p>[Content...]</p>

<div style="display:block !important; padding:2rem !important; margin:2rem 0 !important; border-radius:12px !important; background:linear-gradient(135deg,#3d2b1f,#5c3d2e,#8b6914) !important; text-align:center !important; box-shadow:0 10px 20px rgba(0,0,0,0.15) !important; border-left:5px solid #d4a574 !important;">
<p style="font-size:1.5rem !important; font-weight:800 !important; margin:0 0 0.5rem 0 !important; text-transform:uppercase !important; letter-spacing:1px !important; color:#ffffff !important;">Explore More Recipes</p>
<p style="font-size:1.1rem !important; color:#f5e6d3 !important; font-weight:400 !important; margin:0 0 1rem 0 !important;">Discover viral desserts, homemade chocolate, and gourmet spreads</p>
<a href="https://el-mordjene.info/" style="display:inline-block !important; padding:0.75rem 2rem !important; background:#d4a574 !important; color:#ffffff !important; text-decoration:none !important; border-radius:8px !important; font-weight:700 !important; font-size:1rem !important; letter-spacing:0.5px !important;">Visit El-Mordjene.info &rarr;</a>
</div>

<h2>Frequently Asked Questions</h2>
<div style="margin: 1.5rem 0;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;">
<div style="padding: 1rem 1.25rem;background-color:#fdf6f0;">
<h3 style="margin: 0 0 0.5rem 0;font-size: 1.1rem;color:#000000;">[Question 1?]</h3>
<p style="margin: 0;color:#000000;">[Answer to Question 1.]</p>
</div>
</div>
<div style="margin: 1.5rem 0;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;">
<div style="padding: 1rem 1.25rem;background-color:#fdf6f0;">
<h3 style="margin: 0 0 0.5rem 0;font-size: 1.1rem;color:#000000;">[Question 2?]</h3>
<p style="margin: 0;color:#000000;">[Answer to Question 2.]</p>
</div>
</div>
<div style="margin: 1.5rem 0;border-radius: 8px;border:1px solid #ddd;overflow: hidden;color:#000000;">
<div style="padding: 1rem 1.25rem;background-color:#fdf6f0;">
<h3 style="margin: 0 0 0.5rem 0;font-size: 1.1rem;color:#000000;">[Question 3?]</h3>
<p style="margin: 0;color:#000000;">[Answer to Question 3.]</p>
</div>
</div>

<!-- CRITICAL: DO NOT FORGET THESE SCRIPT TAGS AROUND THE JSON! -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{
      "@type": "Question",
      "name": "[Question 1?]",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "[Answer to Question 1.]"
      }}
    }},
    {{
      "@type": "Question",
      "name": "[Question 2?]",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "[Answer to Question 2.]"
      }}
    }},
    {{
      "@type": "Question",
      "name": "[Question 3?]",
      "acceptedAnswer": {{
        "@type": "Answer",
        "text": "[Answer to Question 3.]"
      }}
    }}
  ]
}}
</script>
</div>

INTERNAL LINKING RULES (STRICT):
- ONLY use genuine links from the list below. Do NOT invent any internal URL.
- Include 2-3 genuine internal links, naturally placed where they fit the topic.
- Use the exact URL and suggested anchor text. Format: <a href="EXACT_URL">anchor text</a>

Allowed genuine internal links:
{links_suggestion}

EDITORIAL GUIDELINES:
- Tone: Warm, instructional, and passionate. Write like a beloved food blogger.
- Word count: 800-1500 words
- NEVER fabricate facts, recipes, nutritional data, or ingredient amounts.
- If sources conflict, mention both perspectives.
- Use short paragraphs (2-3 sentences max per paragraph).
- Include transition words for SEO readability.
- This site is an independent food resource, not affiliated with any brand.

RECIPE DATA REQUIREMENTS:
If the topic is a recipe (or if you generate a recipe within the article), you MUST extract the recipe details into a strict JSON format. 
If it is NOT a recipe, output an empty JSON object {{}}.
- "recipe_name": The name of the recipe (String).
- "recipe_description": Short 1-2 sentence summary for schema (String).
- "recipe_yield": e.g. "4 servings" (String).
- "prep_time_minutes": Numeric value in minutes (Number).
- "cook_time_minutes": Numeric value in minutes (Number).
- "total_time_minutes": Optional, or blank to auto-calc (String).
- "ingredients": One ingredient per line, separated by newlines within the string (String).
- "instructions": One step per line, separated by newlines within the string (String).
- "recipe_image": Leave empty, the system will populate this (String).
- "nutrition_calories": e.g. "120 kcal" (String).
- "video_url": ONLY include if the source material is from a YouTube video URL. Otherwise leave blank (String).
- "author_name": Optional (String).
- "recipe_keywords": Comma-separated keywords, e.g. "chocolate, dessert, viral" (String).
- "recipecuisine": e.g. "International", "French" (String).
- "recipecategory": e.g. "Dessert", "Chocolate" (String).
- "video_upload_date": ONLY include if there's a video URL, format YYYY-MM-DD. Otherwise leave blank. (String).

OUTPUT FORMAT:
Return your response in this exact structured format:

TITLE: [your title]
META_DESCRIPTION: [your meta description]
SLUG: [your-slug]
TAGS: [tag1, tag2, tag3, ...]
CATEGORY: [Choose the most appropriate single category: Recipes OR Food News OR Trends OR Sweets]
LANGUAGE: [en or fr]

---CONTENT_START---
[Generate the entire HTML structure exactly as specified in the HTML template above. CRITICAL: the FAQ JSON-LD schema at the end MUST be inside <script type="application/ld+json">...</script> tags! Output the RAW HTML directly without using ```html markdown tags!]
---CONTENT_END---

---RECIPE_DATA_START---
[Output the strict JSON object here containing recipe details, or {{}} if not a recipe. CRITICAL: Provide ONLY raw JSON text. DO NOT wrap the JSON in ```json or any other markdown formatting.]
---RECIPE_DATA_END---
"""

    return prompt


def build_image_prompt(topic_title, article_content_snippet=""):
    """Build a prompt for generating a food photography featured image."""
    prompt = f"""Generate a stunning, appetizing food photography image suitable for a professional food blog or culinary magazine like Bon Appetit or Tasty.

Context: This image is for a food article about: {topic_title}

CRITICAL INSTRUCTIONS:
- ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO NUMBERS, AND NO WATERMARKS anywhere in the image.
- DO NOT attempt to write the topic title or any keywords on the image.
- DO NOT include graphic design overlays, borders, or lower-thirds.

Style & Composition Guidelines:
- Professional food photography, overhead or 45-degree angle
- Warm, natural lighting with soft shadows (like golden hour or window light)
- Rich, vibrant colors that make food look irresistible
- Clean, styled background (marble, wood, linen, or rustic surfaces)
- Include garnishes, scattered ingredients, or utensils for visual interest
- 16:9 aspect ratio, landscape orientation
- The image should make the viewer hungry and inspired to cook

Exclusions:
- No recognizable brand logos or packaging
- No human faces (hands holding food are OK)
- No cluttered or messy backgrounds"""

    return prompt
