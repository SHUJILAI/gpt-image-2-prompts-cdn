#!/usr/bin/env python3
"""
fix_image_urls.py — rewrite preview_image_latest from @main -> @assets in:
  - assets:prompts.json (full manifest)
  - main:prompts-images.json (split file)
Idempotent.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish_prompts import (  # noqa: E402
    LOCAL_REPO, OUTPUTS_DIR, GH_REMOTE, GH_USER, GH_REPO,
    refresh_indexes, split_manifest_to_dicts, load_token, make_urls,
)


def log(m): print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {m}", flush=True)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ERROR: {' '.join(cmd)}\n{r.stderr}")
    return r.stdout.strip()


def setup(token):
    auth = f"https://x-access-token:{token}@github.com/{GH_USER}/{GH_REPO}.git"
    run(["git", "remote", "set-url", "origin", auth], cwd=LOCAL_REPO)
    run(["git", "fetch", "--quiet", "origin"], cwd=LOCAL_REPO)


def main():
    setup(load_token())

    # ---- assets ----
    log("checkout assets")
    run(["git", "checkout", "--quiet", "assets"], cwd=LOCAL_REPO)
    run(["git", "reset", "--hard", "--quiet", "origin/assets"], cwd=LOCAL_REPO)

    mp = LOCAL_REPO / "prompts.json"
    m = json.loads(mp.read_text())
    fixed = 0
    for p in m["prompts"]:
        sha = p.get("preview_image_pinned_sha") or ""
        # Always rewrite the SHA-independent latest URL
        new_latest = (
            f"https://cdn.jsdelivr.net/gh/{GH_USER}/{GH_REPO}@assets/case-images/{p['id']}.png"
        )
        if p.get("preview_image_latest") != new_latest:
            p["preview_image_latest"] = new_latest
            fixed += 1
        # SHA-pinned URLs only update if we have a SHA
        if sha:
            new_urls = make_urls(p["id"], sha)
            for k, v in new_urls.items():
                if p.get(k) != v:
                    p[k] = v
                    fixed += 1
    log(f"rewrote {fixed} URL field(s) in full manifest")

    refresh_indexes(m)
    m["generated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    mp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")

    pt, pi = split_manifest_to_dicts(m)
    pt_text = json.dumps(pt, indent=2, ensure_ascii=False) + "\n"
    pi_text = json.dumps(pi, indent=2, ensure_ascii=False) + "\n"

    run(["git", "add", "prompts.json"], cwd=LOCAL_REPO)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=LOCAL_REPO).returncode
    if diff:
        run(["git", "commit", "--quiet", "-m",
             "fix: preview_image_latest -> @assets (was @main, broken since 2-branch refactor)"],
            cwd=LOCAL_REPO)
        run(["git", "push", "--quiet", "origin", "assets"], cwd=LOCAL_REPO)
        log("pushed assets")
    else:
        log("assets up-to-date")

    # ---- main ----
    log("checkout main")
    run(["git", "checkout", "--quiet", "main"], cwd=LOCAL_REPO)
    run(["git", "reset", "--hard", "--quiet", "origin/main"], cwd=LOCAL_REPO)
    (LOCAL_REPO / "prompts-text.json").write_text(pt_text)
    (LOCAL_REPO / "prompts-images.json").write_text(pi_text)
    run(["git", "add", "prompts-text.json", "prompts-images.json"], cwd=LOCAL_REPO)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=LOCAL_REPO).returncode
    if diff:
        run(["git", "commit", "--quiet", "-m",
             "fix: preview_image_latest -> @assets in split files"],
            cwd=LOCAL_REPO)
        run(["git", "push", "--quiet", "origin", "main"], cwd=LOCAL_REPO)
        log("pushed main")
    else:
        log("main up-to-date")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "prompts-text.json").write_text(pt_text)
    (OUTPUTS_DIR / "prompts-images.json").write_text(pi_text)

    try:
        run(["git", "remote", "set-url", "origin", GH_REMOTE], cwd=LOCAL_REPO)
    except SystemExit:
        pass
    log("DONE")


if __name__ == "__main__":
    main()
