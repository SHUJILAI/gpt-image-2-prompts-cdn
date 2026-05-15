# gpt-image-2-prompts-cdn

Production-grade storage backend for the **GPT Image 2 Prompt Gallery**. Each PNG under
`case-images/` is a generated example for the corresponding prompt id in `prompts.json`.

- **Manifest**: [`prompts.json`](./prompts.json) — single source of truth for every prompt + its image URL
- **Images**: [`case-images/`](./case-images) — one PNG per prompt id
- **Tooling**: [`bin/`](./bin) — batch publish CLI (`publish-prompts`)
- **License**: code & manifest under MIT; rendered images are reference-only.

---

## Public CDN

Images are served via [jsDelivr](https://www.jsdelivr.com/) for global CDN delivery.

### Recommended for production: SHA-pinned (immutable)

```
https://cdn.jsdelivr.net/gh/SHUJILAI/gpt-image-2-prompts-cdn@<commit-sha>/case-images/<id>.png
```

Each entry in `prompts.json` carries a `preview_image` field already pinned to the
commit that introduced (or last updated) the image. URL never changes once published.

### Latest from main (auto-follows updates)

```
https://cdn.jsdelivr.net/gh/SHUJILAI/gpt-image-2-prompts-cdn@main/case-images/<id>.png
```

Stored in each entry as `preview_image_latest`.

### Fallback: GitHub raw

```
https://raw.githubusercontent.com/SHUJILAI/gpt-image-2-prompts-cdn/<commit-sha>/case-images/<id>.png
```

Stored in each entry as `preview_image_raw`. Use only if jsDelivr is unreachable.

---

## Manifest schema (per prompt)

```json
{
  "id": "lower-kebab-case-slug",
  "title": "Display title",
  "title_zh": "中文标题（可选）",
  "category": "Posters | Portraits | UI Mockups | Character Design | Product Photography | Illustrations | ...",
  "subcategory": "more specific bucket",
  "tags": ["tag1", "tag2"],
  "difficulty": "Beginner | Intermediate | Advanced",
  "model": "openai/gpt-image-2",
  "mode": "text-to-image | image-to-image",
  "language": "en",
  "aspect_ratio": "1:1 | 16:9 | 9:16 | 3:4 | 4:3 | 3:2 | 2:3",
  "prompt": "the actual prompt text...",
  "negative_prompt": "",
  "color_palette": ["#hex", "..."],
  "style_keywords": [],
  "use_cases": [],
  "tip": "advice for getting good results",
  "tip_zh": "中文提示",
  "author": "credit",
  "source_url": "where it came from",
  "license": "Reference-only | CC0 | MIT | ...",
  "featured": false,
  "trending_score": 0.5,
  "preview_image":         "<SHA-pinned jsDelivr URL>",
  "preview_image_latest":  "<main-tracking jsDelivr URL>",
  "preview_image_raw":     "<SHA-pinned GitHub raw URL>",
  "preview_image_pinned_sha": "<commit sha>"
}
```

---

## Publishing new prompts

The repo ships with a small Python CLI under `bin/` that handles the entire
publish flow: validate → generate image → commit → push → re-pin SHA → push.

### Setup

1. Clone this repo.
2. Have a GitHub PAT with `Contents: Read & Write` on this repo.
   - Save it to `~/.local/capy/github-pat` (or any path; export `GH_TOKEN_FILE`).
3. Set environment vars for image generation:
   - `AI_GATEWAY_BASE_URL` (OpenAI/OpenRouter-compatible base URL)
   - `AI_GATEWAY_API_KEY`

### Subcommands

```bash
bin/publish-prompts status                       # show repo HEAD + manifest stats
bin/publish-prompts pull                         # sync local mirror from origin
bin/publish-prompts batch  inputs/my-batch.yaml  # add many prompts at once (parallel image gen)
bin/publish-prompts add    inputs/single.yaml    # add one prompt
bin/publish-prompts remove <id> [<id>...]        # delete prompts (image + manifest entry)
```

Flags:
- `--force` — overwrite existing prompt id (re-generate or replace image)
- `--concurrency N` — parallel image generations for `batch` (default 5)

### Batch YAML format

See [`inputs/batch-template.yaml`](./inputs/batch-template.yaml). Minimum required
per entry: `id`, `title`, `category`, `prompt`. Everything else is optional.

To upload a pre-rendered image instead of generating one, set `image_path: ./path/to/file.png`.

### Workflow at scale (10–100 prompts/week)

1. Draft a YAML file in `inputs/`, e.g. `inputs/2026-05-w3.yaml`.
2. Run `bin/publish-prompts batch inputs/2026-05-w3.yaml --concurrency 5`.
3. The tool generates each image in parallel via gpt-image-2, commits everything
   in one batch, pushes, and re-pins all new entries to the resulting commit SHA.
4. Manifest is mirrored to the consumer workspace's `outputs/gpt-image-2-prompts.json`.

The whole pipeline is idempotent: re-running on the same YAML is a no-op (use
`--force` to overwrite).

---

## License

- Code, scripts, and manifest under MIT.
- Generated case images are provided as reference material; respect OpenAI's
  image-generation usage terms when reusing them in commercial products.
