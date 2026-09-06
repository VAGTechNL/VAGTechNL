#!/usr/bin/env python3
"""Generate VAGTechNL public GitHub profile telemetry SVGs.

Only public GitHub endpoints are queried. The profile repository itself is
excluded from the language mix so profile tooling does not skew code telemetry.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"
LOGIN = os.environ.get("PROFILE_LOGIN", "VAGTechNL")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR = Path("assets")

COLORS = {
    "canvas": "#07080B",
    "panel": "#0D0F13",
    "card": "#14171C",
    "border": "#1C2026",
    "active": "#252A32",
    "primary": "#E6E8EB",
    "secondary": "#A7ADB7",
    "muted": "#6F7682",
    "strong": "#FFFFFF",
    "red": "#E10600",
    "red_dark": "#B80500",
    "red_bright": "#FF2A23",
}

LANGUAGE_COLORS = [
    COLORS["red"],
    COLORS["red_bright"],
    COLORS["secondary"],
    COLORS["muted"],
    COLORS["active"],
]


def request_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "VAGTechNL-profile-metrics",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub API request failed: {url}") from exc


def fetch_profile() -> dict[str, Any]:
    return request_json(f"{API}/users/{quote(LOGIN)}")


def fetch_public_repos() -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = request_json(
            f"{API}/users/{quote(LOGIN)}/repos"
            f"?per_page=100&type=owner&sort=updated&page={page}"
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected repositories response")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch_public_events_30d(now: dt.datetime) -> str:
    cutoff = now - dt.timedelta(days=30)
    count = 0
    capped = False

    for page in range(1, 4):
        batch = request_json(
            f"{API}/users/{quote(LOGIN)}/events/public?per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected public events response")
        if not batch:
            break

        all_in_window = True
        for event in batch:
            created_raw = event.get("created_at")
            if not created_raw:
                continue
            created = dt.datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            if created >= cutoff:
                count += 1
            else:
                all_in_window = False

        if len(batch) < 100 or not all_in_window:
            break
        if page == 3:
            capped = True

    return f"{count}+" if capped else str(count)


def fetch_language_mix(repos: list[dict[str, Any]]) -> list[tuple[str, float]]:
    totals: dict[str, int] = {}

    for repo in repos:
        name = str(repo.get("name", ""))
        if (
            not name
            or repo.get("fork")
            or repo.get("archived")
            or name.casefold() == LOGIN.casefold()
        ):
            continue

        languages_url = repo.get("languages_url")
        if not languages_url:
            continue

        try:
            language_data = request_json(str(languages_url))
        except RuntimeError:
            continue

        if not isinstance(language_data, dict):
            continue

        for language, byte_count in language_data.items():
            if isinstance(byte_count, int) and byte_count > 0:
                totals[language] = totals.get(language, 0) + byte_count

    total_bytes = sum(totals.values())
    if total_bytes <= 0:
        return []

    ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    top = ordered[:4]
    remainder = sum(value for _, value in ordered[4:])

    result = [(name, value / total_bytes * 100.0) for name, value in top]
    if remainder:
        result.append(("Other", remainder / total_bytes * 100.0))
    return result


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def live_indicator(x: int, y: int) -> str:
    return f"""
      <g transform="translate({x} {y})" class="signal-motion">
        <circle cx="0" cy="0" r="4" fill="{COLORS['red_bright']}" opacity=".90"/>
        <circle cx="0" cy="0" r="4" fill="none" stroke="{COLORS['red_bright']}" stroke-width="1.2" opacity="0">
          <animate attributeName="r" dur="5.5s" repeatCount="indefinite" values="4;4;11;14" keyTimes="0;.15;.32;1"/>
          <animate attributeName="opacity" dur="5.5s" repeatCount="indefinite" values="0;.28;.12;0" keyTimes="0;.15;.32;1"/>
        </circle>
      </g>"""


def metric_card(x: int, label: str, value: str, width: int = 266) -> str:
    return f"""
      <g transform="translate({x} 0)">
        <rect width="{width}" height="96" rx="14" fill="url(#card)" stroke="{COLORS['border']}"/>
        <path d="M18 1H54" stroke="{COLORS['red']}" stroke-width="2" stroke-linecap="round" opacity=".90"/>
        <circle cx="22" cy="28" r="3" fill="{COLORS['red_bright']}" opacity=".75"/>
        <text x="34" y="32" class="mono" fill="{COLORS['muted']}" font-size="10.5" letter-spacing="1.15">{esc(label)}</text>
        <text x="20" y="72" fill="{COLORS['strong']}" font-size="31" font-weight="760">{esc(value)}</text>
      </g>"""


def metric_card_mobile(
    x: int,
    y: int,
    label: str,
    value: str,
    width: int,
) -> str:
    return f"""
      <g transform="translate({x} {y})">
        <rect width="{width}" height="112" rx="15" fill="url(#card)" stroke="{COLORS['border']}"/>
        <path d="M18 1H58" stroke="{COLORS['red']}" stroke-width="2" stroke-linecap="round" opacity=".90"/>
        <circle cx="22" cy="32" r="3" fill="{COLORS['red_bright']}" opacity=".75"/>
        <text x="34" y="36" class="mono" fill="{COLORS['muted']}" font-size="11" letter-spacing="1.05">{esc(label)}</text>
        <text x="20" y="84" fill="{COLORS['strong']}" font-size="36" font-weight="760">{esc(value)}</text>
      </g>"""


def language_track(
    mix: list[tuple[str, float]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[str, list[tuple[str, float, str]]]:
    base = (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{height / 2:g}" fill="{COLORS["border"]}"/>'
    )
    if not mix:
        shimmer = f"""
      <rect x="{x}" y="{y}" width="72" height="{height}" rx="{height / 2:g}" fill="{COLORS['active']}" opacity=".7" class="signal-motion">
        <animate attributeName="x" dur="7s" repeatCount="indefinite" values="{x};{x + width - 72};{x}" keyTimes="0;.5;1"/>
        <animate attributeName="opacity" dur="7s" repeatCount="indefinite" values=".18;.48;.18" keyTimes="0;.5;1"/>
      </rect>"""
        return base + shimmer, []

    pieces = [base]
    cursor = float(x)
    rendered: list[tuple[str, float, str]] = []

    for index, (name, percentage) in enumerate(mix):
        color = LANGUAGE_COLORS[index % len(LANGUAGE_COLORS)]
        segment_width = width * percentage / 100.0
        if index == len(mix) - 1:
            segment_width = x + width - cursor
        if segment_width <= 0:
            continue
        pieces.append(
            f'<rect x="{cursor:.2f}" y="{y}" width="{segment_width:.2f}" '
            f'height="{height}" rx="{height / 2:g}" fill="{color}"/>'
        )
        rendered.append((name, percentage, color))
        cursor += segment_width

    return "\n      ".join(pieces), rendered


def code_mix_desktop(mix: list[tuple[str, float]]) -> tuple[str, str]:
    track, legend = language_track(mix, 0, 22, 1124, 8)
    if not legend:
        copy = f"""
      <text x="0" y="60" fill="{COLORS['primary']}" font-size="13.5">No public code repositories yet.</text>
      <text x="0" y="82" class="mono" fill="{COLORS['muted']}" font-size="10.5">PROFILE REPOSITORY EXCLUDED · MIX STARTS AUTOMATICALLY WITH THE NEXT PUBLIC CODE REPO</text>"""
        return track, copy

    legend_parts = []
    x = 0
    for name, percentage, color in legend:
        legend_parts.append(
            f'<circle cx="{x + 4}" cy="63" r="4" fill="{color}"/>'
            f'<text x="{x + 16}" y="67" fill="{COLORS["secondary"]}" font-size="12.5">'
            f'{esc(name)} · {percentage:.1f}%</text>'
        )
        x += 205
    return track, "\n      ".join(legend_parts)


def code_mix_mobile(mix: list[tuple[str, float]]) -> tuple[str, str, int]:
    track, legend = language_track(mix, 0, 22, 576, 9)
    if not legend:
        copy = f"""
      <text x="0" y="68" fill="{COLORS['primary']}" font-size="14">No public code repositories yet.</text>
      <text x="0" y="93" class="mono" fill="{COLORS['muted']}" font-size="10.5">PROFILE REPO EXCLUDED · AUTO-STARTS WITH THE NEXT PUBLIC CODE REPO</text>"""
        return track, copy, 120

    positions = [(0, 70), (288, 70), (0, 99), (288, 99), (0, 128)]
    legend_parts = []
    for (name, percentage, color), (x, y) in zip(legend, positions):
        legend_parts.append(
            f'<circle cx="{x + 5}" cy="{y - 5}" r="4" fill="{color}"/>'
            f'<text x="{x + 17}" y="{y}" fill="{COLORS["secondary"]}" font-size="12.5">'
            f'{esc(name)} · {percentage:.1f}%</text>'
        )
    return track, "\n      ".join(legend_parts), 150


def render_desktop(
    public_repos: str,
    followers: str,
    stars: str,
    events: str,
    mix: list[tuple[str, float]],
    updated: str,
) -> str:
    track, code_mix = code_mix_desktop(mix)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360" role="img" aria-labelledby="title desc">
  <title id="title">VAGTechNL GitHub telemetry</title>
  <desc id="desc">Daily refreshed public GitHub profile metrics.</desc>
  <defs>
    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{COLORS['canvas']}"/>
      <stop offset="1" stop-color="{COLORS['panel']}"/>
    </linearGradient>
    <linearGradient id="card" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{COLORS['panel']}"/>
      <stop offset="1" stop-color="{COLORS['card']}"/>
    </linearGradient>
    <style>
      .sans{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
      .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
      @media (prefers-reduced-motion: reduce){{.signal-motion{{display:none}}}}
    </style>
  </defs>

  <rect width="1200" height="360" rx="24" fill="url(#surface)"/>
  <rect x="1" y="1" width="1198" height="358" rx="23" fill="none" stroke="{COLORS['border']}" stroke-width="2"/>
  <path d="M38 1H150" stroke="{COLORS['red']}" stroke-width="2" stroke-linecap="round" opacity=".72"/>

  <g transform="translate(38 30)" class="sans">
    {live_indicator(4, 4)}
    <text x="18" y="8" class="mono" fill="{COLORS['muted']}" font-size="11" letter-spacing="1.65">PUBLIC GITHUB SIGNAL</text>
    <text x="0" y="43" fill="{COLORS['strong']}" font-size="23" font-weight="760">Profile telemetry</text>
    <text x="0" y="67" fill="{COLORS['secondary']}" font-size="13.5">Daily public snapshot · generated by GitHub Actions</text>

    <g transform="translate(0 91)">
      {metric_card(0, "PUBLIC REPOS", public_repos)}
      {metric_card(286, "FOLLOWERS", followers)}
      {metric_card(572, "TOTAL STARS", stars)}
      {metric_card(858, "PUBLIC EVENTS · 30D", events)}
    </g>

    <g transform="translate(0 217)">
      <text x="0" y="0" class="mono" fill="{COLORS['muted']}" font-size="10.5" letter-spacing="1.15">PUBLIC CODE MIX</text>
      <text x="1124" y="0" class="mono" fill="{COLORS['muted']}" font-size="10" text-anchor="end">PROFILE REPO EXCLUDED</text>
      {track}
      {code_mix}

      <path d="M0 96H1124" stroke="{COLORS['border']}"/>
      <text x="0" y="121" class="mono" fill="{COLORS['muted']}" font-size="10">GITHUB PUBLIC API · DAILY 04:23 UTC</text>
      <text x="1124" y="121" class="mono" fill="{COLORS['muted']}" font-size="10" text-anchor="end">UPDATED · {esc(updated)}</text>
    </g>
  </g>
</svg>"""


