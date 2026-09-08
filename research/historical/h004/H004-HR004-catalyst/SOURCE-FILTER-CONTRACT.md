# H004-HR004 source-category filter contract

Status: **FROZEN BEFORE FILTERED QUEUE OUTPUT INSPECTION**

The first keyword extraction deliberately maximized recall and produced administrative false positives. This second filter may use only NSE disclosure description and attachment-summary text. It may not use symbols, prices or future outcomes.

## Always exclude administrative / reactive descriptions

- Disclosure under SEBI Takeover Regulations
- Spurt in Volume
- Price movement
- Action(s) taken or orders passed
- Action(s) initiated or orders passed
- Pendency of Litigation(s)/dispute(s) or outcome impacting the Company
- News Verification
- Shareholders meeting
- Copy of Newspaper Publication
- Analysts/Institutional Investor Meet/Con. Call Updates
- Monitoring Agency Report
- Record Date
- Appointment / Resignation / Cessation / Change in Management
- Trading Window
- Dividend
- securities allotment/issue descriptions unless an independent market-opening approval is explicitly present in the attachment summary

## Family-specific retained description classes

### ORDER_CONTRACT
Always retain:
- Bagging/Receiving of orders/contracts
- Awarding of order(s)/contract(s)

For General Updates / Updates / Press Release / Agreements / MoU descriptions, retain only when attachment-summary text contains an affirmative award verb (`received`, `secured`, `awarded`, `wins`, `won`, `bagged`, `letter of award`, `purchase order`, `work order`, `contract awarded`, `selected as L1`, `preferred bidder`) together with `order` or `contract` context.

### CAPACITY_COMMISSIONING
Always retain:
- Capacity addition
- Commencement of commercial production/operations
- Adoption of new line(s) of business

For generic updates/press releases, retain only when summary contains `commissioning`, `commercial production`, `commercial operation`, `capacity expansion`, `capacity addition`, `greenfield`, `brownfield`, or `new facility/plant/line`.

### MNA_CONTROL
Always retain:
- Acquisition
- Amalgamation/Merger
- Public Announcement-Open Offer
- Open Offer
- Demerger
- Scheme of Arrangement
- Sale or disposal
- Other Restructuring
- Arrangements for strategic, technical, manufacturing, or marketing tie up

For Agreements / MoU / General Updates / Updates / Press Release / Board Outcome, retain only when summary affirmatively states acquisition of a company/business/stake/undertaking, merger/demerger, disposal/business transfer, strategic investment, change in control, or formation of a material joint venture.

### REGULATORY_MARKET_OPENING
Always retain:
- Granting/withdrawal/surrender/cancellation/suspension of key licenses/ regulatory approvals

For generic updates/press releases, retain only when summary affirmatively describes a regulator/government/customer approval, licence/license, certification or authorization for a product, facility, market or commercial activity. Securities listing/allotment approvals do not qualify.

### GUIDANCE_RAMP
Retain Product launch and generic updates/press releases only when summary contains a quantitative token (digit, percentage, currency, capacity unit, customer/site/store/network count or dated operating horizon) together with guidance, launch, customer/product/network ramp, first commercial operation, or new-business language.

## Output

Every retained candidate remains ungraded. Grade 3/4 materiality is a later source-only decision. The filter is a review-operations rule, not a performance model, and cannot be modified after the filtered queue is generated to improve historical returns.
