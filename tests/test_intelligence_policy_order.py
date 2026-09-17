from __future__ import annotations

import pytest

from marketlab.intelligence_robots import ConservativeRobotPolicy


@pytest.mark.parametrize("rule,target", [
    ("/private", "/private/report"), ("/secret*", "/secret/report"),
    ("/*?download=1$", "/report?download=1"),
])
def test_broad_allow_never_overrides_disallow(rule, target):
    parser = ConservativeRobotPolicy()
    parser.parse(["User-agent: *", "Allow: /", f"Disallow: {rule}"])
    assert parser.can_fetch("MarketLabResearch", "https://www.tcs.com" + target) is False
