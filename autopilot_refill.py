import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

BUFFER_API_URL = "https://api.buffer.com"
TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("BUFFER_TIKTOK_CHANNEL_ID", "6afd1afeece6dfde5f040b25").strip()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_PATH = os.path.join(SCRIPT_DIR, "VICEDALE_VAULT.json")
HISTORY_PATH = os.path.join(SCRIPT_DIR, "posted_history.json")


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


def push_tiktok_carousel(post: dict, mode: str = "addToQueue") -> dict:
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
        ... on InvalidInputError {
          message
        }
        ... on LimitReachedError {
          message
        }
        ... on NotFoundError {
          message
        }
        ... on UnauthorizedError {
          message
        }
        ... on UnexpectedError {
          message
        }
      }
    }
    """

    assets = [{"image": {"url": url}} for url in post["slides"]]

    variables = {
        "input": {
            "channelId": CHANNEL_ID,
            "text": post["text"],
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

    print("=== [Vice-Dale GTA 6 TikTok Autopilot] ===")
    print(f"Channel ID: {CHANNEL_ID} (@vicedale.gg)")
    print(f"Vault size: {len(vault)} carousels ({len(vault) * 5} HD slides)")
    print(f"Previously queued/posted: {len(posted_history)}")

    if not vault:
        print("Vault is empty! Nothing to post.")
        return

    unposted = [p for p in vault if p["id"] not in posted_history]
    if not unposted:
        print("All 20 carousels have cycled once! Resetting rotation cycle.")
        posted_history = []
        unposted = list(vault)

    # Keep Day-1 Checklist first on initial launch, shuffle the rest naturally
    if len(posted_history) == 0 and len(unposted) > 1:
        first = unposted[0]
        rest = unposted[1:]
        random.shuffle(rest)
        candidates = [first] + rest
    else:
        random.shuffle(unposted)
        candidates = unposted

    posts_added = 0
    for post in candidates:
        if max_posts is not None and posts_added >= max_posts:
            print(f"Reached --max={max_posts} cap for this run.")
            break

        print(f"\n-> Queuing [{post['slug']}]: {post['tiktok_title']}")
        try:
            res = push_tiktok_carousel(post)
        except Exception as e:
            print(f"   Exception: {e}")
            continue

        if "errors" in res:
            print(f"   GraphQL Errors: {res['errors']}")
            continue

        result = res.get("data", {}).get("createPost", {})
        typename = result.get("__typename", "")
        msg = result.get("message", "")

        if typename == "LimitReachedError" or "limit reached" in msg.lower() or "10 scheduled" in msg.lower():
            print("-> Buffer TikTok Queue is FULL (10/10 scheduled). Stopping cleanly!")
            break

        if typename == "PostActionSuccess" and result.get("post", {}).get("id"):
            p_info = result["post"]
            print(f"   SUCCESS! Post ID: {p_info['id']} | Status: {p_info.get('status')} | Due: {p_info.get('dueAt')}")
            if post["id"] not in posted_history:
                posted_history.append(post["id"])
            posts_added += 1
            save_json(HISTORY_PATH, posted_history)
            time.sleep(2.0)
        elif "duplicate" in msg.lower():
            print(f"   Skipped duplicate: {msg}")
            if post["id"] not in posted_history:
                posted_history.append(post["id"])
            save_json(HISTORY_PATH, posted_history)
        else:
            print(f"   Buffer returned {typename}: {msg or result}")

    save_json(HISTORY_PATH, posted_history)
    print(f"\n=== Finished! Queued {posts_added} new TikTok carousels for @vicedale.gg ===")


if __name__ == "__main__":
    run_autopilot()
