#!/usr/bin/env python3
"""
Adapter: convert source gpt_image_2_prompts.json (TIANGE2211123/gpt-image-2-prompts:gpt-image-2-prompts)
into the internal YAML batch format expected by publish-prompts.

Input:  /tmp/tiange-source/gpt_image_2_prompts.json
Output: inputs/tiange-source-<n>.yaml
"""
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Need PyYAML: pip install pyyaml")

SRC = Path("/tmp/tiange-source/gpt_image_2_prompts.json")
OUT_DIR = Path(__file__).resolve().parent.parent / "inputs"

# Source category -> display category
CATEGORY_MAP = {
    "poster_typography": "Posters",
    "amateur_realistic": "Portraits",
    "photorealistic_portrait": "Portraits",
    "ui_mockup": "UI Mockups",
    "chinese_commercial": "Chinese Commercial",
    "illustration_style": "Illustrations",
    "product_photography": "Product Photography",
    "infographic_diagram": "Infographics",
    "game_screenshot": "Game / Screenshot",
    "ad_creative": "Advertising",
    "merch_collectible": "Merch / Collectibles",
    "comic_manga": "Comic / Manga",
    "logo_branding": "Logo / Branding",
}

SUBCATEGORY_MAP = {
    "poster_typography": "Typographic Poster",
    "amateur_realistic": "Amateur Realistic",
    "photorealistic_portrait": "Photorealistic Portrait",
    "ui_mockup": "UI Mockup",
    "chinese_commercial": "Chinese Commercial",
    "illustration_style": "Illustration Style",
    "product_photography": "Product Photography",
    "infographic_diagram": "Infographic / Diagram",
    "game_screenshot": "Game Screenshot",
    "ad_creative": "Ad Creative",
    "merch_collectible": "Merch / Collectible",
    "comic_manga": "Comic / Manga",
    "logo_branding": "Logo / Branding",
}

DIFFICULTY_MAP = {
    "poster_typography": "Intermediate",
    "amateur_realistic": "Beginner",
    "photorealistic_portrait": "Intermediate",
    "ui_mockup": "Advanced",
    "chinese_commercial": "Intermediate",
    "illustration_style": "Intermediate",
    "product_photography": "Beginner",
    "infographic_diagram": "Advanced",
    "game_screenshot": "Advanced",
    "ad_creative": "Intermediate",
    "merch_collectible": "Intermediate",
    "comic_manga": "Intermediate",
    "logo_branding": "Beginner",
}

# Source category -> top-level usage bucket (Manus-inspired)
USAGE_CATEGORY_MAP = {
    "poster_typography": "marketing",
    "amateur_realistic": "personal",
    "photorealistic_portrait": "personal",
    "ui_mockup": "business",
    "chinese_commercial": "marketing",
    "illustration_style": "content",
    "product_photography": "business",
    "infographic_diagram": "content",
    "game_screenshot": "personal",
    "ad_creative": "marketing",
    "merch_collectible": "business",
    "comic_manga": "content",
    "logo_branding": "business",
}

# Source category -> primary visual style (controlled enum)
PRIMARY_STYLE_MAP = {
    "poster_typography": "poster",
    "amateur_realistic": "realistic",
    "photorealistic_portrait": "realistic",
    "ui_mockup": "minimal",
    "chinese_commercial": "realistic",
    "illustration_style": "illustration",
    "product_photography": "realistic",
    "infographic_diagram": "illustration",
    "game_screenshot": "3d_render",
    "ad_creative": "realistic",
    "merch_collectible": "3d_render",
    "comic_manga": "anime",
    "logo_branding": "minimal",
}

# Source category -> short tagline templates (English / 中文)
TAGLINE_EN_MAP = {
    "poster_typography": "Eye-catching typographic poster ready for events, music, or campaigns.",
    "amateur_realistic": "Casual, lifestyle-style portrait with an authentic everyday feel.",
    "photorealistic_portrait": "Magazine-grade photorealistic portrait for headshots and editorial use.",
    "ui_mockup": "Production-ready app or website screen, perfect for product showcases.",
    "chinese_commercial": "Localized commercial visual tuned for Chinese market campaigns.",
    "illustration_style": "Distinctive illustrated artwork suitable for content and storytelling.",
    "product_photography": "E-commerce-ready product shot with crisp lighting and clean composition.",
    "infographic_diagram": "Clear, data-rich diagram that explains complex topics at a glance.",
    "game_screenshot": "Cinematic game-style scene for trailers, key art, or fan content.",
    "ad_creative": "Conversion-focused ad creative ready to drop into campaigns.",
    "merch_collectible": "Collectible product render ideal for merch listings and previews.",
    "comic_manga": "Manga-style frame for storyboards, fan art, or short comics.",
    "logo_branding": "Clean brand mark ready for logo systems and identity boards.",
}

