import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "apple_release_discover.py"
SPEC = importlib.util.spec_from_file_location("apple_release_discover", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self, releases, existing_refs=()):
        self.releases = releases
        self.existing_refs = set(existing_refs)

    def get(self, path):
        if "/releases/tags/" in path:
            tag = path.rsplit("/", 1)[-1]
            return next(release for release in self.releases if release["tag_name"] == tag)
        if "/releases?" in path:
            return self.releases if "page=1" in path else []
        raise AssertionError(path)

    def ref_exists(self, repository, ref):
        return (repository, ref) in self.existing_refs


def release(release_id, tag, prerelease=False, assets=()):
    return {
        "id": release_id,
        "tag_name": tag,
        "draft": False,
        "prerelease": prerelease,
        "published_at": f"2026-08-{release_id:02d}T00:00:00Z",
        "assets": [{"name": name} for name in assets],
    }


class DiscoverTests(unittest.TestCase):
    def test_selects_oldest_pending_release_after_baseline(self):
        client = FakeClient([release(12, "v2.5.0"), release(11, "v2.4.0")])
        result = MODULE.discover(client, "upstream/repo", "owner/fork", 10, "", False)
        self.assertEqual(result["tag"], "v2.4.0")
        self.assertEqual(result["needs_dmg"], "true")
        self.assertEqual(result["needs_ios"], "true")

    def test_prerelease_never_uploads_testflight(self):
        client = FakeClient([release(11, "v2.4.0-rc1", prerelease=True)])
        result = MODULE.discover(client, "upstream/repo", "owner/fork", 10, "", False)
        self.assertEqual(result["needs_dmg"], "true")
        self.assertEqual(result["needs_ios"], "false")

    def test_completed_release_is_skipped(self):
        tag = "v2.4.0"
        asset = MODULE.release_asset_name(tag)
        client = FakeClient(
            [release(11, tag, assets=[asset])],
            {("owner/fork", f"tags/{MODULE.MARKER_PREFIX}{tag}")},
        )
        result = MODULE.discover(client, "upstream/repo", "owner/fork", 10, "", False)
        self.assertEqual(result, {"found": "false"})

    def test_promoted_prerelease_still_gets_testflight(self):
        tag = "v2.4.0"
        asset = MODULE.release_asset_name(tag)
        client = FakeClient([release(11, tag, prerelease=False, assets=[asset])])
        result = MODULE.discover(client, "upstream/repo", "owner/fork", 10, "", False)
        self.assertEqual(result["needs_dmg"], "false")
        self.assertEqual(result["needs_ios"], "true")

    def test_manual_force_rebuilds_both_stable_outputs(self):
        tag = "v2.4.0"
        asset = MODULE.release_asset_name(tag)
        client = FakeClient(
            [release(11, tag, assets=[asset])],
            {("owner/fork", f"tags/{MODULE.MARKER_PREFIX}{tag}")},
        )
        result = MODULE.discover(client, "upstream/repo", "owner/fork", 99, tag, True)
        self.assertEqual(result["needs_dmg"], "true")
        self.assertEqual(result["needs_ios"], "true")


if __name__ == "__main__":
    unittest.main()
