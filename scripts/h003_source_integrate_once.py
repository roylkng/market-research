from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"patch target not found in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/marketlab/nse.py",
    '''    CORPORATE_ACTION_ENDPOINT = NSEEndpoint(
        "corporate_actions", f"{BASE_URL}/api/corporates-corporateActions"
    )
''',
    '''    CORPORATE_ACTION_ENDPOINT = NSEEndpoint(
        "corporate_actions", f"{BASE_URL}/api/corporates-corporateActions"
    )
    CORPORATE_ANNOUNCEMENT_ENDPOINT = NSEEndpoint(
        "corporate_announcements", f"{BASE_URL}/api/corporate-announcements"
    )
''',
)

replace_once(
    "src/marketlab/nse.py",
    '''    def archive_bytes(self, url: str) -> bytes:
''',
    '''    def corporate_announcements_with_raw(
        self,
        symbol: str,
        *,
        from_date: str,
        to_date: str,
    ) -> tuple[JSONPayload, bytes]:
        """Fetch exact NSE announcement discovery bytes for one equity symbol."""
        return self._json_get_with_raw(
            self.CORPORATE_ANNOUNCEMENT_ENDPOINT,
            params={
                "index": "equities",
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    def archive_bytes(self, url: str) -> bytes:
''',
)

p = Path("src/marketlab/h003_sources.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "from urllib.parse import urlparse\n",
    "from urllib.parse import urlparse\nfrom zoneinfo import ZoneInfo\n",
    1,
)
text = text.replace(
    "from marketlab.preparation import _parse_exchange_timestamp\n",
    "from marketlab.preparation import PreparationError, _parse_exchange_timestamp\n",
    1,
)
text = text.replace(
    "ALLOWED_ATTACHMENT_HOSTS = frozenset(",
    'IST = ZoneInfo("Asia/Kolkata")\nALLOWED_ATTACHMENT_HOSTS = frozenset(',
    1,
)
text = text.replace(
    "        except (TypeError, ValueError) as exc:\n            last_error = exc\n",
    "        except PreparationError as exc:\n            last_error = exc\n",
    1,
)
text = text.replace(
    "        published_date = published.astimezone(UTC).date()\n",
    "        published_date = published.astimezone(IST).date()\n",
    1,
)
text = text.replace(
    '''    if any(token in text for token in EXCLUDE_ANY):
        return False
    return True
''',
    '''    return not any(token in text for token in EXCLUDE_ANY)
''',
    1,
)
p.write_text(text, encoding="utf-8")

replace_once(
    "Makefile",
    '''\t$(PYTHON) -c "from marketlab.prospective import load_and_validate_runner_rule; d=load_and_validate_runner_rule('registry/h002_runner_rule.yaml'); print(f\\"H002 runner valid: {d['id']} sha256={d['sha256']}\\")"
''',
    '''\t$(PYTHON) -c "from marketlab.prospective import load_and_validate_runner_rule; d=load_and_validate_runner_rule('registry/h002_runner_rule.yaml'); print(f\\"H002 runner valid: {d['id']} sha256={d['sha256']}\\")"
\t$(PYTHON) -c "from marketlab.h003_sources import load_and_validate_source_rule; d=load_and_validate_source_rule('registry/h003_source_rule.yaml'); print(f\\"H003 source rule valid: {d['id']} sha256={d['sha256']}\\")"
''',
)
