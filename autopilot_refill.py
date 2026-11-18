import json
import os
import sys
import time
import urllib.error
import urllib.request

BUFFER_API_URL = "https://api.buffer.com"
TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("BUFFER_TIKTOK_CHANNEL_ID", "6afd1afeece6dfde5f040b25").strip()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_VAULT_PATH = os.path.join(SCRIPT_DIR, "VIDEOS_VAULT.json")
CAROUSELS_VAULT_PATH = os.path.join(SCRIPT_DIR, "VICEDALE_VAULT.json")
HISTORY_PATH = os.path.join(SCRIPT_DIR, "posted_history.json")

# ─────────────────────────────────────────────────────────────────
# ANTI-SHADOWBAN HYBRID AUTOPILOT v3.0
# - Pro MP4 Videos (with built-in VO + Music + SFX) -> automatic publish
# - Photo Carousels (need TikTok trending sound)    -> notification (Notify Me)
# ─────────────────────────────────────────────────────────────────

GTA6_SEO_TAGS = [
    "#gta6", "#gtavi", "#gta6tips", "#gta6launch", "#gta6guide",
    "#vicecity", "#leonida", "#rockstargames", "#gta6gameplay",
    "#gta6map", "#gta6secrets", "#gta6viral", "#gta6hype",
    "#gaming", "#ps5", "#xbox"
]

ENGAGEMENT_HOOKS = [
    "💾 Save this before launch night.",
    "🔁 Share with your squad playing tonight.",
    "👇 Drop which one surprised you most.",
    "🌟 Follow for daily GTA 6 drops.",
    "💬 Which region are you exploring first?",
    "🔥 Follow @vicedale.gg — posting live on launch night.",
    "✅ Save & follow for verified Rockstar info only.",
    "😮 Watch till the end — last stat is wild.",
]

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
    raw = post.get("text", "").strip()
    # Videos already have bespoke SEO captions with exactly 5 viral tags
    if post.get("video_url") and raw:
        return raw
    base_text_lines = raw.split("\n\n")
    core_text = base_text_lines[0] if base_text_lines else post.get("tiktok_title", "")
    hook = ENGAGEMENT_HOOKS[post_index % len(ENGAGEMENT_HOOKS)]
    # Always lead with #gta6 #gtavi + 3 rotating high-volume GTA6 SEO tags (EXACTLY 5 tags)
    rotating_pool = [t for t in GTA6_SEO_TAGS if t not in ("#gta6", "#gtavi")]
    offset = (post_index * 3) % len(rotating_pool)
    rotated = rotating_pool[offset:] + rotating_pool[:offset]
    selected_5 = ["#gta6", "#gtavi"] + rotated[:3]
    tags_str = " ".join(selected_5)
    return f"{core_text}\n\n{hook}\n\n{tags_str}"


def push_tiktok_post(post: dict, post_index: int, mode: str = "addToQueue") -> dict:
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

    is_video = bool(post.get("video_url"))
    caption = build_caption(post, post_index)

    if is_video:
        assets = [{"video": {"url": post["video_url"]}}]
        scheduling_type = "automatic"
        tiktok_meta = {"isAiGenerated": False}
    else:
        assets = [{"image": {"url": url}} for url in post["slides"]]
        scheduling_type = "notification"
        tiktok_meta = {
            "title": post["tiktok_title"][:90],
            "isAiGenerated": False,
        }

    variables = {
        "input": {
            "channelId": CHANNEL_ID,
            "text": caption,
            "mode": mode,
            "schedulingType": scheduling_type,
            "needsApproval": False,
            "assets": assets,
            "metadata": {"tiktok": tiktok_meta},
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return {"errors": [{"message": f"HTTP {e.code}: {body[:400]}"}]}


def run_autopilot():
    if not TOKEN:
        print("ERROR: BUFFER_ACCESS_TOKEN environment variable is missing.")
        sys.exit(1)

    max_posts = None
    only_type = None
    for arg in sys.argv[1:]:
        if arg.startswith("--max="):
            max_posts = int(arg.split("=")[1])
        elif arg.startswith("--only="):
            only_type = arg.split("=")[1].strip().lower()

    videos_vault = load_json(VIDEOS_VAULT_PATH, [])
    carousels_vault = load_json(CAROUSELS_VAULT_PATH, [])
    posted_history = load_json(HISTORY_PATH, [])

    videos_sorted = sorted(videos_vault, key=lambda x: x.get("viral_score", 0), reverse=True)
    carousels_sorted = sorted(carousels_vault, key=lambda x: x.get("viral_score", 0), reverse=True)

    if only_type == "videos":
        combined = videos_sorted
    elif only_type == "carousels":
        combined = carousels_sorted
    else:
        # Prioritize Pro Videos (automatic with music+VO), then Notify Carousels
        combined = videos_sorted + carousels_sorted

    print("=== [Vice-Dale GTA 6 TikTok Autopilot v3.0 — Hybrid Pro Video + Notify Carousel] ===")
    print(f"Channel: {CHANNEL_ID} (@vicedale.gg)")
    print(f"Videos: {len(videos_sorted)} (auto) | Carousels: {len(carousels_sorted)} (notify) | Posted: {len(posted_history)}")
    print()

    unposted = [p for p in combined if p["id"] not in posted_history]
    if not unposted:
        print("All items posted! Resetting rotation cycle.")
        posted_history = []
        unposted = list(combined)

    posts_added = 0
    for idx, post in enumerate(unposted):
        if max_posts is not None and posts_added >= max_posts:
            print(f"Reached --max={max_posts} cap.")
            break

        kind = "VIDEO (AUTO)" if post.get("video_url") else "CAROUSEL (NOTIFY)"
        print(f"-> [{idx+1}/{len(unposted)}] [{kind}] {post['id']} | Score: {post.get('viral_score', '?')}")
        print(f"   Title: {post.get('tiktok_title', '')}")

        try:
            res = push_tiktok_post(post, post_index=posts_added)
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
    print(f"\n=== Done! Queued {posts_added} items for @vicedale.gg ===")


if __name__ == "__main__":
    run_autopilot()
