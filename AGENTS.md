# kodi-littlescreen

Kodi add-on `plugin.video.littlescreen` ("Little Screen"): the YouTube Kids catalogue on Kodi,
unofficial and not affiliated with YouTube or Google. Keep "YouTube" out of the add-on name, id,
icon and repository name; descriptions may say it shows the YouTube Kids catalogue.

## How it works

- `resources/lib/littlescreen/innertube.py` talks to the InnerTube API behind www.youtubekids.com
  (client `WEB_KIDS`, id 76), signed out. The age group goes in
  `kidsAppInfo.contentSettings.corpusPreference`: `PRESCHOOL` (4 and under), `YOUNGER` (5–8),
  `TWEEN` (9–12). `OLDER` is rejected by the API. The client version is scraped from the page
  and cached for a day in the add-on profile (`client.json`); a failed request refreshes it once.
- `region.py` picks `hl`/`gl`: the add-on settings when filled in, otherwise Kodi's
  interface language (`xbmc.getLanguage(ISO_639_1)`) and region. The region is the `locale`
  attribute of the `<region>` named by Kodi's `locale.country` in the language add-on's
  `langinfo.xml` (fallback: the country in its id, `resource.language.de_de` → DE).
  Languages YouTube Kids rejects with HTTP 400 (cy, eo, mt, ...) fall back to `en`; any `gl`
  is accepted.
- `catalog.py` walks responses for `compactVideoRenderer` / `compactChannelRenderer` and
  continuation tokens instead of following exact paths. Home = `browse FEkids_home`; each
  category is the same browse with the anchor's `params`.
- `plugin.py` builds Kodi listings. Videos play through `plugin.video.youtube`
  (`plugin://plugin.video.youtube/play/?video_id=`), whose "suggested videos" autoplay is off
  by default, so nothing outside the Kids catalogue starts on its own.
- `language.py` guesses whether a video is in the catalogue language (YouTube does not send
  it; the CZ catalogue mixes Czech and Slovak). Evidence is kept under labels that do not
  depend on the catalogue: language names (`name:de`; "• Čeština", "Polski", "українською"),
  the scripts of a text (`script:CYRILLIC+LATIN`, once per text) and pack markers (`cs`):
  letters and words only one language uses (`packs/`). `decide(counts, target)` weighs them
  against the catalogue language (`target_language(hl)`): markers count only when it has a
  complete pack (cs, sk); otherwise only scripts (a non-Latin script outranks Latin brand
  names in the same text) and names, so a video whose language is unclear is never hidden.
  Titles without evidence take their channel's language, learned across runs in
  `channels.json` in the add-on profile; a channel still unclear has its own page read once
  (up to 8 per listing, in parallel) and is marked "probed" in the same file. Setting
  `video_language`: 0 any language, 2 only the catalogue language (default; unclear stays;
  1 and 3 from earlier versions read as 2). A filtered page is topped up from up to 3 next
  pages.
- A category is a fixed set of ~36 items with no continuation (repeated calls add little),
  so `channel_tiles()` appends a tile for each channel behind its videos (art = one of its
  video thumbnails). Channels already shown as YouTube's own tiles, empty in YouTube Kids for
  the age group (probe per age group, `<AGE>:<id>` in `channels.json`) or in an unwanted
  language are left out. First opening of a category reads up to 12 channel pages (~1 s).
- Autoplay (`profileN.autoplay`, default on): a video tile is not playable itself but
  `action=play&v=<ids>` (run like RunPlugin), which fills Kodi's video playlist with the picked
  video and the following ones of the same listing (max 50), each through plugin.video.youtube.
  Kodi's own "play next item" setting is global by content type ("videos" = uncategorized),
  so it would also hit other add-ons; YouTube's "suggested videos" would leave the Kids catalogue.
- Profiles (up to 3) live in the add-on settings: name (empty = the localised age group), age
  group, look (big pictures for toddlers = Estuary Wall view 500, no text, no search; or a list = WideList 55, with search).

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q             # unit tests on fixtures (fake Kodi modules)
LIVE=1 .venv/bin/python -m pytest -q      # plus live API tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/kodi-addon-checker --branch omega plugin.video.littlescreen
.venv/bin/python scripts/make_media.py    # redraw icon, fanart, tiles
./scripts/build.sh                        # dist/plugin.video.littlescreen-<version>.zip
./scripts/install-kodi.sh                 # copy into the local Kodi (macOS) and enable
```

CI (`.github/workflows/ci.yml`, pull requests and `main`) runs ruff, pytest (no live tests),
`kodi-addon-checker --branch omega` and uploads the zip from `build.sh` as an artifact. Jobs
run on the runner named by the `RUNNER_LABELS` repository variable (JSON list of labels; the
self-hosted runner while the repository is private), GitHub-hosted `ubuntu-latest` when unset.

## Language filter: adding a pack

A pack makes the filter tell a language apart from its neighbours word by word (needed when
a catalogue mixes close languages, like Czech and Slovak). Without one, a catalogue is
filtered by script and language names only.

1. Collect real titles from the catalogue (`hl`/`gl` of the language) that the filter gets
   wrong or cannot decide, and from the neighbouring languages that turn up in it.
2. Add `packs/<code>.py` with `CODE`, `LETTERS` (letters no other pack uses), `WORDS`
   (lowercase whole words) and, if needed, `PATTERNS` (regexes matched against a whole
   lowercase word), and register it in `packs/__init__.py` (`complete=True` once it is
   good enough to filter a catalogue on its own; incomplete packs only add evidence against
   complete ones, like `others.py`). Language names go into `NAMES` in `language.py`.
3. Word and letter lists must not overlap between packs or with the language names
   (`test_word_lists_do_not_overlap`); a word two languages share is no marker.
4. Add the real titles as test cases (title, channel, expected) in `tests/test_language.py`,
   for the new language's catalogue and for the catalogues of its neighbours.

## Gotchas

- Kodi loads add-on strings (`strings.po`) only at startup or on a language change. After the
  first `install-kodi.sh` labels from `getLocalizedString` are empty until Kodi restarts.
- Test listings without touching the TV: JSON-RPC `Files.GetDirectory` on
  `plugin://plugin.video.littlescreen/?...` runs the add-on inside Kodi with no GUI.
- `scripts/make_fixtures.py` shrinks saved API responses into `tests/fixtures/`.
- `Container.SetViewMode` only sticks once Kodi shows the listing, so `finish()` waits for
  `Container.FolderPath`. Kodi reorders query parameters there: compare them as a dict.
- `Container.Update` from inside a listing is dropped ("updating in progress"; Kodi waits for
  the whole script). "Hledat" is therefore a non-folder item (`action=ask`, run like
  RunPlugin) that shows the keyboard and then opens `action=search&q=...`.
- Estuary draws a label that starts with an emoji as empty: `catalog.clean_label` strips them.
- plugin.video.youtube 7.4.4 on macOS: `get_connect_address` does a UDP connect to port 0
  (errno 49), falls back to the LAN IP while its server listens on 127.0.0.1, so DASH
  playback fails with "Could not connect to server". Not this add-on's bug.
- Driving the Kodi GUI in tests: `GUI.ActivateWindow` is refused while a modal dialog is
  open; `Container.Update(url)` via `scripts/kodi_builtin.py` is more reliable.
