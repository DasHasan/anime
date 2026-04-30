# Anime Viewer — Agent Handoff

Single-file German-language anime streaming viewer. Everything lives in `index.html`.
Working branch: `claude/anime-web-scraper-52vx9`.

---

## Architecture

The app is a single-page, vanilla-JS, mobile-first viewer (no build step, no framework).

**Video pipeline (client-side only):**
The browser fetches source pages via a CORS proxy (`https://cors.eu.org/`), extracts embed or
direct video URLs from the HTML, and plays them. No server component. No eval() execution. No
Node.js.

```
Browser → cors.eu.org → source site → parse HTML → embed/video URL → play
```

**`ANIME_LIST`** (top of `<script>`) is the config. Each entry has `id`, `label`, `short`, `icon`,
and a `seasons` array. Each season has a `type` that controls how episodes are loaded and played.

### Season types

| type | Load | Play | Used by |
|------|------|------|---------|
| `tube` | Count only (`episodeCount`) | Fetches `onepiece.tube/anime/folge/N` → extracts hubu.cloud embed → extracts `.mp4` URL → native `<video>` | One Piece |
| `ajax` | Fetches pre-generated `.txt` file from animetoast.cc with one iframe URL per line | Loads URL as `<iframe>` | Frieren S1 |
| `link` | Count only (`episodeCount`) | Fetches `animetoast.cc/{slug}/?link={linkOffset+N}` → extracts iframe/voe.sx URL → `<iframe>` | Frieren S2 |
| `animebase` | Fetches `anime-base.net/anime/{slug}` → parses Inertia.js `data-page` JSON attr → caches all episode `link1` URLs | Converts `link1` to `/e/{id}` embed URL → `<iframe>` | JJK (current, broken) |

### Key functions

- `loadSeason(idx, resumeEp)` — dispatches to the correct loader based on `season.type`
- `loadAjaxEpisodes(season, resumeEp)` — ajax/txt-file loader
- `loadAnimebaseEpisodes(season, resumeEp)` — anime-base.net Inertia.js loader
- `loadLinkEpisodes(season, resumeEp)` — simple count-based loader (tube + link types)
- `selectEpisode(epNum, isResume)` — fetches and plays an episode; branches on `season.type`
- `decodeHtmlEntities(str)` — uses `<textarea>` trick to decode HTML entities in the `data-page` attr
- `proxyGet(url)` — `fetch(CORS + url).then(r => r.text())`

### Player elements

- `<video id="player-video">` — used for direct MP4 (tube type only)
- `<iframe id="player-frame">` — used for all embed types (ajax, link, animebase)

---

## What works

### One Piece (`tube` type)
**Source:** `onepiece.tube`
**Status: fully working.**

Pipeline:
1. `proxyGet('https://onepiece.tube/anime/folge/N')` → regex for `hubu.cloud` iframe src
2. `proxyGet(hubu.cloud URL)` → regex for `<source src="...mp4?download_token=...">` (in static HTML, no JS eval)
3. Set `playerVideo.src` → native `<video>` playback

Characteristics: no CDN challenge, no JS required, MP4 URL directly in HTML.

### Frieren S1 (`ajax` type)
**Source:** `animetoast.cc` pre-generated txt files
**Status: working** (dependent on txt files being maintained).

### Frieren S2 (`link` type)
**Source:** `animetoast.cc` with link offset
**Status: working** (same dependency caveat).

---

## What is broken / needs work

### JJK (`animebase` type)
**Current source:** `anime-base.net`
**Status: BROKEN / NEEDS REPLACEMENT.**

The `animebase` type was implemented and is in the code but the user reports it has issues.
The suspected problems (not fully diagnosed yet):

1. **luluvid.com iframes may not load** — luluvid.com / lulustream.com could have
   `X-Frame-Options: SAMEORIGIN` or Cloudflare blocking that prevents embedding in a foreign
   origin iframe.
2. **`link1` may be null** for some episodes — the research showed 96/119 episodes use luluvid
   in `link1`; the remaining 23 use voe.sx in `link3` (DDoS-Guard protected) or lulustream.com.
3. **The `data-page` regex may miss the attribute** if anime-base.net's HTML structure changed
   or if the attribute is split across lines.

**The user wants a different source for JJK entirely.** The `animebase` type can stay in the code
as a fallback but a new, reliable source needs to be found and wired in.

---

## German streaming site research — full findings

This was extensively researched. Summary for JJK specifically:

### Sites that DON'T work (hard blocked)
| Site | Reason |
|------|--------|
| `aniworld.to` | DDoS-Guard JS challenge (HTTP 403, 898-byte challenge page) |
| `anime4you.cc` | Cloudflare blocking challenge (200 but no real content) |
| `anime-hood.to` | HTTP 403 on all requests |
| `anicloud.io` | HTTP 503 |
| `anime-loads.org` | DDoS-Guard HTTP 403 |
| `anime-serien.com` | HTTP 503 |

### Sites that DON'T work for video extraction
| Site | Reason |
|------|--------|
| `s.to` | DDoS-Guard passthrough (200), but embed URL loaded dynamically via React API (`/api/inline/verify-init`) — not in static HTML |
| `anime-stream.to` | Series listing 200, but episode redirect uses Cloudflare Turnstile interactive challenge |
| `jujutsu-stream.com` | Listing 200 (Vue SPA with episode slugs in JS), but all `/watch/` episode pages return 404 |

