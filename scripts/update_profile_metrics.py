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
    COLORS["red_dark"],
    COLORS["red_bright"],
    COLORS["secondary"],
    COLORS["muted"],
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

        oldest_in_window = True
        for event in batch:
            created_raw = event.get("created_at")
            if not created_raw:
                continue
            created = dt.datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            if created >= cutoff:
                count += 1
            else:
                oldest_in_window = False

        if len(batch) < 100 or not oldest_in_window:
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
            # One repository should not blank the whole public profile.
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

    result: list[tuple[str, float]] = [
        (name, value / total_bytes * 100.0) for name, value in top
    ]
    if remainder:
        result.append(("Other", remainder / total_bytes * 100.0))
    return result


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def metric_card(x: int, label: str, value: str, width: int = 266) -> str:
    return f"""
      <g transform="translate({x} 0)">
        <rect width="{width}" height="102" rx="14" fill="url(#panel)" stroke="{COLORS['border']}"/>
        <rect width="5" height="102" rx="2.5" fill="{COLORS['red']}"/>
        <text x="22" y="29" fill="{COLORS['muted']}" font-size="11" letter-spacing="1.2">{esc(label)}</text>
        <text x="22" y="72" fill="{COLORS['strong']}" font-size="34" font-weight="700">{esc(value)}</text>
      </g>"""


def metric_card_mobile(x: int, y: int, label: str, value: str, width: int) -> str:
    return f"""
      <g transform="translate({x} {y})">
        <rect width="{width}" height="118" rx="14" fill="url(#panel)" stroke="{COLORS['border']}"/>
        <rect width="6" height="118" rx="3" fill="{COLORS['red']}"/>
        <text x="22" y="34" fill="{COLORS['muted']}" font-size="12" letter-spacing="1.05">{esc(label)}</text>
        <text x="22" y="83" fill="{COLORS['strong']}" font-size="38" font-weight="700">{esc(value)}</text>
      </g>"""


def language_track(
    mix: list[tuple[str, float]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[str, list[tuple[str, float, str]]]:
    if not mix:
        return (
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'rx="{height / 2:g}" fill="{COLORS["border"]}"/>',
            [],
        )

    pieces = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{height / 2:g}" fill="{COLORS["border"]}"/>'
    ]
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
            f'height="{height}" fill="{color}"/>'
        )
        rendered.append((name, percentage, color))
        cursor += segment_width

    return "\n      ".join(pieces), rendered


