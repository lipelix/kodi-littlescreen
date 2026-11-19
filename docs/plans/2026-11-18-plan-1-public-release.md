# Plan 1: public release on GitHub Pages

Status: in progress — Tasks 1–2 done (2026-11-19)

## Goal

Little Screen (`plugin.video.littlescreen`) is installable by anyone from a Kodi repository
hosted on GitHub Pages and works outside the Czech Republic: catalogue language and region
follow Kodi, the language filter is not Czech-only, and the add-on is tested on Kodi 20–22.

## Starting point

The add-on was imported from its private predecessor `plugin.video.ytkids` 0.4.2: the YouTube
Kids catalogue through the youtubekids.com InnerTube API (client `WEB_KIDS`, signed out, age
group via `corpusPreference`), up to three profiles (big pictures for toddlers or a list with
search), a Czech/Slovak language filter, channel tiles at the end of categories, autoplay of
the following videos, playback through `plugin.video.youtube`. See `AGENTS.md`.

Checked on 2026-11-18 (signed out, `hl`/`gl`): DE, US, PL, SK, ES, JP, RU, UA and SA return
localised categories; CN returns one category. The client version must be read from the
youtubekids.com page; some loads carry an experiment build (handled in 0.4.2).

## Guardrails

- **Name.** "Little Screen" only. No "YouTube" in the add-on name, id, icon or repository
  name; descriptions say it shows the YouTube Kids catalogue, is unofficial and not affiliated
  with YouTube or Google.
- **No private details** in code, docs, commits, issues, PRs, CI logs or screenshots: no
  machine names, home paths, host names, local network addresses or family details.
  Screenshots come from a clean Kodi profile.
- **No data leaves the device** except requests to youtubekids.com and what
  `plugin.video.youtube` does for playback. No analytics.
- **Kodi rules.** Every change passes `kodi-addon-checker --branch omega`, `ruff` and the
  tests. English (`en_gb`) is the source language; Czech stays complete.
- **Settings stay compatible** within Little Screen (ids keep their meaning once released).

## Tasks

### Task 1: Rename to Little Screen

- Add-on id `plugin.video.littlescreen`, name "Little Screen", provider `lipelix`, version
  `0.5.0`; Python package `ytkids` → `littlescreen`; log prefix, scripts, `AGENTS.md`, tests.
- Summary/description/disclaimer in en_gb and cs_cz per the guardrails; `news` starts fresh.
- Icon and fanart stay (they carry no text); check them for anything brand-like.
- Done when: the add-on installs under the new id in a test Kodi, all checks pass, and
  `git grep -i -E 'ytkids|youtube kids'` only finds descriptive mentions.

### Task 2: Language and region follow Kodi

- Settings `hl`/`gl` get an "Automatic" default: language from Kodi's interface language
  (`xbmc.getLanguage(xbmc.ISO_639_1)`), region from Kodi's region/country setting; find a
  reliable source and map it to an ISO 3166 code, with a fallback from the language. Manual
  values still override.
- Default profile names are not Czech literals any more: an empty name shows the localised age
  label ("Ages 4 and under", …).
- The language filter defaults to "Automatic": "Czech only" when the catalogue language is
  Czech, otherwise "Any language" (Task 3 widens this).
- Done when: unit tests cover the mapping; with Kodi set to German the add-on shows the German
  catalogue without touching its settings.

### Task 3: Language filter beyond Czech and Slovak

- Split `language.py` into a generic part (scripts, language names in channel names, channel
  memory) and marker packs per language (`cs`, `sk` to start).
- Setting "Videos in": Any language / Only the catalogue language. For a language with a
  pack, use it; otherwise filter by script (Latin, Cyrillic, Greek, Arabic, Hebrew, CJK, …)
  and language names only, which never hides a video of an unclear language.
- Document in `AGENTS.md` how to add a pack (word lists must not overlap; a test per pack with
  real titles).
- Done when: tests cover cs/sk on the existing real titles and script filtering on samples
  from at least DE, PL, RU and JP catalogues.

### Task 4: CI

- GitHub Actions on pull requests and `main`: `ruff check`, `ruff format --check`, `pytest`
  (no live tests), `kodi-addon-checker --branch omega`, build the add-on zip as an artifact.
- While the repository is private, jobs run on the self-hosted runner picked by the
  `RUNNER_LABELS` repository variable; once public, GitHub-hosted runners are fine.
- Done when: a PR shows the checks green.

### Task 5: Kodi repository on GitHub Pages

- A repository add-on (`repository.littlescreen`) whose `datadir`, `info` and `checksum` point
  to `https://lipelix.github.io/kodi-littlescreen/`.
- A script builds the Pages tree: `addons.xml`, `addons.xml.md5`, `<id>/<id>-<version>.zip`
  for the add-on and the repository add-on, plus the repository zip at the root for the first
  install.
- A workflow publishes the tree to Pages on a `v*` tag (Pages is switched on in Task 8).
- Done when: the tree, served locally, installs the repository and then the add-on in a test
  Kodi, and an update is offered after a version bump.

### Task 6: README and landing page

- `README.md`: what it is, screenshots, install (repository zip from Pages), profiles and
  settings, language filter, autoplay, privacy, limits (unofficial API, profiles are not a
  lock: use Kodi's master lock), the macOS note below, licence.
- macOS note: `plugin.video.youtube` 7.4.x cannot play there until its HTTP server listens on
  `0.0.0.0` (YouTube add-on settings → HTTP server); explain the trade-off.
- Pages `index.html`: the same in short, with the "Download repository" button.
- Done when: both render well (checked in a browser), with no private details.

### Task 7: Kodi 20, 21 and 22

- Run each Kodi version headless in a Linux container (Xvfb), install the add-on, list
  profiles/categories/channels over JSON-RPC and start one video.
- Fix what breaks; set `xbmc.python` to the lowest version that works and document it.
- Done when: a script reruns the check and the result is in the PR.

### Task 8: Go public (owner gate)

- Scan the whole tree and history for private details (guardrails) and fix them.
- The owner makes the repository public and switches Pages on; then tag `v1.0.0`, check the
  Pages URL installs on a clean Kodi.
- Done when: v1.0.0 is installable from the Pages URL.

### Task 9: Switch the maintainer's own Kodi

- Install Little Screen from the Pages repository on the maintainer's Kodi, carry over the
  settings (profiles, language filter, autoplay) and caches from `plugin.video.ytkids`, remove
  the old add-on, archive the private predecessor repository.
- Only while the Kodi is idle (nothing playing, nobody browsing for 15 minutes).
- Done when: the maintainer's profiles open in Little Screen and a video plays.

## Later

- Submission to the official Kodi repository (`xbmc/repo-plugins`) after v1 has run for a while.
