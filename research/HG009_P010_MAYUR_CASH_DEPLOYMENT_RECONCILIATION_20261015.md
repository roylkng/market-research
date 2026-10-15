# HG009 P010: MAYURUNIQ cash deployment, not just headline FCF

**Source observed:** original NSE FY26 audited consolidated iXBRL for March 31, 2026, first retained local source capture at 2026-10-14T19:33:58Z.  
**Research date:** October 15, 2026.  
**Scientific purpose:** independent cash-flow arithmetic and source-byte custody, **not** an equity valuation or prediction.

Source: [Mayur Uniquoters Ltd original NSE FY26 iXBRL](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_159322_20052026182510_iXBRL_WEB.html). P003 originally captured only CFO minus PPE, leaving substantial long-term asset movements unaddressed. P009 independently archived multiple original HTML variants. P010 now verifies **one explicitly pinned first retained source version** against its signed Git receipt and exact original NSE table rows. A different retrieved HTML SHA is never silently accepted as equivalent.

## Cash-use reconciliation, ₹ crore

| Original FY26 consolidated cash-flow line | FY26 |
|---|---:|
| Reported net operating cash inflow | +133.1527 |
| Cash purchase of property, plant and equipment | -24.2071 |
| **CFO after cash spent on PPE** | **+108.9456** |
| Cash purchase of other long-term assets | -266.2441 |
| Proceeds from sale of other long-term assets | +160.3842 |
| **Net cash placement into other long-term assets** | **-105.8599** |
| **CFO minus PPE and net other long-term-asset placement** | **+3.0857** |
| Reported total net investing cash outflow | -115.0471 |
| **CFO + full net investing cash** | **+18.1056** |
| Reported total net financing cash outflow | -23.7729 |
| **Net cash change before FX** | **-5.6673** |
| FX effect | +1.7020 |
| **Reported net cash change after FX** | **-3.9653** |
| Cash beginning FY26 | 83.1003 |
| Cash ending FY26 | 79.1350 |

The arithmetic exactly reconciles to the filing cash statement. Its **₹3.0857 crore residual is NOT owner free cash flow**. Net purchases of other long-term assets may be investments or deposits with future realization, and not permanent operating consumption. Conversely, mechanically calling ₹108.9456 crore "FCF" while ignoring a cash deployment of ₹105.8599 crore is financially misleading.

Balance-sheet proof of asset presence, not shareholder liquidity: FY26 **current investments ₹176.8723 crore**, **noncurrent investments ₹108.0728 crore**, and **deposits with maturity beyond 12 months ₹73.55 crore**. Those fields do not prove which assets were acquired with the year's long-term-asset flows, their encumbrance, minority claims, credit quality, recoverability, future yield, or distributability.

P010 pinpoints three tasks necessary before a MAYURUNIQ per-share intrinsic valuation:

1. Find original FY25-to-FY26 **investment and deposit roll-forward** that reconciles the ₹266.2441 crore purchases and ₹160.3842 crore redemptions to note-level asset categories, interest and restricted balances.
2. Reconcile **multi-year** working capital including ₹47.50 crore FY26 inventory increase and ₹22.64 crore cash absorption by trade receivables, and distinguish permanent reinvestment versus one-time cycle movements.
3. Confirm **current** fully diluted share count, genuine distributable cash, normalized maintenance capex and minority ownership. Only then model 3-year cash to parent shareholders and a defensible market-price margin of safety.

No dividend-adjusted return, post-October market quote, scenario probability, trade depth, or source-calibrated long-horizon annual stock alpha has been estimated.

**Reproduction:** `python scripts/materialize_hg009_p010_mayur.py --check` and `pytest -q tests/test_hg009_p010_mayur.py`. Source custody under `research/hg009/p009-originals/MAYURUNIQ/`, canonical signed output under `research/hg009/hg009-p010-mayur-investing-cash-bridge-v1.json`. Prior P003 and P009 artifacts are unchanged.
