# HG006-D002 Discrete-Event Outcome Ontology v1

Status: **FROZEN BEFORE HG006-D001 HISTORICAL OUTPUT IS OPENED**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Historical completion labels opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Define what counts as transaction progress, completion, failure and right-censoring for
HG006 historical discrete-event research before inspecting the historical cohort.

D002 is an ontology/labeling contract. It does not calculate probabilities.

## Core principle

A transaction is not "successful" merely because:

- a board approved it;
- shareholders approved it;
- an exchange granted in-principle approval;
- NCLT sanctioned a scheme;
- an offer opened;
- a record date was fixed.

Completion requires the family-specific economic terminal state defined below.

## Common state classes

Every historical transaction episode must end the observation window in exactly one:

- COMPLETED;
- FAILED_OR_WITHDRAWN;
- RIGHT_CENSORED;
- UNRESOLVED_SOURCE_CONFLICT.

RIGHT_CENSORED is not failure.

UNRESOLVED_SOURCE_CONFLICT is excluded from the numerator and denominator of a simple
completion fraction and must be reported separately.

## Evidence hierarchy

Terminal state may be assigned only from explicit official NSE/SEBI/company filing text
bound to exact source evidence.

No state may be inferred from:

- subsequent stock price;
- absence of later announcements;
- model memory;
- news articles;
- current company status alone.

## Family-specific completion semantics

### BUYBACK

COMPLETED when official evidence explicitly establishes completion/closure of the buyback
and, where applicable, extinguishment or completion of the accepted-share process.

FAILED_OR_WITHDRAWN when official evidence explicitly states withdrawal, cancellation,
rejection, non-proceeding or regulatory failure.

Offer opening or board approval alone is non-terminal.

### OPEN_OFFER_CONTROL

COMPLETED when official evidence establishes closure/completion of the open-offer process
and the underlying acquisition/control transaction is stated as completed or consummated
when that transaction is part of the offer.

FAILED_OR_WITHDRAWN when the offer/acquisition is explicitly withdrawn, terminated,
rejected or cannot proceed.

A public announcement or offer opening alone is non-terminal.

### DELISTING

COMPLETED only when official evidence establishes successful/effective delisting or
completion of the delisting offer leading to delisting.

FAILED_OR_WITHDRAWN when the discovered price is rejected, the delisting fails,
withdraws, terminates or is formally abandoned.

Board/shareholder approval alone is non-terminal.

### SCHEME_REORGANISATION

COMPLETED only when the scheme is explicitly stated to have become effective / operative
after required tribunal/regulatory/filing conditions.

NCLT sanction alone is not sufficient if effectiveness remains conditional.

FAILED_OR_WITHDRAWN when the scheme is explicitly withdrawn, rejected, terminated,
superseded without continuation, or declared not effective.

### RIGHTS_ISSUE

COMPLETED when allotment/completion of the rights issue is explicitly established.

FAILED_OR_WITHDRAWN when the issue is explicitly withdrawn, cancelled or abandoned.

Record date, opening and closing alone are non-terminal unless allotment/completion is
also explicit.

### PREFERENTIAL_WARRANT

This family has two distinct terminal questions.

#### A. issuance_completion

COMPLETED when the preferential securities/warrants/shares are explicitly allotted.

FAILED_OR_WITHDRAWN when the proposed issuance is explicitly withdrawn, rejected,
cancelled or not proceeded with.

Exchange in-principle approval or shareholder approval alone is non-terminal.

#### B. full_economic_exercise

For warrants/options only, COMPLETED when all relevant exercise/conversion obligations
for the tracked issuance are explicitly completed.

Partial exercise is non-terminal unless the transaction terms themselves define the
tracked tranche as complete.

A base rate for issuance_completion may not be silently substituted for
full_economic_exercise.

### CAPITAL_REDUCTION

COMPLETED when the reduction is explicitly effective/implemented following required
approvals/filings.

FAILED_OR_WITHDRAWN when explicitly rejected, withdrawn, terminated or abandoned.

### OFFER_FOR_SALE

COMPLETED when the OFS is explicitly closed/completed with the final sale/allocation
process concluded.

FAILED_OR_WITHDRAWN when explicitly withdrawn/cancelled.

### TENDER_OFFER

COMPLETED when the tender transaction is explicitly closed/completed and accepted
securities/consideration are settled as applicable.

FAILED_OR_WITHDRAWN when explicitly withdrawn, cancelled or terminated.

## Non-terminal progress states

Historical extraction may retain:

- PROPOSAL;
- BOARD_APPROVED;
- SHAREHOLDER_APPROVED;
- REGULATORY_OR_COURT_APPROVED;
- PUBLIC_ANNOUNCEMENT;
- RECORD_DATE_FIXED;
- OFFER_OPEN;
- OFFER_CLOSED;
- ALLOTMENT_COMPLETED;
- TRANSACTION_COMPLETED;
- CANCELLED_OR_WITHDRAWN;
- PROCEDURAL_UPDATE;
- UNKNOWN.

The family-specific ontology above decides whether one of these observations is truly
terminal for that family.

## Transaction episode identity

HG006 base rates are calculated per transaction episode, not per symbol-family aggregate.

D001 symbol-family chronologies are source-feasibility containers only.

Before probability estimation, HG006 must separately freeze and validate an episode
threading method using exact transaction references, dates, parties, security terms and
document evidence.

Two unrelated preferential issues or schemes by the same issuer may not be collapsed
into one observation.

## Right-censoring

A transaction episode with no explicit terminal state by 2026-09-30 is RIGHT_CENSORED.

It must not be counted as failure.

Later survival/time-to-event analysis may use censoring explicitly.

## Current-case application boundary

Historical stage-transition rates may eventually inform the discrete transaction
component of current cases.

They may not assign probabilities to:

- operating utilization;
- EBITDA per tonne;
- valuation multiples;
- post-raise capital productivity;
- tenant economics;
- management execution quality.

Those require separate operating-analog evidence.

## Scientific boundary

No D002 output creates:

- a historical completion rate;
- a current-company completion probability;
- expected return;
- buy/sell/hold;
- portfolio eligibility;
- live-capital authorization.
