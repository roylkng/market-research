from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup

PROVIDER_MARKER = "S&P Global Market Intelligence"
CURRENCY_RE = re.compile(r"\bFinancial currency(?: is|:)?\s*([A-Z]{3})\b", re.IGNORECASE)
FISCAL_YEAR_RE = re.compile(r"^FY\s*(\d{4})$", re.IGNORECASE)
MISSING_MARKERS = {"", "-", "--", "—", "N/A", "NA", "n/a"}


@dataclass(frozen=True)
class ParsedAnnualForecast:
    symbol: str
    fiscal_period: str
    period_ending: str
    consensus_eps: float
    eps_currency: str
    revenue_growth_forecast_pct: float | None
    analyst_count: int | None
    provider: str
    source_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def normalize_fiscal_period(value: str) -> str | None:
    match = FISCAL_YEAR_RE.fullmatch(_clean(value))
    if match is None:
        return None
    return f"FY{match.group(1)}"


def parse_period_ending(value: str) -> str | None:
    cleaned = _clean(value)
    if cleaned in MISSING_MARKERS:
        return None
    for pattern in ("%b %d, %Y", "%b %d %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> float | None:
    cleaned = _clean(value)
    if cleaned in MISSING_MARKERS:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()").replace(",", "").replace("₹", "").replace("$", "")
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return -parsed if negative else parsed


def _parse_percent(value: str) -> float | None:
    cleaned = _clean(value)
    if cleaned in MISSING_MARKERS:
        return None
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1]
    return _parse_float(cleaned)


def _parse_int(value: str) -> int | None:
    parsed = _parse_float(value)
    if parsed is None or not parsed.is_integer() or parsed < 0:
        return None
    return int(parsed)


def _row_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).strip()


def _table_rows(table) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for tr in table.find_all("tr"):
        cells = [_clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        key = _row_key(cells[0])
        if key and key not in rows:
            rows[key] = cells[1:]
    return rows


def _find_financial_rows(soup: BeautifulSoup) -> dict[str, list[str]]:
    required = {"fiscal year", "period ending", "eps", "revenue growth", "no analysts"}
    candidates: list[dict[str, list[str]]] = []
    for table in soup.find_all("table"):
        rows = _table_rows(table)
        if required.issubset(rows):
            candidates.append(rows)
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one annual financial forecast table; found {len(candidates)}"
        )
    return candidates[0]


def _extract_currency(page_text: str) -> str:
    match = CURRENCY_RE.search(page_text)
    if match is None:
        raise ValueError("financial forecast currency marker not found")
    return match.group(1).upper()


def _column_index(
    fiscal_values: list[str],
    period_values: list[str],
    expected_fiscal_period: str,
    expected_period_ending: str,
) -> int:
    matches: list[int] = []
    width = min(len(fiscal_values), len(period_values))
    for index in range(width):
        fiscal = normalize_fiscal_period(fiscal_values[index])
        period = parse_period_ending(period_values[index])
        if fiscal == expected_fiscal_period and period == expected_period_ending:
            matches.append(index)
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one matching annual forecast column for "
            f"{expected_fiscal_period}/{expected_period_ending}; found {len(matches)}"
        )
    return matches[0]


def _value_at(rows: dict[str, list[str]], key: str, index: int) -> str:
    values = rows[key]
    if index >= len(values):
        raise ValueError(f"forecast row {key!r} is shorter than target column")
    return values[index]


def parse_annual_forecast(
    *,
    symbol: str,
    source_url: str,
    html: bytes,
    expected_fiscal_period: str,
    expected_period_ending: str,
) -> ParsedAnnualForecast:
    if date.fromisoformat(expected_period_ending).isoformat() != expected_period_ending:
        raise ValueError("expected_period_ending must be canonical ISO YYYY-MM-DD")
    if normalize_fiscal_period(expected_fiscal_period) != expected_fiscal_period:
        raise ValueError("expected_fiscal_period must be canonical FYyyyy")

    soup = BeautifulSoup(html, "html.parser")
    page_text = _clean(soup.get_text(" ", strip=True))
    identity = f"NSE:{symbol}"
    if identity not in page_text:
        raise ValueError(f"page identity marker missing: {identity}")
    if PROVIDER_MARKER not in page_text:
        raise ValueError("S&P Global Market Intelligence provider marker missing")

    rows = _find_financial_rows(soup)
    index = _column_index(
        rows["fiscal year"],
        rows["period ending"],
        expected_fiscal_period,
        expected_period_ending,
    )
    eps = _parse_float(_value_at(rows, "eps", index))
    if eps is None:
        raise ValueError("target annual consensus EPS is unavailable or unparsable")

    revenue_growth = _parse_percent(_value_at(rows, "revenue growth", index))
    analyst_count = _parse_int(_value_at(rows, "no analysts", index))
    currency = _extract_currency(page_text)

    return ParsedAnnualForecast(
        symbol=symbol,
        fiscal_period=expected_fiscal_period,
        period_ending=expected_period_ending,
        consensus_eps=eps,
        eps_currency=currency,
        revenue_growth_forecast_pct=revenue_growth,
        analyst_count=analyst_count,
        provider=PROVIDER_MARKER,
        source_url=source_url,
    )