### Sites that partially work
| Site | What works | What doesn't |
|------|-----------|--------------|
| `animetoast.cc` | HTTP 200, has JJK GerSub + GerDub S1/S2/S3 (partial), vidmoly server 3 m3u8 in static HTML | ~42% of episodes have Cloudflare Turnstile on vidmoly; voe.sx (server 1) is DDoS-Guard blocked; byse.sx (server 2) is Vite SPA with no video in static HTML. Old txt-file approach used `iframe-data/` path which still exists. |
| `otakustream.de` | HTTP 200, no CDN at all, voe.sx iframe src directly in static HTML | **Does NOT have JJK** (confirmed). voe.sx itself is DDoS-Guard protected so can only be used as iframe (not for direct video). |
| `anime-base.net` | HTTP 200 (Cloudflare passive only), all JJK episodes in Inertia.js JSON | luluvid.com embed may not work as iframe (unconfirmed); m3u8 extraction requires eval-unpacking + m3u8 token is IP-bound |

### What a good source looks like (requirements)
The ideal source matches `onepiece.tube`:
- HTTP 200 on episode/listing page (no JS challenge)
- Embed URL or direct video URL **in static HTML** (no JS-only loading)
- Embed host either: (a) directly embeddable as `<iframe>` without X-Frame-Options blocking, OR (b) returns a direct video URL (MP4 or m3u8) in its own static HTML

### Suggested next research directions for JJK

1. **Diagnose the current `animebase` failure first** — is it a luluvid iframe issue or a
   data-page parsing issue? Open DevTools on the live page, click a JJK episode, and check
   the console/network tab.

2. **Try animetoast.cc vidmoly approach** — server 3 on animetoast.cc uses vidmoly.net, and
   the m3u8 is directly in the static HTML for ~58% of episodes. This would require a new
   season type that: (a) GETs the animetoast listing page, (b) extracts the nonce from
   `var iframe_loader = {...,"nonce":"..."}`, (c) POSTs to `admin-ajax.php` with
   `action=get_episode_data&title=...&server=3&episode=N&nonce=...`, (d) fetches the vidmoly
   embed URL, (e) regexes out `sources: [{ file: '...' }]` for the m3u8.
   Known animetoast.cc JJK slugs/titles:
   - S1 Sub: slug=`jujutsu-kaisen-ger-sub`, title=`Jujutsu Kaisen S1`, 24 eps
   - S1 Dub: slug=`jujutsu-kaisen-ger-dub`, title=`Jujutsu Kaisen Dub S1`, 24 eps
   - S2 Sub: slug=`jujutsu-kaisen-2nd-season-ger-sub`, title=`Jujutsu Kaisen S2`, 23 eps
   - S2 Dub: slug=`jujutsu-kaisen-2nd-season-ger-dub`, title=`Jujutsu Kaisen Dub S2`
   - S3 Sub: slug=`jujutsu-kaisen-shimetsu-kaiyuu-zenpen-ger-sub` (partial, being added)
   Caveat: vidmoly Turnstile affects ~42% of episodes; those would silently fail.

3. **Keep searching** — look for niche/dedicated JJK streaming sites (like `onepiece.tube`
   is for One Piece) that have no protection and direct video URLs. Search terms:
   "jujutsu kaisen deutsch stream site" / "jjk german streaming" — filter for smaller/niche
   sites not on the main blocked list above.

4. **Check `randaris.app`** — the original research flagged it as "landing page only" but
   it may have content under different paths. Low priority.

---

## CORS proxy

`const CORS = 'https://cors.eu.org/';` — prepended to every fetch URL.
Used for all source sites and embed hosts. Works for sites that return HTTP 200.
Does NOT help with sites behind JS challenges (DDoS-Guard, Cloudflare Turnstile).

**IP-binding caveat:** if an embed host generates a time/IP-bound token when the page is
fetched via the CORS proxy, that token is bound to the proxy's IP. Video segments fetched
directly by the browser from the CDN (different IP) will get 403. This is why luluvid m3u8
extraction is not viable without a full proxy chain. Iframe approach sidesteps this (the
user's browser fetches luluvid directly).

---

## Implementation guide for a new JJK source

Once a working source is confirmed, wire it in by:

1. Add a new season `type` constant (e.g. `'vidmoly'`, `'jjknew'`, etc.)
2. Add a `loadXxxEpisodes(season, resumeEp)` function that populates the global `episodes`
   array with objects `{ number, title, <source-specific-url-field> }`
3. Add the case to `loadSeason()`:
   ```js
   } else if (season.type === 'newtype') {
     await loadXxxEpisodes(season, resumeEp);
   }
   ```
4. Add the case to `selectEpisode()`:
   - If the source yields a direct MP4: set `playerVideo.src`, show `playerVideo`, return early
     (follow the `tube` type pattern, lines 857–877)
   - If the source yields an iframe embed URL: set `embedUrl` and fall through to
     `playerFrame.src = embedUrl` (follow the `ajax`/`animebase` pattern)
5. Update the JJK entry in `ANIME_LIST`:
   ```js
   { label: 'Staffel 1', type: 'newtype', /* source-specific fields */ }
   ```

The `animebase` season type and its functions (`loadAnimebaseEpisodes`, `decodeHtmlEntities`)
can remain in the code — just change the JJK seasons config to use the new type.
