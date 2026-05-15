# gpt-image-2-prompts-cdn

Storage backend for the **GPT Image 2 Prompt Gallery** project. Each PNG under `case-images/` is a generated example for the corresponding prompt id in `prompts.json`.

## Public CDN

Images are served via [jsDelivr](https://www.jsdelivr.com/) for production-grade global delivery:

```
https://cdn.jsdelivr.net/gh/SHUJILAI/gpt-image-2-prompts-cdn@main/case-images/<slug>.png
```

For immutable references (recommended in JSON manifests), pin to a commit SHA:

```
https://cdn.jsdelivr.net/gh/SHUJILAI/gpt-image-2-prompts-cdn@<sha>/case-images/<slug>.png
```

## License

- Code & manifest: MIT
- Generated case images: provided as-is for reference; respect OpenAI's image-generation usage terms.
