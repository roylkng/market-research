"""Conservative robots evaluation: a matching Disallow vetoes a broad Allow.

urllib.robotparser uses first-match rules. The supplementary veto intentionally
may overblock more-specific Allow exceptions, rather than use them to override a
site restriction. This is not a claim of full RFC 9309 parser conformance.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit
from urllib.robotparser import RobotFileParser


class ConservativeRobotPolicy(RobotFileParser):
    def can_fetch(self, useragent, url):
        if not super().can_fetch(useragent, url):
            return False
        entries = [entry for entry in self.entries if entry.applies_to(useragent)]
        if not entries and self.default_entry is not None:
            entries = [self.default_entry]
        parsed = urlsplit(url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        for entry in entries:
            for rule in entry.rulelines:
                if rule.allowance:
                    continue
                pattern = unquote(rule.path)
                anchored = pattern.endswith("$")
                if anchored:
                    pattern = pattern[:-1]
                expression = "^" + ".*".join(re.escape(part) for part in pattern.split("*"))
                if anchored:
                    expression += "$"
                if re.search(expression, path) or re.search(expression, unquote(path)):
                    return False
        return True