TAGLINE_ZH_MAP = {
    "poster_typography": "适合活动、音乐、品牌活动的高视觉冲击海报。",
    "amateur_realistic": "贴近真实生活感的随手肖像，自然不做作。",
    "photorealistic_portrait": "杂志级写实人像，适合形象照与编辑用图。",
    "ui_mockup": "可直接用作产品展示的高保真 App / 网页样机。",
    "chinese_commercial": "面向中文市场的本土化商业视觉。",
    "illustration_style": "风格化插画，适合内容创作和讲故事。",
    "product_photography": "电商级产品图，光线干净、构图利落。",
    "infographic_diagram": "信息密度高、一眼读懂复杂主题的科普图。",
    "game_screenshot": "电影感游戏画面，可用于宣传、KV 或同人。",
    "ad_creative": "可直接投流的广告创意视觉。",
    "merch_collectible": "周边/手办级产品渲染图，适合商品展示。",
    "comic_manga": "漫画风格分镜，可用于脚本、同人或短篇。",
    "logo_branding": "干净的品牌符号，可直接用于 logo 系统与品牌板。",
}

# Normalize odd aspect ratios to one of the 7 supported by gpt-image-2 sizing
AR_NORMALIZE = {
    "1:1":     "1:1",
    "16:9":    "16:9",
    "9:16":    "9:16",
    "3:2":     "3:2",
    "2:3":     "2:3",
    "4:3":     "4:3",
    "3:4":     "3:4",
    # non-standard -> closest supported
    "4:5":     "3:4",
    "16:10":   "16:9",
    "2.35:1":  "16:9",
    "21:9":    "16:9",
    "9:19.5":  "9:16",
}


def slugify(s: str, maxlen: int = 60) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:maxlen].rstrip("-")


def adapt(src_data: dict) -> dict:
    out_prompts = []
    for p in src_data["prompts"]:
        raw_cat = p["category"]
        raw_ar = p["aspect_ratio"]
        if raw_ar not in AR_NORMALIZE:
            sys.exit(f"unmapped aspect_ratio: {raw_ar} (id {p['id']})")
        slug_title = slugify(p["title"])
        new_id = f"img2-{p['id']:02d}-{slug_title}"

        entry = {
            "id": new_id,
            "title": p["title"],
            "tagline_en": TAGLINE_EN_MAP.get(raw_cat, ""),
            "tagline_zh": TAGLINE_ZH_MAP.get(raw_cat, ""),
            "usage_category": USAGE_CATEGORY_MAP.get(raw_cat, "content"),
            "primary_style":  PRIMARY_STYLE_MAP.get(raw_cat, "realistic"),
            "category": CATEGORY_MAP.get(raw_cat, raw_cat.replace("_", " ").title()),
            "subcategory": SUBCATEGORY_MAP.get(raw_cat, raw_cat),
            "tags": list(dict.fromkeys((p.get("tags") or []) + [raw_cat, "gpt-image-2"])),
            "difficulty": DIFFICULTY_MAP.get(raw_cat, "Intermediate"),
            "aspect_ratio": AR_NORMALIZE[raw_ar],
            "prompt": p["prompt"],
            "negative_prompt": "",
            "style_keywords": p.get("tags") or [],
            "use_cases": [],
            "tip": f"Curated GPT Image 2 prompt (source aspect {raw_ar} normalized to {AR_NORMALIZE[raw_ar]} for generation).",
            "tip_zh": "精选 GPT Image 2 提示词；原宽高比已归一化到生成端支持的尺寸。",
            "author": "TIANGE2211123",
            "source_url": "https://github.com/TIANGE2211123/gpt-image-2-prompts/tree/gpt-image-2-prompts",
            "license": "Reference-only",
            "featured": False,
            "trending_score": 0.7,
        }
        out_prompts.append(entry)
    return {"prompts": out_prompts}


def main():
    if not SRC.exists():
        sys.exit(f"source missing: {SRC}")
    src_data = json.loads(SRC.read_text())
    out_data = adapt(src_data)
    n = len(out_data["prompts"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"tiange-source-{n}.yaml"
    with out_path.open("w") as f:
        yaml.safe_dump(
            out_data,
            f,
            allow_unicode=True,
            sort_keys=False,
            width=120,
            default_flow_style=False,
        )
    print(f"wrote {n} prompts -> {out_path}")
    print(f"first id: {out_data['prompts'][0]['id']}")
    print(f"last  id: {out_data['prompts'][-1]['id']}")


if __name__ == "__main__":
    main()
