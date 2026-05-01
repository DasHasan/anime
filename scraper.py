#!/usr/bin/env python3
"""
aniworld.to scraper — extracts episode list from a season page.

Usage:
    python scraper.py [URL]

Example:
    python scraper.py https://aniworld.to/anime/stream/jujutsu-kaisen/staffel-1

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium
"""

import sys
import json
import asyncio
from urllib.parse import urljoin

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install dependencies first:\n  pip install playwright beautifulsoup4\n  playwright install chromium")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependencies first:\n  pip install playwright beautifulsoup4\n  playwright install chromium")
    sys.exit(1)

BASE_URL = "https://aniworld.to"
DEFAULT_URL = "https://aniworld.to/anime/stream/jujutsu-kaisen/staffel-1"
DDOS_GUARD_TIMEOUT = 15  # seconds to wait for DDoS-Guard challenge


async def wait_for_ddos_guard(page):
    """Wait until DDoS-Guard challenge completes."""
    print("  Waiting for DDoS-Guard challenge to complete...", flush=True)
    for _ in range(DDOS_GUARD_TIMEOUT * 2):
        title = await page.title()
        if "DDoS-Guard" not in title:
            print("  Challenge passed.", flush=True)
            return True
        await asyncio.sleep(0.5)
    return False


async def scrape_season(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="de-DE",
        )
        page = await context.new_page()

        print(f"Fetching: {url}", flush=True)
        await page.goto(url, wait_until="commit", timeout=30_000)

        passed = await wait_for_ddos_guard(page)
        if not passed:
            await browser.close()
            raise RuntimeError(
                "DDoS-Guard challenge did not complete within "
                f"{DDOS_GUARD_TIMEOUT}s. Try again or check your connection."
            )

        # Wait for main content to load
        await page.wait_for_load_state("networkidle", timeout=15_000)

        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")

    # ── Anime title ──────────────────────────────────────────────────
    title_el = soup.select_one("h1.series-title, h1[itemprop='name'], h1")
    anime_title = title_el.get_text(strip=True) if title_el else "Unknown"

    # ── Season info ──────────────────────────────────────────────────
    season_el = soup.select_one(".season-title, #season-title, h2.seasonEpisodesList")
    season_title = season_el.get_text(strip=True) if season_el else ""

    # ── Episodes ─────────────────────────────────────────────────────
    # aniworld.to lists episodes in <table> or <div> rows inside
    # a container with class "episodesList" or similar.
    episodes = []

    # Strategy 1: table rows with episode links
    rows = soup.select("table.seasonEpisodesList tr, .episodesList tr")
    for row in rows:
        link = row.select_one("a[href*='/episode-']")
        if not link:
            continue
        ep_url = urljoin(BASE_URL, link["href"])
        ep_title_el = row.select_one(".seasonEpisodeTitle, td.seasonEpisodeTitle a")
        ep_title = ep_title_el.get_text(strip=True) if ep_title_el else link.get_text(strip=True)
        ep_num_el = row.select_one(".seasonEpisodeCount, td:first-child")
        try:
            ep_num = int(ep_num_el.get_text(strip=True))
        except (ValueError, AttributeError):
            ep_num = len(episodes) + 1
        episodes.append({"number": ep_num, "title": ep_title, "url": ep_url})

    # Strategy 2: anchor tags that match /episode-N pattern
    if not episodes:
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/episode-" in href and href not in seen:
                seen.add(href)
                ep_url = urljoin(BASE_URL, href)
                ep_title = a.get_text(strip=True) or href.split("/")[-1]
                episodes.append({"number": len(episodes) + 1, "title": ep_title, "url": ep_url})

    episodes.sort(key=lambda e: e["number"])

    return {
        "anime_title": anime_title,
        "season_title": season_title,
        "source_url": url,
        "episode_count": len(episodes),
        "episodes": episodes,
    }


def print_results(data: dict):
    print(f"\n{'='*60}")
    print(f"Anime : {data['anime_title']}")
    if data["season_title"]:
        print(f"Season: {data['season_title']}")
    print(f"URL   : {data['source_url']}")
    print(f"Episodes found: {data['episode_count']}")
    print(f"{'='*60}")
    for ep in data["episodes"]:
        print(f"  {ep['number']:>3}. {ep['title']}")
        print(f"       {ep['url']}")
    print()


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    data = await scrape_season(url)
    print_results(data)

    out_file = "episodes.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