def render_mobile(
    public_repos: str,
    followers: str,
    stars: str,
    events: str,
    mix: list[tuple[str, float]],
    updated: str,
) -> str:
    track, code_mix, divider_y = code_mix_mobile(mix)
    source_y = divider_y + 27
    updated_y = source_y + 24
    total_height = max(650, 430 + updated_y + 28)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{total_height}" viewBox="0 0 640 {total_height}" role="img" aria-labelledby="title desc">
  <title id="title">VAGTechNL GitHub telemetry</title>
  <desc id="desc">Mobile daily refreshed public GitHub profile metrics.</desc>
  <defs>
    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{COLORS['canvas']}"/>
      <stop offset="1" stop-color="{COLORS['panel']}"/>
    </linearGradient>
    <linearGradient id="card" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{COLORS['panel']}"/>
      <stop offset="1" stop-color="{COLORS['card']}"/>
    </linearGradient>
    <style>
      .sans{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
      .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
      @media (prefers-reduced-motion: reduce){{.signal-motion{{display:none}}}}
    </style>
  </defs>

  <rect width="640" height="{total_height}" rx="24" fill="url(#surface)"/>
  <rect x="1" y="1" width="638" height="{total_height - 2}" rx="23" fill="none" stroke="{COLORS['border']}" stroke-width="2"/>
  <path d="M32 1H132" stroke="{COLORS['red']}" stroke-width="2" stroke-linecap="round" opacity=".72"/>

  <g transform="translate(32 30)" class="sans">
    {live_indicator(4, 4)}
    <text x="18" y="8" class="mono" fill="{COLORS['muted']}" font-size="12" letter-spacing="1.55">PUBLIC GITHUB SIGNAL</text>
    <text x="0" y="47" fill="{COLORS['strong']}" font-size="28" font-weight="760">Profile telemetry</text>
    <text x="0" y="76" fill="{COLORS['secondary']}" font-size="15">Daily public snapshot · GitHub Actions</text>

    <g transform="translate(0 108)">
      {metric_card_mobile(0, 0, "PUBLIC REPOS", public_repos, 272)}
      {metric_card_mobile(288, 0, "FOLLOWERS", followers, 288)}
      {metric_card_mobile(0, 130, "TOTAL STARS", stars, 272)}
      {metric_card_mobile(288, 130, "PUBLIC EVENTS · 30D", events, 288)}
    </g>

    <g transform="translate(0 384)">
      <text x="0" y="0" class="mono" fill="{COLORS['muted']}" font-size="11" letter-spacing="1.1">PUBLIC CODE MIX</text>
      <text x="576" y="0" class="mono" fill="{COLORS['muted']}" font-size="10" text-anchor="end">PROFILE REPO EXCLUDED</text>
      {track}
      {code_mix}

      <path d="M0 {divider_y}H576" stroke="{COLORS['border']}"/>
      <text x="0" y="{source_y}" class="mono" fill="{COLORS['muted']}" font-size="10">GITHUB PUBLIC API · DAILY 04:23 UTC</text>
      <text x="0" y="{updated_y}" class="mono" fill="{COLORS['muted']}" font-size="10">UPDATED · {esc(updated)}</text>
    </g>
  </g>
</svg>"""


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    profile = fetch_profile()
    repos = fetch_public_repos()

    public_repos = str(profile.get("public_repos", len(repos)))
    followers = str(profile.get("followers", "—"))
    stars = str(sum(int(repo.get("stargazers_count", 0)) for repo in repos))
    events = fetch_public_events_30d(now)
    mix = fetch_language_mix(repos)
    updated = now.strftime("%Y-%m-%d %H:%M UTC")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.svg").write_text(
        render_desktop(public_repos, followers, stars, events, mix, updated),
        encoding="utf-8",
    )
    (OUT_DIR / "metrics-mobile.svg").write_text(
        render_mobile(public_repos, followers, stars, events, mix, updated),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
