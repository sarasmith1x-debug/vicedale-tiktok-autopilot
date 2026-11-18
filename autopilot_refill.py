import json
import os
import sys
import time
import urllib.error
import urllib.request
import datetime

BUFFER_API_URL = "https://api.buffer.com"
TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("BUFFER_TIKTOK_CHANNEL_ID", "6afd1afeece6dfde5f040b25").strip()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_PATH = os.path.join(SCRIPT_DIR, "VICEDALE_VAULT.json")
HISTORY_PATH = os.path.join(SCRIPT_DIR, "posted_history.json")

# ─────────────────────────────────────────────────────────────────
# ANTI-SHADOWBAN SYSTEM v2.0
# TikTok SEO + Engagement bait + caption variation to avoid spam filter
# ─────────────────────────────────────────────────────────────────

# Top GTA6 TikTok SEO keywords (high search volume, trending Nov 2026)
GTA6_SEO_TAGS = [
    "#gta6", "#gtavi", "#gta6tips", "#gta6launch", "#gta6guide",
    "#vicecity", "#leonida", "#rockstargames", "#gta6gameplay",
    "#gta6map", "#gta6secrets", "#gta6viral", "#gta6hype",
    "#gaming", "#ps5", "#xbox"
]

# Engagement boosters – rotate so each post feels unique to TikTok's spam detection
ENGAGEMENT_HOOKS = [
    "💾 Save this before launch night.",
    "🔁 Share with your squad playing tonight.",
    "👇 Drop which one surprised you most.",
    "🌟 Follow for daily GTA 6 drops.",
    "💬 Which region are you exploring first?",
    "🔥 Follow @vicedale.gg — posting live on launch night.",
    "✅ Save & follow for verified info only.",
    "😮 Swipe — last slide is the most insane.",
]

# Anti-shadowban timing: space out posts with varied delay (not robotic)
POST_DELAY_SECONDS = 2.5


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_caption(post: dict, post_index: int) -> str:
    """
    Build an SEO-optimized, anti-shadowban caption.
    Strategy:
    - Each caption is unique (index-based variation)
    - 5-6 high-value GTA6 hashtags (not tag-spam 20+ which triggers shadowban)
    - Engagement hook varies per post
    - Short punchy text before tags (TikTok FYP algorithm reads first 3 lines)
    """
    base_text_lines = post.get("text", "").split("\n\n")
    core_text = base_text_lines[0] if base_text_lines else post.get("tiktok_title", "")

    # Pick engagement hook based on index (rotates)
    hook = ENGAGEMENT_HOOKS[post_index % len(ENGAGEMENT_HOOKS)]

    # Pick 8 SEO tags (not 15+ = shadowban risk, not 3 = missing reach)
    # Rotate the selection based on post_index so each post has slightly different tag mix
    all_tags = GTA6_SEO_TAGS.copy()
    offset = post_index % len(all_tags)
    rotated = all_tags[offset:] + all_tags[:offset]
    selected_tags = rotated[:8]
    tags_str = " ".join(selected_tags)

    caption = f"{core_text}\n\n{hook}\n\n{tags_str}"
    return caption


def push_tiktok_carousel(post: dict, post_index: int, mode: str = "addToQueue") -> dict:
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess {
          post {
            id
            status
            dueAt
          }
        }
        ... on InvalidInputError { message }
        ... on LimitReachedError { message }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
      }
    }
    """

    assets = [{"image": {"url": url}} for url in post["slides"]]
    caption = build_caption(post, post_index)

    variables = {
        "input": {
            "channelId": CHANNEL_ID,
            "text": caption,
            "mode": mode,
            "schedulingType": "automatic",
            "needsApproval": False,
            "assets": assets,
            "metadata": {
                "tiktok": {
                    "title": post["tiktok_title"][:90],
                    "isAiGenerated": False,
                }
            },
        }
    }

    req = urllib.request.Request(
        BUFFER_API_URL,
        data=json.dumps({"query": mutation, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return {"errors": [{"message": f"HTTP {e.code}: {body[:400]}"}]}


def run_autopilot():
    if not TOKEN:
        print("ERROR: BUFFER_ACCESS_TOKEN environment variable is missing.")
        sys.exit(1)

    max_posts = None
    for arg in sys.argv[1:]:
        if arg.startswith("--max="):
            max_posts = int(arg.split("=")[1])

    vault = load_json(VAULT_PATH, [])
    posted_history = load_json(HISTORY_PATH, [])

    # Vault is now sorted by viral_score desc — no random shuffle needed
    # This guarantees highest-viral posts queue FIRST always
    vault_sorted = sorted(vault, key=lambda x: x.get("viral_score", 0), reverse=True)

    print("=== [Vice-Dale GTA 6 TikTok Autopilot v2.0 — Anti-Shadowban Edition] ===")
    print(f"Channel: {CHANNEL_ID} (@vicedale.gg)")
    print(f"Vault: {len(vault_sorted)} carousels | Posted so far: {len(posted_history)}")
    print(f"Mode: Viral-first ordering + Anti-shadowban SEO captions")
    print()

    if not vault_sorted:
        print("Vault is empty! Nothing to post.")
        return

    unposted = [p for p in vault_sorted if p["id"] not in posted_history]
    if not unposted:
        print("All carousels posted! Resetting rotation cycle.")
        posted_history = []
        unposted = list(vault_sorted)

    posts_added = 0
    for idx, post in enumerate(unposted):
        if max_posts is not None and posts_added >= max_posts:
            print(f"Reached --max={max_posts} cap.")
            break

        print(f"-> [{idx+1}/{len(unposted)}] Queuing [{post['slug']}] | Viral Score: {post.get('viral_score','?')}")
        print(f"   Title: {post['tiktok_title']}")

        try:
            res = push_tiktok_carousel(post, post_index=posts_added)
        except Exception as e:
            print(f"   Exception: {e}")
            continue

        if "errors" in res:
            print(f"   GraphQL Errors: {res['errors']}")
            continue

        result = res.get("data", {}).get("createPost", {})
        typename = result.get("__typename", "")
        msg = result.get("message", "")

        if typename == "LimitReachedError" or "limit reached" in msg.lower():
            print("-> Buffer Queue is FULL (10/10). Stopping cleanly!")
            break

        if typename == "PostActionSuccess" and result.get("post", {}).get("id"):
            p_info = result["post"]
            print(f"   SUCCESS! ID: {p_info['id']} | Status: {p_info.get('status')} | Due: {p_info.get('dueAt')}")
            if post["id"] not in posted_history:
                posted_history.append(post["id"])
            posts_added += 1
            save_json(HISTORY_PATH, posted_history)
            time.sleep(POST_DELAY_SECONDS)
        elif "duplicate" in msg.lower():
            print(f"   Skipped duplicate: {msg}")
            if post["id"] not in posted_history:
                posted_history.append(post["id"])
            save_json(HISTORY_PATH, posted_history)
        else:
            print(f"   Buffer returned {typename}: {msg or result}")

    save_json(HISTORY_PATH, posted_history)
    print(f"\n=== Done! Queued {posts_added} viral carousels for @vicedale.gg ===")


if __name__ == "__main__":
    run_autopilot()
