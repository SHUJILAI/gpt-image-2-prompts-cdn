#!/usr/bin/env python3
"""
backfill_new_fields.py — add 4 Manus-inspired fields to existing prompts.

Adds to each prompt in prompts.json (on assets branch):
  - usage_category   (marketing | content | business | personal)
  - primary_style    (realistic | illustration | 3d_render | anime |
                      pixel_art | minimal | vintage | cyberpunk | poster | sketch)
  - tagline_en       (one-sentence pitch, English)
  - tagline_zh       (一句话卖点，中文)

Then regenerates prompts-text.json + prompts-images.json (on main branch).

Workflow:
  1. checkout assets, mutate prompts.json, refresh indexes, commit & push assets
  2. extract split files (text + images), checkout main, write split files,
     commit & push main
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Reuse logic from publish_prompts.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish_prompts import (  # noqa: E402
    LOCAL_REPO,
    OUTPUTS_DIR,
    GH_REMOTE,
    GH_USER,
    GH_REPO,
    refresh_indexes,
    split_manifest_to_dicts,
    load_token,
    USAGE_CATEGORIES,
    PRIMARY_STYLES,
)

# Display category -> (usage_category, primary_style, tagline_en, tagline_zh)
CATEGORY_BACKFILL = {
    "Portraits": (
        "personal", "realistic",
        "Magazine-grade portrait for headshots, profiles, and lifestyle.",
        "杂志级人像，适合形象照、头像与生活方式内容。",
    ),
    "Product Photography": (
        "business", "realistic",
        "E-commerce-ready product shot with crisp lighting and clean composition.",
        "电商级产品图，光线干净、构图利落。",
    ),
    "Photo Editing": (
        "personal", "realistic",
        "Pro-grade photo enhancement and retouching for everyday photos.",
        "专业级修图与增强，让普通照片立刻提升一档。",
    ),
    "Fashion": (
        "marketing", "realistic",
        "Editorial fashion visual ready for campaigns and lookbooks.",
        "时尚编辑级视觉，可直接用于品牌活动与造型册。",
    ),
    "3D Render": (
        "business", "3d_render",
        "Production-grade 3D render for product, merch, or visualization.",
        "高品质 3D 渲染，适合产品、周边、可视化展示。",
    ),
    "Posters": (
        "marketing", "poster",
        "Eye-catching typographic poster for events and campaigns.",
        "视觉冲击力强的海报设计，适合活动与品牌投放。",
    ),
    "Style Transfer": (
        "personal", "illustration",
        "Transform any photo into a distinctive artistic style.",
        "把照片变成特定艺术风格的视觉转换。",
    ),
    "Creative": (
        "content", "illustration",
        "Imaginative visual for storytelling, content, or social posts.",
        "富有想象力的创意视觉，适合内容创作与社交分享。",
    ),
    "Viral / Social": (
        "content", "realistic",
        "Scroll-stopping visual designed to perform on social media.",
        "自带传播力的社交视觉，专为信息流投放设计。",
    ),
    "UI Mockups": (
        "business", "minimal",
        "Production-ready app or website screen for product showcases.",
        "高保真 App / 网页样机，可直接用于产品展示。",
    ),
    "Character Design": (
        "content", "illustration",
        "Original character concept ready for game, animation, or fiction.",
        "原创角色设定，可用于游戏、动画或小说。",
    ),
    "Illustrations": (
        "content", "illustration",
        "Distinctive illustrated artwork for editorial and content use.",
        "风格化插画，适合编辑用图与内容创作。",
    ),
}


def log(msg: str) -> None:
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.exit(
            f"ERROR: {' '.join(cmd)}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"
        )
    return res.stdout.strip()


def setup_repo(token: str) -> None:
    """Clone if missing, fetch latest, configure auth+identity."""
    auth = f"https://x-access-token:{token}@github.com/{GH_USER}/{GH_REPO}.git"
    if not LOCAL_REPO.exists():
        LOCAL_REPO.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", auth, str(LOCAL_REPO)])
    else:
        run(["git", "remote", "set-url", "origin", auth], cwd=LOCAL_REPO)
        run(["git", "fetch", "--quiet", "origin"], cwd=LOCAL_REPO)
    run(["git", "config", "user.email", "bot@happycapy.local"], cwd=LOCAL_REPO)
    run(["git", "config", "user.name",  "Capy Bot"], cwd=LOCAL_REPO)


def scrub_remote() -> None:
    if LOCAL_REPO.exists():
        try:
            run(["git", "remote", "set-url", "origin", GH_REMOTE], cwd=LOCAL_REPO)
        except SystemExit:
            pass


def backfill_entry(p: dict) -> tuple[bool, list[str]]:
    """Mutate p in-place. Return (changed, missing_fields)."""
    cat = p.get("category", "")
    mapping = CATEGORY_BACKFILL.get(cat)

    if not mapping:
        # Unknown category: fall back to defaults but still set fields so they exist
        log(f'  WARN: unknown category "{cat}" for id={p.get("id")} -> using defaults')
        usage, style, t_en, t_zh = ("content", "realistic", "", "")
    else:
        usage, style, t_en, t_zh = mapping

    changed = False
    if not p.get("usage_category"):
        p["usage_category"] = usage
        changed = True
    if not p.get("primary_style"):
        p["primary_style"] = style
        changed = True
    if "tagline_en" not in p:
        p["tagline_en"] = t_en
        changed = True
    if "tagline_zh" not in p:
        p["tagline_zh"] = t_zh
        changed = True

    # Validation
    missing = []
    if p["usage_category"] not in USAGE_CATEGORIES:
        missing.append(f"invalid usage_category={p['usage_category']}")
    if p["primary_style"] not in PRIMARY_STYLES:
        missing.append(f"invalid primary_style={p['primary_style']}")
    return changed, missing


def main() -> None:
    token = load_token()
    setup_repo(token)

    # ---- Stage 1: assets branch ----
    log("checkout assets")
    run(["git", "checkout", "--quiet", "assets"], cwd=LOCAL_REPO)
    run(["git", "reset", "--hard", "--quiet", "origin/assets"], cwd=LOCAL_REPO)

    manifest_path = LOCAL_REPO / "prompts.json"
    if not manifest_path.exists():
        sys.exit("ERROR: assets branch missing prompts.json")

    manifest = json.loads(manifest_path.read_text())
    log(f"loaded {len(manifest['prompts'])} prompts")

    changed_count = 0
    errors = []
    for p in manifest["prompts"]:
        changed, missing = backfill_entry(p)
        if changed:
            changed_count += 1
        if missing:
            errors.append((p.get("id"), missing))

    if errors:
        log("VALIDATION ERRORS:")
        for pid, ms in errors:
            log(f"  {pid}: {ms}")
        sys.exit("aborting due to validation errors")

    log(f"backfilled new fields on {changed_count}/{len(manifest['prompts'])} prompts")

    refresh_indexes(manifest)
    manifest["generated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    # Generate split files into the working tree (assets branch keeps full manifest;
    # we emit the split files here and copy them onto main below)
    pt, pi = split_manifest_to_dicts(manifest)
    pt_text = json.dumps(pt, indent=2, ensure_ascii=False) + "\n"
    pi_text = json.dumps(pi, indent=2, ensure_ascii=False) + "\n"

    # On assets, only commit prompts.json (split files belong on main)
    run(["git", "add", "prompts.json"], cwd=LOCAL_REPO)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=LOCAL_REPO
    ).returncode
    if diff != 0:
        run(
            ["git", "commit", "--quiet", "-m",
             "backfill: add usage_category / primary_style / tagline_en / tagline_zh + indexes"],
            cwd=LOCAL_REPO,
        )
        run(["git", "push", "--quiet", "origin", "assets"], cwd=LOCAL_REPO)
        log("pushed assets")
    else:
        log("assets already up-to-date")

    # ---- Stage 2: main branch ----
    log("checkout main")
    run(["git", "checkout", "--quiet", "main"], cwd=LOCAL_REPO)
    run(["git", "reset", "--hard", "--quiet", "origin/main"], cwd=LOCAL_REPO)

    (LOCAL_REPO / "prompts-text.json").write_text(pt_text)
    (LOCAL_REPO / "prompts-images.json").write_text(pi_text)

    run(["git", "add", "prompts-text.json", "prompts-images.json"], cwd=LOCAL_REPO)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=LOCAL_REPO
    ).returncode
    if diff != 0:
        run(
            ["git", "commit", "--quiet", "-m",
             "split: add usage_category / primary_style / tagline_en / tagline_zh"],
            cwd=LOCAL_REPO,
        )
        run(["git", "push", "--quiet", "origin", "main"], cwd=LOCAL_REPO)
        log("pushed main")
    else:
        log("main already up-to-date")

    # Mirror to outputs/
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "prompts-text.json").write_text(pt_text)
    (OUTPUTS_DIR / "prompts-images.json").write_text(pi_text)
    log("mirrored split files to outputs/")

    scrub_remote()
    log("DONE")


if __name__ == "__main__":
    main()