def render_desktop(
    public_repos: str,
    followers: str,
    stars: str,
    events: str,
    mix: list[tuple[str, float]],
    updated: str,
) -> str:
    track, legend = language_track(mix, 0, 18, 1124, 12)

    if legend:
        legend_parts = []
        x = 0
        for name, percentage, color in legend:
            legend_parts.append(
                f'<circle cx="{x + 5}" cy="57" r="5" fill="{color}"/>'
                f'<text x="{x + 18}" y="62" fill="{COLORS["secondary"]}" '
                f'font-size="13">{esc(name)} · {percentage:.1f}%</text>'
            )
            x += 210
        code_mix_text = "\n      ".join(legend_parts)
    else:
        code_mix_text = (
            f'<text x="0" y="58" fill="{COLORS["secondary"]}" font-size="14">'
            "No public code repositories indexed yet. Profile repository is excluded."
            "</text>"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360" role="img" aria-labelledby="title desc">
  <title id="title">VAGTechNL GitHub telemetry</title>
  <desc id="desc">Daily refreshed public GitHub profile metrics.</desc>
  <defs>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{COLORS['panel']}"/>
      <stop offset="1" stop-color="{COLORS['card']}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="360" rx="24" fill="{COLORS['canvas']}"/>
  <rect x="1" y="1" width="1198" height="358" rx="23" fill="none" stroke="{COLORS['border']}" stroke-width="2"/>

  <g transform="translate(38 32)" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">
    <text x="0" y="0" fill="{COLORS['muted']}" font-size="12" letter-spacing="1.8">LIVE GITHUB SIGNAL</text>
    <text x="0" y="31" fill="{COLORS['strong']}" font-size="24" font-weight="700">Public profile telemetry</text>
    <text x="0" y="55" fill="{COLORS['secondary']}" font-size="14">Refreshed daily by GitHub Actions · public data only.</text>

    <g transform="translate(0 82)">
{metric_card(0, "PUBLIC REPOS", public_repos)}
{metric_card(286, "FOLLOWERS", followers)}
{metric_card(572, "TOTAL STARS", stars)}
{metric_card(858, "PUBLIC EVENTS · 30D", events)}
    </g>

    <g transform="translate(0 214)">
      <text x="0" y="0" fill="{COLORS['muted']}" font-size="11" letter-spacing="1.2">PUBLIC CODE MIX</text>
      {track}
      {code_mix_text}
      <path d="M0 78H1124" stroke="{COLORS['border']}"/>
      <text x="0" y="105" fill="{COLORS['muted']}" font-size="11">SOURCE · GitHub public API</text>
      <text x="1124" y="105" fill="{COLORS['muted']}" font-size="11" text-anchor="end">UPDATED · {esc(updated)}</text>
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
    track, legend = language_track(mix, 0, 20, 576, 14)

    if legend:
        legend_parts = []
        positions = [(0, 70), (288, 70), (0, 98), (288, 98), (0, 126)]
        for (name, percentage, color), (x, y) in zip(legend, positions):
            legend_parts.append(
                f'<circle cx="{x + 6}" cy="{y - 5}" r="5" fill="{color}"/>'
                f'<text x="{x + 20}" y="{y}" fill="{COLORS["secondary"]}" '
                f'font-size="13">{esc(name)} · {percentage:.1f}%</text>'
            )
        code_mix_text = "\n      ".join(legend_parts)
        divider_y = 150
        source_y = 181
        updated_y = 208
    else:
        code_mix_text = (
            f'<text x="0" y="70" fill="{COLORS["secondary"]}" font-size="14">'
            "No public code repositories indexed yet."
            "</text>"
            f'<text x="0" y="94" fill="{COLORS["muted"]}" font-size="12">'
            "Profile repository excluded from code mix."
            "</text>"
        )
        divider_y = 120
        source_y = 151
        updated_y = 178

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="650" viewBox="0 0 640 650" role="img" aria-labelledby="title desc">
  <title id="title">VAGTechNL GitHub telemetry</title>
  <desc id="desc">Mobile daily refreshed public GitHub profile metrics.</desc>
  <defs>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{COLORS['panel']}"/>
      <stop offset="1" stop-color="{COLORS['card']}"/>
    </linearGradient>
  </defs>
  <rect width="640" height="650" rx="24" fill="{COLORS['canvas']}"/>
  <rect x="1" y="1" width="638" height="648" rx="23" fill="none" stroke="{COLORS['border']}" stroke-width="2"/>

  <g transform="translate(32 32)" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">
    <text x="0" y="0" fill="{COLORS['muted']}" font-size="13" letter-spacing="1.8">LIVE GITHUB SIGNAL</text>
    <text x="0" y="37" fill="{COLORS['strong']}" font-size="27" font-weight="700">Public profile telemetry</text>
    <text x="0" y="66" fill="{COLORS['secondary']}" font-size="15">Daily refresh · public data only.</text>

    <g transform="translate(0 98)">
{metric_card_mobile(0, 0, "PUBLIC REPOS", public_repos, 270)}
{metric_card_mobile(286, 0, "FOLLOWERS", followers, 290)}
{metric_card_mobile(0, 134, "TOTAL STARS", stars, 270)}
{metric_card_mobile(286, 134, "PUBLIC EVENTS · 30D", events, 290)}
    </g>

    <g transform="translate(0 380)">
      <text x="0" y="0" fill="{COLORS['muted']}" font-size="12" letter-spacing="1.2">PUBLIC CODE MIX</text>
      {track}
      {code_mix_text}
      <path d="M0 {divider_y}H576" stroke="{COLORS['border']}"/>
      <text x="0" y="{source_y}" fill="{COLORS['muted']}" font-size="11">SOURCE · GitHub public API</text>
      <text x="0" y="{updated_y}" fill="{COLORS['muted']}" font-size="11">UPDATED · {esc(updated)}</text>
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
