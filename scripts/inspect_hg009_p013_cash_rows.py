"""P013 original NSE FY26 source-row reconnaissance, no valuation side effects.

Read the previously SHA-attested ACE, ACUTAAS and TRAVELFOOD HTML from
the permanent Git archive. Print only the row labels and published amounts
needed to reconcile CFO with investing/financing cash. No new source calls.
"""
from __future__ import annotations

import gzip
import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p009_attestation import SOURCES

ROOT = Path(__file__).resolve().parents[1]
MATCH = re.compile(
    r"cash flow|net cash|cash and cash|investing activities|financing activities|"
    r"borrowings|loan|lease liabilit|interest paid|dividend paid|"
    r"fixed assets|property, plant|capital work|current investments|"
    r"purchase of investments|sale of investments|"
    r"investments in subsidiaries|acquisition|financ(ing|e) charges|"
    r"term deposits|bank deposits|cash equivalents|"
    r"net increase|decrease in cash|balance at end|balance at beginning",
    re.IGNORECASE,
)

def main() -> int:
    for symbol, pin in SOURCES.items():
        location = ROOT / "research/hg009/p008-originals" / symbol / (
            pin["raw_sha256"] + ".html.gz"
        )
        raw = gzip.decompress(location.read_bytes())
        if hashlib.sha256(raw).hexdigest() != pin["raw_sha256"]:
            raise AlphaContractError(f"P013 wrong original {symbol} NSE filing")
        soup = BeautifulSoup(raw, "html.parser")
        print(f"\n====== {symbol} ORIGINAL NSE CASH ROWS ======")
        count = 0
        for row in soup.find_all("tr"):
            if row.find("tr") is not None:
                continue
            cells = [
                " ".join(cell.get_text(" ", strip=True).split())
                for cell in row.find_all(["td", "th"], recursive=False)
            ]
            # NSE iXBRL has nested wrappers and a leftmost blank table cell;
            # inspect every direct cell and keep the row label/value together.
            joined = " || ".join(cells)
            if not cells or not MATCH.search(joined):
                continue
            print(joined[:650])
            count += 1
            if count >= 140:
                break
        print(f"SOURCE_ROWS_PRINTED={count}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
