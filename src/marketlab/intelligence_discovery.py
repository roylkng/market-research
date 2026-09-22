"""Bounded discovery -> document -> company review, with append-only provenance."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_http import SourceBlocked, approved_url
from marketlab.intelligence_nse_feed import (
    NSEAnnouncementFetcher,
    validate_nse_announcement_source,
)
from marketlab.intelligence_news import (
    VERSION,
    document_body,
    entity_mentions,
    link_allowed,
    parse_feed,
    parse_listing,
    resource_key,
    topic_candidates,
)
from marketlab.intelligence_runtime import build_report
from marketlab.intelligence_store import ResearchStore, canonical, digest, now_text, timestamp


def validate_config(config: dict) -> None:
    sources = config["sources"]
    if not 1 <= len(sources) <= 12 or len({s["source_id"] for s in sources}) != len(sources):
        raise EvidenceError("Discovery needs unique, bounded source definitions")
    for field, minimum, maximum in (("max_pages_per_source", 1, 5), ("article_budget", 0, 30),
                                     ("lookback_days", 1, 30)):
        value = config[field]
        if type(value) is not int or not minimum <= value <= maximum:
            raise EvidenceError(f"Invalid discovery bound: {field}")
    for source in sources:
        approved_url(source["url"])
        exploratory = source.get("unlinked_document_budget", 0)
        if type(exploratory) is not int or not 0 <= exploratory <= 2:
            raise EvidenceError("Unlinked exploration must be bounded separately")
        if source["kind"] not in {"feed", "nse_feed", "prn_listing"}:
            raise EvidenceError("Unreviewed discovery adapter")
        if source["kind"] == "nse_feed":
            validate_nse_announcement_source(source)
        if source["access"] not in {"HEADLINES_ONLY", "PUBLIC_DOCUMENTS"}:
            raise EvidenceError("Explicit source access scope required")
        if source["access"] == "PUBLIC_DOCUMENTS" and source["document_parser"] not in {"prnewswire", "pib", "sebi"}:
            raise EvidenceError("Unreviewed document parser")


def _failure(error: Exception) -> dict:
    return {"status": "BLOCKED" if isinstance(error, SourceBlocked) else "PARSE_FAILED",
            "error_type": type(error).__name__,
            "details": getattr(error, "details", {}), "completed_at": now_text()}


def discover_source(
    store: ResearchStore,
    source: dict,
    panel: dict,
    fetcher,
    max_pages: int,
    *,
    nse_fetcher=None,
) -> list[dict]:
    """Pagination follows links present in the listing. Never invent a historical URL."""
    queue, visited, discovered = [source["url"]], set(), []
    existing = {r["item_id"]: r for r in store.records("news_item")}
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        attempt = {"stage": "DISCOVERY", "source_id": source["source_id"], "url": url,
                   "started_at": now_text(), "source_spec_sha256": digest(source),
                   "window_complete": False, "version": VERSION}
        try:
            source_fetcher = (
                nse_fetcher
                if source["kind"] == "nse_feed"
                else fetcher
            )
            if source_fetcher is None:
                raise EvidenceError("Reviewed NSE RSS fetcher is required")
            raw, meta = source_fetcher.fetch(
                url,
                url_guard=lambda target: (
                    urlparse(target).netloc == urlparse(source["url"]).netloc
                    and urlparse(target).path == urlparse(source["url"]).path
                ),
            )
            raw_hash = store.save_object(raw)
            attempt.update(response=meta, raw_sha256=raw_hash)
            active_source = {**source, "url": url}
            if source["kind"] in {"feed", "nse_feed"}:
                rows, pages = parse_feed(raw, active_source), []
            else:
                rows, pages = parse_listing(raw, active_source)
            ids = []
            for row in rows:
                identity = {k: row[k] for k in ("title", "publication", "item_status")}
                identity["resource_key"] = resource_key(row["url"]) if row["url"] else row["item_sha256"]
                item_id = digest([VERSION, identity])
                # Same release can be observed in several feeds. Keep all occurrences.
                if item_id not in existing:
                    record = {**row, "item_id": item_id, "resource_key": identity["resource_key"],
                              "first_seen_at": meta["observed_at"], "processed_at": now_text(),
                              "first_raw_sha256": raw_hash, "source_id": source["source_id"],
                              "mentions": entity_mentions(row["title"], panel["members"]),
                              "topics": topic_candidates(row["title"]),
                              "source_class": source["source_class"], "version": VERSION}
                    store.append("news_item", item_id, record)
                    existing[item_id] = record
                ids.append(item_id)
                discovered.append({"item": existing[item_id], "source": source, "provider_rank": len(discovered)})
            attempt.update(status="SNAPSHOT_CAPTURED", item_ids=ids, item_count=len(rows),
                           pages_available=pages, completed_at=now_text())
            for page in pages:
                p, original = urlparse(page), urlparse(source["url"])
                numbers = parse_qs(p.query).get("page", [])
                if (p.netloc == original.netloc and p.path == original.path and len(numbers) == 1
                        and numbers[0].isdigit() and page not in visited and page not in queue):
                    queue.append(page)
            attempt["pagination_limited"] = bool(queue and len(visited) >= max_pages)
        except Exception as exc:  # noqa: BLE001 - record failure, then return nonzero overall
            attempt.update(_failure(exc))
            queue.clear()
        attempt["attempt_id"] = digest(attempt)
        store.append("news_attempt", attempt["attempt_id"], attempt)
    return discovered


def temporal_state(item: dict, as_of: str, lookback_days: int) -> str:
    public = item["publication"]
    when = public["value"]
    if not when:
        return "PUBLICATION_UNRESOLVED"
    delta = timestamp(as_of) - timestamp(when)
    if delta < timedelta(0):
        return "DATE_ONLY_CURRENT_DAY" if public["precision"] == "DAY_UPPER_BOUND" and delta > -timedelta(days=1) else "FUTURE_PUBLICATION"
    return "OUTSIDE_LOOKBACK" if delta > timedelta(days=lookback_days) else "IN_LOOKBACK"


def select_documents(discovered: list[dict], *, as_of: str, budget: int, lookback_days: int) -> tuple[list[dict], list[dict]]:
    """Fixed research triage, not investment ranking. Every deferral is recorded."""
    unique, deferred = {}, []
    for entry in discovered:
        item, source = entry["item"], entry["source"]
        key = item["resource_key"]
        reason = None
        if source["access"] == "HEADLINES_ONLY":
            reason = "HEADLINES_ONLY_SOURCE"
        elif item["item_status"] != "DISCOVERED" or not link_allowed(item["url"], source):
            reason = "LINK_OR_ITEM_NOT_APPROVED"
        elif temporal_state(item, as_of, lookback_days) in {"OUTSIDE_LOOKBACK", "FUTURE_PUBLICATION"}:
            reason = temporal_state(item, as_of, lookback_days)
        if reason:
            deferred.append({"item_id": item["item_id"], "reason": reason})
        elif key not in unique:
            unique[key] = entry
    def priority(entry):
        item, source = entry["item"], entry["source"]
        mentions = item["mentions"]
        relevance = (
            0
            if mentions["panel_symbols"]
            else 1
            if mentions.get("official_nse_symbols")
            else 2
            if source.get("region") == "IN"
            else 3
        )
        has_topic = 0 if item["topics"] else 1
        # Provider ordering is triage only. Time-only cards must not be treated
        # as either ancient or as proven fresh publications before the article is read.
        return relevance, has_topic, source["source_id"], entry.get("provider_rank", 0), item["resource_key"]
    ordered = sorted(unique.values(), key=priority)
    selected, unlinked_counts = [], Counter()
    for entry in ordered:
        item, source = entry["item"], entry["source"]
        mentions = item["mentions"]
        linked = any(
            mentions.get(k)
            for k in (
                "panel_symbols",
                "official_nse_symbols",
                "unverified_nse_symbols",
                "bse_codes_for_review",
            )
        )
        source_id = source["source_id"]
        if not linked and unlinked_counts[source_id] >= source.get("unlinked_document_budget", 0):
            deferred.append({"item_id": item["item_id"], "reason": "NO_COMPANY_LINK_EXPLORATION_LIMIT"})
        elif len(selected) >= budget:
            deferred.append({"item_id": item["item_id"], "reason": "ARTICLE_BUDGET_DEFERRED"})
        else:
            selected.append(entry)
            if not linked:
                unlinked_counts[source_id] += 1
    return selected, deferred


def acquire_document(store: ResearchStore, entry: dict, panel: dict, fetcher) -> dict:
    item, source = entry["item"], entry["source"]
    if source["access"] != "PUBLIC_DOCUMENTS" or not link_allowed(item["url"], source):
        raise EvidenceError("Document fetch has no reviewed access scope")
    attempt = {"stage": "DOCUMENT", "source_id": source["source_id"], "item_id": item["item_id"],
               "resource_key": item["resource_key"], "url": item["url"], "version": VERSION,
               "source_spec_sha256": digest(source), "started_at": now_text(), "window_complete": False}
    try:
        raw, response = fetcher.fetch(item["url"], url_guard=lambda target: (
            link_allowed(target, source) and resource_key(target) == item["resource_key"]))
        raw_hash = store.save_object(raw)
        attempt.update(response=response, raw_sha256=raw_hash)
        if not link_allowed(response["resolved_url"], source):
            raise EvidenceError("Resolved document path is outside source scope")
        if "html" not in response["content_type"].lower():
            raise EvidenceError("Attachment format not supported by this HTML adapter")
        doc = document_body(raw, source)
        body_hash = store.save_object(doc["body"].encode())
        lead_hash = store.save_object(doc["lead"].encode())
        # Cosmetic page changes are observations, not new economic developments.
        document_id = digest([VERSION, item["resource_key"], doc["title"], body_hash, doc["publication"]])
        prior = next((r for r in store.records("news_document") if r["document_id"] == document_id), None)
        if prior is None:
            record = {"document_id": document_id, "resource_key": item["resource_key"],
                      "source_id": source["source_id"], "source_spec": source,
                      "discovered_from_item_id": item["item_id"], "url": response["resolved_url"],
                      "raw_sha256": raw_hash, "body_sha256": body_hash, "lead_sha256": lead_hash,
                      "title": doc["title"], "publication": doc["publication"],
                      "publication_candidates": doc["publication_candidates"],
                      "first_seen_at": response["observed_at"], "processed_at": now_text(),
                      "mentions": entity_mentions(doc["title"] + " " + doc["lead"], panel["members"]),
                      "topics": topic_candidates(doc["lead"]),
                      "source_class": source["source_class"],
                      "independent_corroboration": False,
                      "state": "DOCUMENT_RETRIEVED_REQUIRES_ECONOMIC_REVIEW", "version": VERSION}
            store.append("news_document", document_id, record)
        attempt.update(status="DOCUMENT_CAPTURED", document_id=document_id, completed_at=now_text())
    except Exception as exc:  # noqa: BLE001 - retain failed attempt and partial report
        attempt.update(_failure(exc))
    attempt["attempt_id"] = digest(attempt)
    store.append("news_attempt", attempt["attempt_id"], attempt)
    return attempt


def run_discovery(
    store: ResearchStore,
    panel: dict,
    config: dict,
    fetcher,
    *,
    nse_fetcher=None,
) -> dict:
    validate_config(config)
    store.append("news_configuration", digest(config), config)
    if nse_fetcher is None and any(
        source["kind"] == "nse_feed" for source in config["sources"]
    ):
        nse_fetcher = NSEAnnouncementFetcher()
    started, items = now_text(), []
    for source in config["sources"]:
        items.extend(
            discover_source(
                store,
                source,
                panel,
                fetcher,
                config["max_pages_per_source"],
                nse_fetcher=nse_fetcher,
            )
        )
    selected, deferred = select_documents(items, as_of=now_text(), budget=config["article_budget"],
                                         lookback_days=config["lookback_days"])
    for entry in selected:
        acquire_document(store, entry, panel, fetcher)
    attempts = [r for r in store.records("news_attempt") if timestamp(r["started_at"]) >= timestamp(started)]
    run = {"started_at": started, "completed_at": now_text(), "configuration_sha256": digest(config),
           "attempt_ids": sorted(r["attempt_id"] for r in attempts),
           "deferred": sorted(deferred, key=lambda r: (r["item_id"], r["reason"])),
           "selected_item_ids": [e["item"]["item_id"] for e in selected],
           "status": "PARTIAL_FAILURE" if any(r["status"] in {"BLOCKED", "PARSE_FAILED"} for r in attempts) else "BOUNDED_CAPTURE_COMPLETE",
           "full_market_coverage": False, "live_capital_allowed": False, "version": VERSION}
    run["run_id"] = digest(run)
    store.append("news_run", run["run_id"], run)
    return run


def build_discovery_report(store: ResearchStore, panel: dict, company_config: dict, config: dict, *, as_of: str) -> dict:
    """Join into existing company packets without pretending headline matches are facts."""
    report = build_report(store, panel, company_config, as_of=as_of)
    cutoff = timestamp(as_of)
    docs = [r for r in store.records("news_document") if timestamp(r["processed_at"]) <= cutoff]
    items = [r for r in store.records("news_item") if timestamp(r["processed_at"]) <= cutoff]
    attempts = [r for r in store.records("news_attempt") if timestamp(r["completed_at"]) <= cutoff]
    latest_success, latest_attempt = {}, {}
    for attempt in sorted(attempts, key=lambda r: (r["completed_at"], r["attempt_id"])):
        if attempt["stage"] != "DOCUMENT":
            continue
        key = attempt["resource_key"]
        latest_attempt[key] = attempt
        if attempt["status"] == "DOCUMENT_CAPTURED":
            latest_success[key] = attempt["document_id"]
    stories = []
    for doc in sorted(docs, key=lambda r: (r["first_seen_at"], r["document_id"]), reverse=True):
        story = {**doc, "time_state": temporal_state(doc, as_of, config["lookback_days"])}
        story.pop("source_spec")
        story["version_state"] = ("LATEST_OBSERVED_VERSION" if latest_success.get(doc["resource_key"])
                                  == doc["document_id"] else "EARLIER_OBSERVED_VERSION")
        story["latest_fetch_status"] = latest_attempt.get(doc["resource_key"], {}).get("status", "UNKNOWN")
        story["topics"] = [{k: row[k] for k in ("topic", "review_question", "status")} for row in doc["topics"]]
        story["forecast"] = None
        stories.append(story)
    for packet in report["packets"]:
        packet["news_discovery"] = {
            "headline_item_ids": [r["item_id"] for r in items if packet["symbol"] in r["mentions"]["panel_symbols"]],
            "document_ids": [r["document_id"] for r in docs if packet["symbol"] in r["mentions"]["panel_symbols"]],
            "coverage": "INCOMPLETE_DISCOVERY_NOT_ALL_COMPANY_NEWS", "reviewed_economic_event_count": 0}
        packet.pop("packet_sha256")
        packet["packet_sha256"] = digest(packet)
    report["engine"] = "COMPANY_INTELLIGENCE_V2_WITH_NEWS_DISCOVERY"
    report["news_discovery"] = {"configuration_sha256": digest(config), "version": VERSION,
        "item_count": len(items), "document_count": len(docs),
        "distinct_document_resources": len({r["resource_key"] for r in docs}),
        "panel_companies_with_mentions": sorted({s for r in docs for s in r["mentions"]["panel_symbols"]}),
        "panel_companies_with_headlines": sorted({s for r in items for s in r["mentions"]["panel_symbols"]}),
        "official_nse_symbols_with_headlines": sorted(
            {s for r in items for s in r["mentions"].get("official_nse_symbols", [])}
        ),
        "unverified_external_symbols": sorted(
            {s for r in docs for s in r["mentions"]["unverified_nse_symbols"]}
        ),
        "items": items, "stories": stories, "attempts": attempts,
        "runs": [r for r in store.records("news_run") if timestamp(r["completed_at"]) <= cutoff],
        "source_status_counts": dict(Counter(r["status"] for r in attempts)),
        "missing_channels": ["COMPLETE_EXCHANGE_FILINGS", "PUBLIC_SOCIAL", "COMPLETE_EDITORIAL_NEWS"],
        "full_market_coverage": False, "forecast": None}
    report.pop("report_sha256")
    report["report_sha256"] = digest(report)
    return report


def verify_discovery(store: ResearchStore, panel: dict) -> dict:
    checked = 0
    for doc in store.records("news_document"):
        parsed = document_body(store.read_object(doc["raw_sha256"]), doc["source_spec"])
        for key in ("body", "lead"):
            if parsed[key].encode() != store.read_object(doc[key + "_sha256"]):
                raise EvidenceError("Retained article does not reproduce")
        if parsed["title"] != doc["title"] or parsed["publication"] != doc["publication"]:
            raise EvidenceError("Retained article metadata drift")
        if topic_candidates(parsed["lead"]) != doc["topics"]:
            raise EvidenceError("Topic match does not reproduce from source")
        if entity_mentions(parsed["title"] + " " + parsed["lead"], panel["members"]) != doc["mentions"]:
            raise EvidenceError("Entity mentions do not reproduce")
        checked += 1
    return {"verified_original_documents": checked, "verified_forecasts": 0}


def export_discovery_report(report: dict, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    news = report["news_discovery"]
    lines = ["# MarketLab v2 discovery report", "", f"As of: {report['as_of']}", "",
             f"{news['item_count']} observed items, {news['document_count']} document versions.",
             "Bounded source snapshots, not complete news coverage. Mentions are not buy signals.", "",
             "## Source attempts", "", "| Source | Stage | Outcome |", "|---|---|---|"]
    for a in news["attempts"]:
        lines.append(f"| {a['source_id']} | {a['stage']} | {a['status']} |")
    lines += ["", "## Automatically discovered documents", ""]
    for r in news["stories"]:
        lines += [f"### {r['title']}", "", f"Source: {r['url']}",
                  (f"Publication: {r['publication']['value']} ({r['publication']['precision']}). "
                  f"First collected: {r['first_seen_at']}. Time state: {r['time_state']}."),
                  (f"Panel mentions: {', '.join(r['mentions']['panel_symbols']) or 'None resolved'}. "
                  f"Other official NSE identities: {', '.join(r['mentions'].get('official_nse_symbols', [])) or 'None'}. "
                  f"Other NSE identifiers requiring verification: {', '.join(r['mentions']['unverified_nse_symbols']) or 'None'}.")]
        lines.extend(t["review_question"] for t in r["topics"])
        lines += [""]
    lines += ["## Limits", "", ("Company identification is provisional mention routing. No financial "
              "forecast, valuation or directional score is inferred from headlines. Article research "
              "priority is not investment ranking. Unfetched, stale and unknown-date items are retained."),
              "Independent editorial feeds are headline-only and subject to their personal-use terms.", ""]
    for suffix, text in (("json", canonical(report) + "\n"), ("md", "\n".join(lines))):
        p = destination / f"discovery-{report['report_sha256']}.{suffix}"
        if p.exists() and p.read_text() != text:
            raise EvidenceError("Immutable report output conflict")
        p.write_text(text)
