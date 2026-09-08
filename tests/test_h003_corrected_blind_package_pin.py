from __future__ import annotations

import json
from pathlib import Path

from marketlab.h003_review_batches import BLIND_PACKAGE_SHA256, validate_source_document

CURRENT_PACKAGE_SHA256 = "70240c328f1812866b53e97f94b867335eb668f37918e952223d17f9e3fa9b24"
INVALIDATED_PACKAGE_SHA256S = {
    "a94a99c8f5fbad4aa0c5409f47362543cec879d07ec8a8006a8937c38bcfdb01",
    "a21efa55f8d72f3d2ac6ceef56d57b9897232f25f2e4c8f13d6449481ad77cfb",
}
ROOT = Path("research/prospective/h003/FY27-Q2-2026-09-06/outcomes-o001")


def test_sharder_is_pinned_to_current_contact_scrubbed_package() -> None:
    package = json.loads((ROOT / "blind-packets.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert BLIND_PACKAGE_SHA256 == CURRENT_PACKAGE_SHA256
    assert BLIND_PACKAGE_SHA256 not in INVALIDATED_PACKAGE_SHA256S
    assert package["package_sha256"] == CURRENT_PACKAGE_SHA256
    assert manifest["blind_package_sha256"] == CURRENT_PACKAGE_SHA256
    assert len(validate_source_document(package, manifest)) == 869
