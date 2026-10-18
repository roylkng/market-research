# L001 P012 | Zuari's June 30 portfolio versus October 15 market prices

**Research date:** October 18, 2026. **Status:** Retrospective accounting/value diagnostic, independent of the frozen HG009 signals, actions and controls. This analysis is not an entry instruction or a current fair-value assessment.

## The consequential hidden assumption

The issuer's June 30, 2026 investor deck (original issuer original PDF SHA `6ebec1ef99aba350000aab28b1e9f1b6c6a39471458df488ece9c7f8ea4fb25b`, page 20) reported **₹4,223 crore** of group listed strategic investments across five quoted companies, with *June* reference stock prices. The earlier P010 compared this with Zuari Industries' **October 15** equity capitalization. That mismatch can create a fictitious asset discount if the underlying listed investments fell in the intervening months.

A correct retrospective comparison must, at minimum, reprice each underlying quoted holding using the **same October 15 NSE session** as Zuari's own basic-share capitalization, preserve original symbol + ISIN, and reject splits or unresolved holding changes.

## Exact source assets, not online latest prices

- NSE original 2026-10-15 whole-market cash-market UDiFF ZIP retained at `research/prospective/h021/daily-prices/raw/sha256/3d1c7039e2c70868cc44b51d1f9e4b0f942afc0575fe8c4a524aed9e01eac3e8.zip`.
- UDiFF original was first captured **2026-10-15T17:21:34Z**, after AE001's 18:30 IST same-day cutoff. This analysis is **NOT** an admissible 15 October EOD predictive signal.
- Five June original issuer rows and their exact exchange identities:
  - CHAMBLFERT (INE085A01013), June quote ₹468, rounded holding ₹2,783cr;
  - ZUARI (INE840M01016), June quote ₹230, rounded holding ₹310cr;
  - PARADEEP (INE088F01024), June quote ₹136, rounded holding ₹8cr;
  - TEXRAIL (INE621L01012), June quote ₹108, rounded holding ₹695cr;
  - TEXINFRA (INE435C01024), June quote ₹109, rounded holding ₹428cr.
- The issuer's individually rounded values total **₹4,224cr**, ₹1cr above the reported aggregate ₹4,223cr. The engine scales the proportional reprice to the issuer aggregate, rather than treating rounded lakh-share counts as exact.
- The old holding-company historical basic shares (2,97,81,184) come from P004 source-audited shareholding; their *fully diluted October 15* status remains unverified.
- The March 31 net borrowing bridge ₹2,581.29cr gross debt less ₹61.8655cr cash is **not contemporaneous October 15 debt**. P010's September ₹258.5cr receivable repayment and intragroup share transfer are important; the outstanding October parent/subsidiary and pledged-debt structure remains unverified.

## Economic and causal restrictions

The model calculates an **unchanged June group holdings** quoted-price mark at October 15. That does not prove the number of each holding is still unchanged, or that listed shares can be realized at the close without slippage, block discounts, pledges, ownership restrictions, capital-gains tax or group debt covenants. June share holdings are rounded; there may have been corporate actions after June.

It uses the March debt solely as a transparent **cross-dated stress illustration**. It deliberately does not calculate parent owner earnings, fair value, prospective alpha, net realized proceeds or an investment ranking. Never subtract pledged portfolio market value as an *extra* liability when its collateral loans are already part of debt.

A complete investment-quality sum of parts needs:
1. October 15 group stake *units* and legal owner chain from original governance filings, including the September internal TEXINFRA transfer and any pledge release.
2. October 15 parent and subsidiary borrowings/claims, collateral waterfall, recent ICD cash settlement and Dubai repatriation, excluding intercompany balances on consolidation.
3. Up-to-date block-sale after-tax realizable listed portfolio value versus cash/creditors, tax, liquidity haircuts and control premiums.
4. Actual gross and net cash distributed to parent owners and prospective 1/2/3-year after-cost return observations.

**This corrects date alignment without inventing an investment opportunity.**

## Observed results: full original NSE replay succeeded

Independent workflow **39119236445** passed and published GitHub Actions artifact **12133860963**, which contains `l001-p012-zuari-price-synchronized-20261015.json` (canonical report SHA `3080ce5cdd63a161c45ce7be75d6bf68f2f17919bc1fa61d6844697476957fd9`).

| Original listed issuer | June issuer quote | Oct 15 original NSE close | June issuer rounded mark ₹Cr | Repriced Oct 15 ₹Cr |
|---|---:|---:|---:|---:|
| CHAMBLFERT | 468.00 | **390.30** | 2,783 | **2,320.40** |
| ZUARI | 230.00 | **206.39** | 310 | **278.11** |
| PARADEEP | 136.00 | **146.41** | 8 | **8.61** |
| TEXRAIL | 108.00 | **112.89** | 695 | **726.30** |
| TEXINFRA | 109.00 | **123.98** | 428 | **486.71** |

Individually rounded June line marks total ₹4,224Cr; original issuer June aggregate is ₹4,223Cr. Scaling the proportional repricing to its actual disclosed group aggregate yields **₹3,820.124826Cr** on October 15, down **9.54%** from June.

The fresh date-aligned *listed asset mark* only, offset with **still-stale March** debt (₹2,519.4245Cr net), yields a hypothetical ₹1,300.7003Cr residual against ₹796.7956Cr of historical basic equity value. The residual-minus-price gap is **₹503.9047Cr**, not shareholder value.

**Downside sensitivity on the repriced portfolio:**

| Extra portfolio markdown after Oct15 mark | Residual after old March net debt ₹Cr | Gap to historical equity cap ₹Cr |
|---|---:|---:|
| 0% | 1,300.70 | +503.90 |
| 10% | 918.69 | +121.89 |
| **13.19% (crossover)** | **~796.80** | **~0** |
| 20% | 536.68 | −260.12 |
| 30% | 154.66 | −642.13 |

**This supersedes P010's misleading additional 21.47% cushion derived from June asset prices.** The relevant *additional* cushion for an unchanged-ownership and March-net-debt cross-date calculation is approximately **13.19%**. This does **not** represent a robust investment margin of safety because debt/ownership changes, liquidation taxes, pledge terms, operating subsidiary residuals, counterparty recovery and dilution remain unresolved.

The October 15 market ZIP was captured later that same day, well after AE001 decision cutoff, so this is strictly **post-hoc independent original-price reconciliation**. No effect on the original HG009 frozen experiment or recorded returns.
