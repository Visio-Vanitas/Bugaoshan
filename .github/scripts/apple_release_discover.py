#!/usr/bin/env python3
"""Find the next upstream release that still needs Apple artifacts."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


MARKER_PREFIX = "apple-ci/testflight/"


class GitHubClient:
    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self.token = token
        self.api_url = api_url.rstrip("/")

    def get(self, path: str) -> Any:
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "bugaoshan-apple-release-sync",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def ref_exists(self, repository: str, ref: str) -> bool:
        encoded_ref = urllib.parse.quote(ref, safe="/")
        try:
            self.get(f"/repos/{repository}/git/ref/{encoded_ref}")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return False
            raise
        return True

    def release_assets(self, repository: str, tag: str) -> set[str]:
        encoded_tag = urllib.parse.quote(tag, safe="")
        try:
            release = self.get(f"/repos/{repository}/releases/tags/{encoded_tag}")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return set()
            raise
        return {asset["name"] for asset in release.get("assets", [])}


def release_asset_name(tag: str) -> str:
    version = tag[1:] if tag.startswith("v") else tag
    return f"bugaoshan_{version}_macos_arm64.dmg"


def release_work(
    client: GitHubClient,
    release: dict[str, Any],
    automation_repository: str,
    force: bool,
) -> dict[str, str] | None:
    tag = release["tag_name"]
    asset_name = release_asset_name(tag)
    assets = client.release_assets(automation_repository, tag)
    prerelease = bool(release.get("prerelease"))
    needs_dmg = force or asset_name not in assets
    marker = f"tags/{MARKER_PREFIX}{tag}"
    needs_ios = force or not client.ref_exists(automation_repository, marker)

    if not needs_dmg and not needs_ios:
        return None

    return {
        "found": "true",
        "tag": tag,
        "version": tag[1:] if tag.startswith("v") else tag,
        "release_id": str(release["id"]),
        "published_at": release.get("published_at") or "",
        "prerelease": str(prerelease).lower(),
        "asset_name": asset_name,
        "needs_dmg": str(needs_dmg).lower(),
        "needs_ios": str(needs_ios).lower(),
    }


def discover(
    client: GitHubClient,
    upstream_repository: str,
    automation_repository: str,
    baseline_id: int,
    manual_tag: str,
    force: bool,
) -> dict[str, str]:
    if manual_tag:
        encoded_tag = urllib.parse.quote(manual_tag, safe="")
        release = client.get(
            f"/repos/{upstream_repository}/releases/tags/{encoded_tag}"
        )
        if release.get("draft"):
            raise RuntimeError(f"{manual_tag} is still a draft release")
        return release_work(client, release, automation_repository, force) or {
            "found": "false"
        }

    releases: list[dict[str, Any]] = []
    for page in range(1, 6):
        batch = client.get(
            f"/repos/{upstream_repository}/releases?per_page=100&page={page}"
        )
        releases.extend(batch)
        if len(batch) < 100:
            break

    candidates = [
        release
        for release in releases
        if not release.get("draft") and int(release["id"]) > baseline_id
    ]
    candidates.sort(key=lambda release: (release.get("published_at") or "", release["id"]))

    for release in candidates:
        work = release_work(client, release, automation_repository, force=False)
        if work:
            return work
    return {"found": "false"}


def write_outputs(outputs: dict[str, str], output_path: str) -> None:
    lines = [f"{key}={value}" for key, value in outputs.items()]
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output_file:
            output_file.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--automation", required=True)
    parser.add_argument("--baseline-id", required=True, type=int)
    parser.add_argument("--tag", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    outputs = discover(
        GitHubClient(token, os.environ.get("GITHUB_API_URL", "https://api.github.com")),
        args.upstream,
        args.automation,
        args.baseline_id,
        args.tag,
        args.force,
    )
    write_outputs(outputs, args.github_output)


if __name__ == "__main__":
    main()
