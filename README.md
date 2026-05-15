# gpt-image-2-prompts-cdn

Deliverable for the **GPT Image 2 Prompt Gallery**.

The `main` branch contains exactly two files for downstream consumers:

| file | purpose |
| --- | --- |
| [`prompts-text.json`](./prompts-text.json) | id → prompt text + metadata (title, category, tags, tip, …) |
| [`prompts-images.json`](./prompts-images.json) | id → preview image URLs (SHA-pinned + branch-tracking + raw fallback) |

Both files use the same id keys, so a 1:1 join recovers the full record.

```js
// minimal merge example
const text   = await (await fetch('.../prompts-text.json')).json();
const images = await (await fetch('.../prompts-images.json')).json();
const merged = Object.fromEntries(
  Object.keys(text.items).map(id => [id, { ...text.items[id], ...images.items[id] }])
);
```

## Image URLs

Each entry in `prompts-images.json` carries three URLs:

- **`preview_image`** — jsDelivr, **SHA-pinned**, immutable. Use this in production.
- **`preview_image_latest`** — jsDelivr, tracks the `assets` branch (auto-follows updates).
- **`preview_image_raw`** — GitHub raw, SHA-pinned. Fallback only.

## Branch layout

- **`main`** — the deliverable (the two JSONs above + this README + LICENSE). Pulled by downstream.
- **`assets`** — image storage (`case-images/`), tooling (`bin/`), batch sources (`inputs/`), and the full per-prompt manifest (`prompts.json`).

## License

MIT for code & manifest. Generated case images are reference-only material; honor OpenAI's image-generation usage terms.
