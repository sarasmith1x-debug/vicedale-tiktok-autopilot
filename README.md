# Vice-Dale GTA 6 TikTok Autopilot (`@vicedale.gg`)

Automated GitHub Actions + Buffer GraphQL pipeline that keeps `@vicedale.gg` on TikTok filled (`10/10` scheduled posts) with 20 high-resolution 5-slide GTA 6 carousels (100 HD 1080x1920 slides).

## How it works
1. All 20 GTA 6 carousels (5 HD slides each) live in `posts/` and are indexed in `VICEDALE_VAULT.json`.
2. GitHub Actions (`.github/workflows/vicedale_autopilot.yml`) runs every 6 hours.
3. `autopilot_refill.py` pushes unposted multi-image TikTok carousels to Buffer GraphQL API (`https://api.buffer.com`) until the 10-post Free Tier queue is full.
4. `posted_history.json` is committed automatically after each run to avoid duplicates.

## Required GitHub Secret
- `BUFFER_ACCESS_TOKEN` — Buffer Personal Access Token (`ViceDale GTA6`).
