"""L001 P025: issuer daily buyback cash-price and per-share NAV arithmetic.

Archive authentic buyback-2026.html bytes and actual capture UTC before any
cash reconstruction. Source averages are rounded two-decimal issuer quotes,
exclude brokerage/transaction charges, and are NOT a verified cash ledger.
All share/NAV effects are *counterfactual*, holding June30 issuer NAV fixed.
No current fleet valuation, legal October cancellation or alpha is inferred.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest

SOURCE_URL = "https://greatship.com/buyback-2026.html"
REPORT_ID = "L001-P025-GESHIP-ISSUER-ROUNDED-REPURCHASE-CASH-NAV-v1"
SOURCE_DIR = Path("research/l001/originals/geship_2026_buyback_table")
REPORT_PATH = Path("research/l001/l001-p025-geship-issuer-buyback-cash-nav-v1.json")
PINS = {
    "capital_bridge": (
        "research/l001/l001-p024-geship-buyback-capital-bridge-v1.json",
        "769514c9a271598c563ae54c4bebf3b36097a9ca",
        "report_sha256",
        "d9a3f3f50c583df53d1055e8a495b127647d324bc0c06a9457e2bd63107c2f44",
    ),
    "frontier": (
        "research/l001/l001-p023-value-falsification-frontier-v1.json",
        "dbcf91030ba488ba99d10287f45afead562da6a4",
        "report_sha256",
        "847f93a8cb6872a9c7a0a44049504617ea55c387bf3954edb532d3e97c05daef",
    ),
}
DATE_RE = re.compile(r"^(\d{2}) (Sep|Oct) 2026$")
FIRST_DATE = "04 Sep 2026"
LAST_DATE = "19 Oct 2026"
SEPT_LAST = "30 Sep 2026"
BEFORE_SHARES = 142_767_161
SEPT_EXTINGUISHED = 1_858_941
POST_SEPT_SHARES = 140_908_220
CUM_OCT19 = 3_095_660
JUNE_NAV_PER_OLD_SHARE = Decimal("1886")
OCT19_EQ_CLOSE = Decimal("1519.30")


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _utc(text: str) -> datetime:
    try:
        instant = datetime.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("P025 actual capture time invalid") from exc
    if instant.tzinfo is None:
        raise AlphaContractError("P025 actual capture clock must have offset")
    return instant.astimezone(UTC)


def _original_table(raw: bytes) -> list[dict[str, Any]]:
    if not raw or len(raw) > 2_000_000 or b"<" not in raw:
        raise AlphaContractError("P025 issuer HTML missing or oversized")
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    if (
        "buy back 2026" not in text
        or "great eastern" not in text and "greatship" not in text
        or "daily activity" not in text
        or "average acquisition price" not in text
        or "cumulative total" not in text
        or "excluding transaction" not in text
    ):
        raise AlphaContractError("P025 original issuer buyback page identity absent")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in tr.find_all(["td", "th"], recursive=False)
        ]
        if len(cells) < 4 or not DATE_RE.fullmatch(cells[0]):
            continue
        if len(cells) != 4:
            raise AlphaContractError("P025 issuer date row column count changed")
        day, quantity, price, cumulative = cells
        shares = int(quantity.replace(",", "")) if quantity else 0
        cum = int(cumulative.replace(",", ""))
        if shares < 0 or cum < 0 or not cumulative:
            raise AlphaContractError("P025 issuer negative buyback count")
        if shares:
            if not price:
                raise AlphaContractError("P025 issuer nonzero purchase lacks average")
            try:
                avg = Decimal(price.replace(",", ""))
            except Exception as exc:
                raise AlphaContractError("P025 issuer price not decimal") from exc
            if not avg.is_finite() or avg <= 0 or avg.as_tuple().exponent < -2:
                raise AlphaContractError("P025 issuer average precision invalid")
            average = str(avg.quantize(Decimal("0.01")))
        elif price.strip():
            raise AlphaContractError("P025 zero purchase assigned average")
        else:
            average = None
        from datetime import datetime as dt

        parsed = dt.strptime(day, "%d %b %Y").date().isoformat()
        rows.append({
            "date": parsed,
            "display_date": day,
            "shares_purchased": shares,
            "issuer_rounded_avg_inr_per_share": average,
            "issuer_cumulative_purchased": cum,
        })
    if (
        len(rows) != 30
        or rows[0]["display_date"] != FIRST_DATE
        or rows[-1]["display_date"] != LAST_DATE
        or [r["date"] for r in rows] != sorted(set(r["date"] for r in rows))
    ):
        raise AlphaContractError("P025 original issuer 30-day freeze is incomplete")
    running = 0
    for row in rows:
        running += row["shares_purchased"]
        if row["issuer_cumulative_purchased"] != running:
            raise AlphaContractError("P025 issuer daily and cumulative totals diverge")
    sep = next(r for r in rows if r["display_date"] == SEPT_LAST)
    if (
        sep["issuer_cumulative_purchased"] != SEPT_EXTINGUISHED
        or rows[-1]["issuer_cumulative_purchased"] != CUM_OCT19
    ):
        raise AlphaContractError("P025 original Sep vs Oct issuer purchases drift")
    return rows


def signed_capture(raw: bytes, *, observed_at_utc: str) -> dict[str, Any]:
    rows = _original_table(raw)
    stamp = _utc(observed_at_utc)
    if stamp < datetime(2026, 10, 19, tzinfo=UTC):
        raise AlphaContractError("P025 cannot first-see Oct19 table before publication")
    sha = hashlib.sha256(raw).hexdigest()
    output = {
        "schema_version": 1,
        "receipt_id": "L001-P025-ISSUER-BUYBACK-HTML-RECEIPT-v1",
        "original_issuer_url": SOURCE_URL,
        "source_sha256": sha,
        "source_size_bytes": len(raw),
        "actual_retrieval_utc": stamp.isoformat(),
        "original_issuer_raw_html_path": str(SOURCE_DIR / f"{sha}.html"),
        "last_issuer_daily_activity_date": LAST_DATE,
        "selected_issuer_report_rows": len(rows),
        "original_page_can_change_later": True,
        "publication_date_inferred_from_first_retrieval": False,
        "live_capital_allowed": False,
    }
    output["receipt_sha256"] = digest(output)
    return output


def validate_capture(receipt: dict[str, Any], raw: bytes) -> None:
    unsigned = copy.deepcopy(receipt)
    if unsigned.pop("receipt_sha256", None) != digest(unsigned):
        raise AlphaContractError("P025 source receipt hash changed")
    if receipt != signed_capture(raw, observed_at_utc=receipt["actual_retrieval_utc"]):
        raise AlphaContractError("P025 issuer original HTML differs from receipt")


def pinned_prior_sources(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    contents, refs = {}, {}
    for key, (path, git_blob, field, expected) in PINS.items():
        raw = (root / path).read_bytes()
        if _blob(raw) != git_blob:
            raise AlphaContractError(f"P025 {key} prior git source changed")
        data = json.loads(raw)
        if data.get(field) != expected:
            raise AlphaContractError(f"P025 {key} original result hash drift")
        unsigned = copy.deepcopy(data)
        if unsigned.pop(field) != digest(unsigned):
            raise AlphaContractError(f"P025 {key} original signed report tampered")
        contents[key] = data
        refs[key] = {"original_repo_path": path, "git_blob_sha": git_blob,
                     "source_byte_sha256": hashlib.sha256(raw).hexdigest()}
    return contents, refs


def _money(rupees: Decimal) -> float:
    return float((rupees / Decimal("10000000")).quantize(Decimal("0.000001")))


def _rs(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def build_cash_nav_sensitivity(
    raw: bytes, receipt: dict[str, Any], prior: dict[str, dict],
    references: dict[str, dict],
) -> dict[str, Any]:
    validate_capture(receipt, raw)
    rows = _original_table(raw)
    cap = prior["capital_bridge"]
    frontier = next(x for x in prior["frontier"]["evidence"] if x["symbol"] == "GESHIP")
    if (
        cap["certified_paidup_shares_before_september_buyback"] != BEFORE_SHARES
        or cap["certified_september_shares_extinguished"] != SEPT_EXTINGUISHED
        or cap["certified_post_september_paidup_shares"] != POST_SEPT_SHARES
        or cap["oct19_issuer_report_total_cumulative_purchased"] != CUM_OCT19
        or cap["oct19_current_paidup_or_fully_diluted_shares_verified"] is not False
        or frontier["historical_issuer_nav_per_old_share_inr_not_marked_current"]
        != float(JUNE_NAV_PER_OLD_SHARE)
        or frontier["original_oct19_nse_eq_close_inr"] != float(OCT19_EQ_CLOSE)
    ):
        raise AlphaContractError("P025 reference certified share/NAV lineage differs")
    sep = [r for r in rows if r["date"] <= "2026-09-30"]
    octrows = [r for r in rows if r["date"] >= "2026-10-01"]
    calc = lambda items: sum(
        (Decimal(row["shares_purchased"]) * Decimal(
            row["issuer_rounded_avg_inr_per_share"] or "0"
        ) for row in items), Decimal(0)
    )
    sep_cash, oct_cash = calc(sep), calc(octrows)
    sep_count = sum(x["shares_purchased"] for x in sep)
    oct_count = sum(x["shares_purchased"] for x in octrows)
    if sep_count != SEPT_EXTINGUISHED or sep_count + oct_count != CUM_OCT19:
        raise AlphaContractError("P025 issuer rounded price-cash sums inconsistent")
    original_equity_rs = JUNE_NAV_PER_OLD_SHARE * BEFORE_SHARES
    after_sep = (original_equity_rs - sep_cash) / POST_SEPT_SHARES
    fully_cancelled = (original_equity_rs-sep_cash-oct_cash) / (
        POST_SEPT_SHARES-oct_count
    )
    if not (JUNE_NAV_PER_OLD_SHARE <= after_sep <= fully_cancelled):
        raise AlphaContractError("P025 counterfactual NAV accretion arithmetic drift")
    packet = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "as_of": "2026-10-21",
        "actual_source_capture_utc": receipt["actual_retrieval_utc"],
        "issuer_page_receipt_sha256": receipt["receipt_sha256"],
        "issuer_rounded_daily_source_sha256": receipt["source_sha256"],
        "source_can_be_replaced_on_issuer_site": True,
        "input_legal_share_and_NAV_sources": references,
        "sep_buyback_rounded_daily_purchased_shares": sep_count,
        "sep_estimated_cash_spend_cr_excluding_fees": _money(sep_cash),
        "oct_to_19th_rounded_daily_purchased_shares": oct_count,
        "oct_to_19th_estimated_cash_spend_cr_excluding_fees": _money(oct_cash),
        "cumulative_rounded_daily_purchased_shares": sep_count+oct_count,
        "cumulative_estimated_cash_spend_cr_excluding_fees": _money(sep_cash+oct_cash),
        "sept_buyback_shares_legally_certified_extinguished": SEPT_EXTINGUISHED,
        "oct19_later_legally_extinguished_shares_verified": False,
        "current_actual_parent_diluted_shares": None,
        "june_2026_reported_NAV_inr_per_old_share_not_current": float(JUNE_NAV_PER_OLD_SHARE),
        "oct19_original_close_inr_not_a_fill": float(OCT19_EQ_CLOSE),
        "only_counterfactual_const_NAV_no_other_cash_change": {
            "sep_only_if_all_first_lot_legally_cancelled_inr": _rs(after_sep),
            "sept_increment_inr_per_share_not_observed": _rs(
                after_sep-JUNE_NAV_PER_OLD_SHARE
            ),
            "sept_increment_percent_of_original_nav_not_return": _rs(
                100*(after_sep/JUNE_NAV_PER_OLD_SHARE-1)
            ),
            "if_oct_extra_also_legally_cancelled_inr": _rs(fully_cancelled),
            "full_sep_oct_increment_inr_per_share_not_observed": _rs(
                fully_cancelled-JUNE_NAV_PER_OLD_SHARE
            ),
            "full_sep_oct_increment_percent_not_return": _rs(
                100*(fully_cancelled/JUNE_NAV_PER_OLD_SHARE-1)
            ),
        },
        "purchased_not_necessarily_legally_extinguished": True,
        "rounded_price_products_are_not_actual_settlement_cash": True,
        "transaction_brokerage_fees_and_taxes_excluded": True,
        "NAV_source_is_from_june_not_october_current": True,
        "updated_fleet_asset_prices_and_liabilities_reconciled": False,
        "investment_expected_return": None,
        "current_equity_margin_of_safety_verified": False,
        "live_capital_allowed": False,
    }
    packet["report_sha256"] = digest(packet)
    return packet


def validate_cash_nav_result(
    packet: dict[str, Any], *, raw: bytes, receipt: dict[str, Any],
    prior: dict[str, dict], references: dict[str, dict],
) -> None:
    unsigned = copy.deepcopy(packet)
    if unsigned.pop("report_sha256", None) != digest(unsigned):
        raise AlphaContractError("P025 archived NAV-sensitivity report modified")
    if packet != build_cash_nav_sensitivity(raw, receipt, prior, references):
        raise AlphaContractError("P025 archived source arithmetic not reproducible")
