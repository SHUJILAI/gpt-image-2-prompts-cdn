#!/usr/bin/env python3
"""
publish_prompts.py — batch-publish new GPT Image 2 prompts to the public CDN repo.

Usage:
  publish_prompts.py batch <input.yaml|input.json>   # add many at once
  publish_prompts.py add   <input.yaml|input.json>   # add one (single mapping)
  publish_prompts.py pull                            # sync local mirror from origin
  publish_prompts.py status                          # print repo + manifest stats

Repository (hard-coded for this project):
  GitHub:    SHUJILAI/gpt-image-2-prompts-cdn
  CDN:       https://cdn.jsdelivr.net/gh/SHUJILAI/gpt-image-2-prompts-cdn@<sha>/case-images/<id>.png

Environment:
  GH_TOKEN_FILE   path to file containing GitHub PAT (default: ~/.local/capy/github-pat)
  AI_GATEWAY_BASE_URL, AI_GATEWAY_API_KEY (auto-detected from env)

Batch input schema (YAML or JSON):
  prompts:
    - id: my-prompt-slug          # required, lower-kebab-case
      title: ...                   # required
      title_zh: ...                # optional
      category: Posters            # required
      subcategory: Travel Poster   # optional
      tags: [poster, travel]       # optional
      difficulty: Intermediate     # Beginner|Intermediate|Advanced
      aspect_ratio: "3:4"          # one of 1:1, 16:9, 9:16, 3:4, 4:3, 3:2, 2:3
      prompt: |                    # required
        ...
      negative_prompt: ""          # optional
      color_palette: [...]
      style_keywords: [...]
      use_cases: [...]
      tip: ...
      tip_zh: ...
      author: ...
      source_url: ...
      license: CC0
      featured: false
      trending_score: 0.5
      image_path: null             # optional; if set, skip generation and upload local file
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, shutil, time, hashlib, urllib.request, base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/home/node/a0/workspace/983afd77-d2b2-4376-a1c4-710d52d310ec/workspace')
LOCAL_REPO = WORKSPACE / 'tmp' / 'repo'
OUTPUTS_DIR = WORKSPACE / 'outputs'
OUTPUTS_JSON = OUTPUTS_DIR / 'gpt-image-2-prompts.json'
OUTPUTS_IMAGES = OUTPUTS_DIR / 'case-images'

GH_USER = 'SHUJILAI'
GH_REPO = 'gpt-image-2-prompts-cdn'
GH_REMOTE = f'https://github.com/{GH_USER}/{GH_REPO}.git'

DEFAULT_TOKEN_FILE = Path.home() / '.local' / 'capy' / 'github-pat'

ASPECT_TO_SIZE = {
    '1:1':  '1024x1024',
    '16:9': '1536x1024',
    '9:16': '1024x1536',
    '3:2':  '1536x1024',
    '2:3':  '1024x1536',
    '4:3':  '1536x1024',
    '3:4':  '1024x1536',
}

REQUIRED_FIELDS = ['id', 'title', 'category', 'prompt']

# ---------- utilities ----------

def log(msg: str) -> None:
    print(f'[{datetime.utcnow().strftime("%H:%M:%S")}] {msg}', flush=True)

def load_token() -> str:
    p = Path(os.environ.get('GH_TOKEN_FILE', DEFAULT_TOKEN_FILE))
    if not p.exists():
        sys.exit(f'ERROR: GitHub PAT not found at {p}. Set GH_TOKEN_FILE or place a token there.')
    return p.read_text().strip()

def load_input(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f'ERROR: input file not found: {path}')
    text = p.read_text()
    if p.suffix.lower() in ('.yaml', '.yml'):
        try:
            import yaml  # type: ignore
        except ImportError:
            sys.exit('ERROR: install PyYAML: pip install pyyaml')
        return yaml.safe_load(text)
    return json.loads(text)

def run(cmd: list[str], cwd: Path | None = None, check: bool = True, env: dict | None = None) -> str:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if check and res.returncode != 0:
        sys.exit(f'ERROR: {" ".join(cmd)}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}')
    return res.stdout.strip()

# ---------- repo management ----------

def ensure_repo(token: str) -> None:
    """Clone if missing, pull if present. Set authenticated remote."""
    auth_url = f'https://x-access-token:{token}@github.com/{GH_USER}/{GH_REPO}.git'
    if not LOCAL_REPO.exists():
        log(f'Cloning {GH_USER}/{GH_REPO} into {LOCAL_REPO}')
        LOCAL_REPO.parent.mkdir(parents=True, exist_ok=True)
        run(['git', 'clone', '--quiet', auth_url, str(LOCAL_REPO)])
    else:
        run(['git', 'remote', 'set-url', 'origin', auth_url], cwd=LOCAL_REPO)
        run(['git', 'fetch', '--quiet', 'origin'], cwd=LOCAL_REPO)
        run(['git', 'checkout', '--quiet', 'main'], cwd=LOCAL_REPO)
        run(['git', 'reset', '--hard', '--quiet', 'origin/main'], cwd=LOCAL_REPO)
    # Configure identity
    run(['git', 'config', 'user.email', 'bot@happycapy.local'], cwd=LOCAL_REPO)
    run(['git', 'config', 'user.name',  'Capy Bot'], cwd=LOCAL_REPO)

def scrub_remote() -> None:
    """Remove token from remote URL."""
    if LOCAL_REPO.exists():
        try:
            run(['git', 'remote', 'set-url', 'origin', GH_REMOTE], cwd=LOCAL_REPO)
        except SystemExit:
            pass

def current_sha() -> str:
    return run(['git', 'rev-parse', 'HEAD'], cwd=LOCAL_REPO)

def push() -> str:
    run(['git', 'push', '--quiet', 'origin', 'main'], cwd=LOCAL_REPO)
    return current_sha()

# ---------- manifest ----------

def load_manifest() -> dict:
    p = LOCAL_REPO / 'prompts.json'
    return json.loads(p.read_text()) if p.exists() else {
        'schema_version': '1.2',
        'name': 'GPT Image 2 Prompt Gallery',
        'prompts': [],
    }

def save_manifest(m: dict) -> None:
    m['generated_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    (LOCAL_REPO / 'prompts.json').write_text(json.dumps(m, indent=2, ensure_ascii=False) + '\n')

def index_by_id(manifest: dict) -> dict:
    return {p['id']: p for p in manifest.get('prompts', [])}

def make_urls(slug: str, sha: str) -> dict:
    return {
        'preview_image':         f'https://cdn.jsdelivr.net/gh/{GH_USER}/{GH_REPO}@{sha}/case-images/{slug}.png',
        'preview_image_latest':  f'https://cdn.jsdelivr.net/gh/{GH_USER}/{GH_REPO}@main/case-images/{slug}.png',
        'preview_image_raw':     f'https://raw.githubusercontent.com/{GH_USER}/{GH_REPO}/{sha}/case-images/{slug}.png',
        'preview_image_pinned_sha': sha,
    }

# ---------- image generation ----------

def gen_image(prompt: str, size: str, out: Path, max_retries: int = 3) -> None:
    base = os.environ.get('AI_GATEWAY_BASE_URL')
    key  = os.environ.get('AI_GATEWAY_API_KEY')
    if not base or not key:
        sys.exit('ERROR: AI_GATEWAY_BASE_URL / AI_GATEWAY_API_KEY not set in env')
    url = f'{base.rstrip("/")}/api/v1/images/generations'
    body = json.dumps({
        'model':  'openai/gpt-image-2',
        'prompt': prompt,
        'size':   size,
        'n':      1,
    }).encode()
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={
                    'Authorization': f'Bearer {key}',
                    'Content-Type':  'application/json',
                    'Accept':        'application/json',
                    'User-Agent':    'capy-publish-prompts/1.0',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            item = data['data'][0]
            if 'url' in item:
                req2 = urllib.request.Request(item['url'], headers={'User-Agent': 'capy-publish-prompts/1.0'})
                with urllib.request.urlopen(req2, timeout=120) as r2:
                    out.write_bytes(r2.read())
            elif 'b64_json' in item:
                out.write_bytes(base64.b64decode(item['b64_json']))
            else:
                raise RuntimeError(f'unexpected response: {data}')
            return
        except Exception as e:
            last_err = e
            log(f'  gen retry {attempt}/{max_retries} for {out.name}: {e}')
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f'image generation failed after {max_retries} attempts: {last_err}')

# ---------- core operations ----------

def normalize_entry(e: dict) -> dict:
    """Validate & fill defaults."""
    for f in REQUIRED_FIELDS:
        if not e.get(f):
            sys.exit(f'ERROR: prompt missing required field "{f}": {json.dumps(e, ensure_ascii=False)[:200]}')
    e.setdefault('aspect_ratio', '1:1')
    if e['aspect_ratio'] not in ASPECT_TO_SIZE:
        sys.exit(f'ERROR: unsupported aspect_ratio: {e["aspect_ratio"]}')
    e.setdefault('language', 'en')
    e.setdefault('mode', 'text-to-image')
    e.setdefault('model', 'openai/gpt-image-2')
    e.setdefault('tags', [])
    e.setdefault('difficulty', 'Intermediate')
    e.setdefault('license', 'Reference-only')
    e.setdefault('featured', False)
    return e

def cmd_pull() -> None:
    ensure_repo(load_token())
    log(f'pulled, HEAD={current_sha()}')
    scrub_remote()

def cmd_status() -> None:
    ensure_repo(load_token())
    m = load_manifest()
    log(f'repo  HEAD={current_sha()}')
    log(f'manifest prompts: {len(m.get("prompts", []))}')
    cats = {}
    for p in m.get('prompts', []):
        cats[p.get('category', '?')] = cats.get(p.get('category', '?'), 0) + 1
    log(f'categories: {cats}')
    scrub_remote()

def add_prompts(entries: list[dict], force: bool = False, concurrency: int = 5) -> dict:
    token = load_token()
    ensure_repo(token)
    manifest = load_manifest()
    by_id = index_by_id(manifest)

    # 1) validate + dedup
    to_add = []
    for raw in entries:
        e = normalize_entry(dict(raw))
        if e['id'] in by_id and not force:
            log(f'  SKIP existing id "{e["id"]}" (use --force to overwrite)')
            continue
        to_add.append(e)
    if not to_add:
        log('nothing to add.')
        scrub_remote()
        return {'added': 0, 'sha': current_sha()}

    log(f'preparing {len(to_add)} new prompt(s)')

    # 2) generate / copy images in parallel
    case_dir = LOCAL_REPO / 'case-images'
    case_dir.mkdir(exist_ok=True)
    OUTPUTS_IMAGES.mkdir(parents=True, exist_ok=True)

    def fetch_image(e: dict) -> tuple[str, Exception | None]:
        slug = e['id']
        out = case_dir / f'{slug}.png'
        try:
            if e.get('image_path'):
                src = Path(e['image_path'])
                if not src.exists():
                    raise FileNotFoundError(f'image_path not found: {src}')
                shutil.copyfile(src, out)
                log(f'  COPIED  {slug}  <-  {src}')
            else:
                size = ASPECT_TO_SIZE[e['aspect_ratio']]
                gen_image(e['prompt'], size, out)
                log(f'  GEN OK  {slug}  ({size})')
            # mirror to outputs/case-images/ for local preview
            shutil.copyfile(out, OUTPUTS_IMAGES / f'{slug}.png')
            return slug, None
        except Exception as ex:
            return slug, ex

    failures = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for slug, err in ex.map(fetch_image, to_add):
            if err:
                failures.append((slug, str(err)))

    if failures:
        log(f'WARNING: {len(failures)} image(s) failed:')
        for s, e in failures:
            log(f'  - {s}: {e}')
        # remove failed entries
        to_add = [e for e in to_add if e['id'] not in {s for s, _ in failures}]
        if not to_add:
            sys.exit('all images failed; aborting.')

    # 3) append/replace entries (without URLs yet, will inject post-push)
    for e in to_add:
        # remove any prior copy
        manifest['prompts'] = [p for p in manifest['prompts'] if p['id'] != e['id']]
        # placeholder URLs (overwritten after push)
        e.update(make_urls(e['id'], 'PENDING'))
        manifest['prompts'].append(e)
    save_manifest(manifest)

    # 4) commit images + manifest, push to get SHA
    run(['git', 'add', 'case-images', 'prompts.json'], cwd=LOCAL_REPO)
    run(['git', 'commit', '--quiet', '-m', f'add {len(to_add)} prompt(s): ' + ', '.join(e["id"] for e in to_add)], cwd=LOCAL_REPO)
    sha = push()
    log(f'pushed initial commit SHA={sha}')

    # 5) rewrite URLs for the just-added prompts (pin to new SHA), commit again
    for e in manifest['prompts']:
        if e['id'] in {x['id'] for x in to_add}:
            e.update(make_urls(e['id'], sha))
    save_manifest(manifest)
    run(['git', 'add', 'prompts.json'], cwd=LOCAL_REPO)
    # only commit if there are changes
    diff = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=LOCAL_REPO).returncode
    if diff != 0:
        run(['git', 'commit', '--quiet', '-m', f're-pin {len(to_add)} prompt(s) to SHA {sha[:8]}'], cwd=LOCAL_REPO)
        sha = push()
        log(f'pushed manifest pin SHA={sha}')

    # 6) sync to outputs/
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_JSON.write_text((LOCAL_REPO / 'prompts.json').read_text())

    scrub_remote()
    return {
        'added':  len(to_add),
        'failed': len(failures),
        'sha':    sha,
        'new_ids': [e['id'] for e in to_add],
        'failed_ids': [s for s, _ in failures],
    }

def remove_prompts(ids: list[str]) -> dict:
    token = load_token()
    ensure_repo(token)
    manifest = load_manifest()
    by_id = index_by_id(manifest)
    removed = []
    missing = []
    for pid in ids:
        if pid not in by_id:
            missing.append(pid); continue
        manifest['prompts'] = [p for p in manifest['prompts'] if p['id'] != pid]
        img = LOCAL_REPO / 'case-images' / f'{pid}.png'
        if img.exists(): img.unlink()
        local_img = OUTPUTS_IMAGES / f'{pid}.png'
        if local_img.exists(): local_img.unlink()
        removed.append(pid)
    if not removed:
        log(f'nothing to remove. missing: {missing}')
        scrub_remote()
        return {'removed': 0, 'missing': missing, 'sha': current_sha()}
    save_manifest(manifest)
    run(['git', 'add', '-A'], cwd=LOCAL_REPO)
    run(['git', 'commit', '--quiet', '-m', f'remove {len(removed)} prompt(s): ' + ', '.join(removed)], cwd=LOCAL_REPO)
    sha = push()
    OUTPUTS_JSON.write_text((LOCAL_REPO / 'prompts.json').read_text())
    scrub_remote()
    log(f'removed {len(removed)} prompt(s); sha={sha}')
    return {'removed': len(removed), 'missing': missing, 'sha': sha, 'removed_ids': removed}

def cmd_remove(ids: list[str]) -> None:
    if not ids: sys.exit('ERROR: provide at least one id to remove')
    res = remove_prompts(ids)
    log(f'DONE: {res}')

def cmd_batch(path: str, force: bool = False, concurrency: int = 5) -> None:
    inp = load_input(path)
    if 'prompts' not in inp or not isinstance(inp['prompts'], list):
        sys.exit('ERROR: input must have a top-level "prompts" list')
    res = add_prompts(inp['prompts'], force=force, concurrency=concurrency)
    log(f'DONE: {res}')

def cmd_add(path: str, force: bool = False) -> None:
    inp = load_input(path)
    # if top-level is a single mapping, wrap it
    entries = inp['prompts'] if 'prompts' in inp else [inp]
    res = add_prompts(entries, force=force, concurrency=1)
    log(f'DONE: {res}')

# ---------- entrypoint ----------

def main() -> None:
    ap = argparse.ArgumentParser(prog='publish_prompts', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)

    p_batch = sp.add_parser('batch', help='Add many prompts from a YAML/JSON list')
    p_batch.add_argument('input')
    p_batch.add_argument('--force', action='store_true', help='Overwrite existing prompt ids')
    p_batch.add_argument('--concurrency', type=int, default=5)

    p_add = sp.add_parser('add', help='Add one prompt')
    p_add.add_argument('input')
    p_add.add_argument('--force', action='store_true')

    p_rm = sp.add_parser('remove', help='Remove one or more prompts by id')
    p_rm.add_argument('ids', nargs='+')

    sp.add_parser('pull',   help='Sync local mirror from origin')
    sp.add_parser('status', help='Print repo + manifest stats')

    args = ap.parse_args()
    if   args.cmd == 'batch':  cmd_batch(args.input, force=args.force, concurrency=args.concurrency)
    elif args.cmd == 'add':    cmd_add(args.input, force=args.force)
    elif args.cmd == 'remove': cmd_remove(args.ids)
    elif args.cmd == 'pull':   cmd_pull()
    elif args.cmd == 'status': cmd_status()

if __name__ == '__main__':
    main()
