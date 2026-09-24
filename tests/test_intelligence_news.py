from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_discovery import (
    build_discovery_report,
    discover_source,
    run_discovery,
    select_documents,
    temporal_state,
    validate_config,
    verify_discovery,
)
from marketlab.intelligence_http import PublicFetcher, SourceBlocked
from marketlab.intelligence_news import (
    canonical_url,
    document_body,
    entity_mentions,
    parse_feed,
    parse_listing,
    publication,
    resource_key,
    topic_candidates,
)
from marketlab.intelligence_nse_feed import NSE_ANNOUNCEMENTS_URL
from marketlab.intelligence_store import ResearchStore, now_text

URL = "https://www.prnewswire.com/in/news-releases/test-company-302800001.html"
FEED = "https://www.prnewswire.com/rss/news-releases-list.rss"
FIXED_DATE = "2026-09-17T07:00:00Z"
DATE = (
    datetime.now(UTC) - timedelta(days=1)
).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source(**kwargs):
    return {"source_id": "test", "kind": "feed", "url": FEED, "publisher": "PRNewswire",
            "source_class": "ISSUER_DISTRIBUTION", "access": "PUBLIC_DOCUMENTS",
            "document_parser": "prnewswire", "region": "IN", "timezone": "Asia/Kolkata",
            "article_hosts": ["www.prnewswire.com"],
            "article_path_pattern": r"/(?:in/)?news-releases/[^/?]+-\d{8,12}\.html", **kwargs}


def panel():
    return {"panel_id": "SYNTHETIC-TEST", "members": [
        {"symbol": "INFY", "company_name": "Infosys Ltd.", "isin": "INE009A01021", "constituent_industry": "IT"},
        {"symbol": "ITC", "company_name": "ITC Ltd.", "isin": "INE154A01025", "constituent_industry": "FMCG"}]}


def config(**kwargs):
    return {"sources": [source()], "max_pages_per_source": 2, "article_budget": 2,
            "lookback_days": 7, **kwargs}


def feed(title="Infosys plans new facility", url=URL, pub=DATE):
    return (f'<rss><channel><item><title>{title}</title><link>{url}</link>'
            f'<pubDate>{pub}</pubDate><guid>release-1</guid></item></channel></rss>').encode()


def article(*, body=None, date=DATE, metadata=""):
    text = body or ("Infosys (NSE: INFY) plans an investment, subject to customer qualification. "
                    "The announced facility is not commissioned. No revenue forecast is provided. "
                    "About Elsewhere NSE: WRONG")
    return (f'<html><head><meta name="date" content="{date}">{metadata}</head>'
            '<body><article class="news-release"><h1>Infosys plans a facility</h1>'
            f'<section class="release-body">{text}</section></article></body></html>').encode()


class Fetcher:
    def __init__(self, content=None):
        self.content = content or {FEED: feed(), URL: article()}
        self.calls = []

    def fetch(self, url, *, url_guard=None):
        self.calls.append(url)
        if url_guard and not url_guard(url):
            raise SourceBlocked("Scope rejected")
        raw = self.content[url]
        if isinstance(raw, Exception):
            raise raw
        return raw, {"resolved_url": url, "content_type": "text/html" if b'<html' in raw else 'application/xml',
                     "status_code": 200, "observed_at": now_text()}


@pytest.mark.parametrize("raw", ["14:12 IST", "today", "17 Sep", "2026-13-01", "invalid"])
def test_no_invented_publication_day(raw):
    assert publication(raw)["value"] is None


def test_day_precision_is_explicit_and_conservative():
    assert publication("16 Sep, 2026 +0530") == {
        "value": "2026-09-16T18:29:59.999999+00:00", "precision": "DAY_UPPER_BOUND", "raw": "16 Sep, 2026 +0530"}
    assert publication("2026-09-16")["value"] == publication("16 Sep 2026")["value"]


@pytest.mark.parametrize("raw", ["2026-09-17T12:30:00+05:30", "Thu, 17 Sep 2026 07:00:00 GMT", FIXED_DATE])
def test_timezone_normalization(raw):
    assert publication(raw)["value"] == "2026-09-17T07:00:00+00:00"


def test_nse_exchange_timestamp_uses_source_timezone():
    assert publication("23-Sep-2026 15:19:20", "Asia/Kolkata") == {
        "value": "2026-09-23T09:49:20+00:00",
        "precision": "SECOND",
        "raw": "23-Sep-2026 15:19:20",
    }


def test_nse_feed_context_exposes_event_semantics_without_promoting_it_to_fact():
    nse = {
        **source(),
        "source_id": "nse-announcements",
        "kind": "nse_feed",
        "url": NSE_ANNOUNCEMENTS_URL,
        "publisher": "NSE",
        "access": "HEADLINES_ONLY",
    }
    raw = (
        b"<rss><channel><item>"
        b"<title>Whirlpool of India Limited</title>"
        b"<link>https://nsearchives.nseindia.com/corporate/test.pdf</link>"
        b"<description>The Exchange has sought clarification regarding promoter stake sale. "
        b"|SUBJECT: News Verification</description>"
        b"<pubDate>23-Sep-2026 15:19:20</pubDate>"
        b"</item></channel></rss>"
    )
    row = parse_feed(raw, nse)[0]
    assert row["publication"]["value"] == "2026-09-23T09:49:20+00:00"
    assert "promoter stake sale" in row["event_context"]
    assert len(row["event_context_sha256"]) == 64
    topics = topic_candidates(row["event_context"])
    assert [topic["topic"] for topic in topics] == ["OWNERSHIP_CONTROL"]
    assert all(topic["status"] == "TEXT_TOPIC_NOT_CONFIRMED_EVENT" for topic in topics)


def test_atom_updated_is_not_fabricated_original_publication():
    raw = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id><title>Test</title><link href="https://www.prnewswire.com/test"/><updated>2026-09-17T07:00:00Z</updated></entry></feed>'
    row = parse_feed(raw, source())[0]
    assert row["publication"]["value"] is None
    assert row["updated_raw"] == DATE


@pytest.mark.parametrize("raw", [b'<!DOCTYPE rss [<!ENTITY a "x">]><rss/>', b'<html>Access denied</html>', b'\x00<rss/>'])
def test_unsafe_or_wrong_feed_never_becomes_empty_success(raw):
    with pytest.raises(EvidenceError):
        parse_feed(raw, source())


def test_missing_feed_fields_are_retained():
    rows = parse_feed(b'<rss><channel><item><title>Missing link</title></item></channel></rss>', source())
    assert len(rows) == 1 and rows[0]["item_status"] == "MALFORMED_ITEM"


def test_tracking_dedup_preserves_resource_identifiers():
    assert resource_key(URL + '?utm_source=feed') == resource_key(URL)
    assert canonical_url('https://www.sebi.gov.in/a?ID=1&utm_medium=x') != canonical_url('https://www.sebi.gov.in/a?ID=2')


def test_unknown_symbols_not_discarded_and_common_tickers_not_matched():
    m = entity_mentions('ITC is an abbreviation. Infosys plans new work. NSE: NEWCO BSE: 123456', panel()["members"])
    assert m["panel_symbols"] == ["INFY"]
    assert m["official_nse_symbols"] == []
    assert m["unverified_nse_symbols"] == ["NEWCO"]
    assert m["bse_codes_for_review"] == ["123456"]
    assert entity_mentions('NSE: ITC', panel()["members"])["panel_symbols"] == ["ITC"]


def test_official_nse_identity_is_not_mislabelled_as_deep_panel():
    members = panel()["members"] + [{
        "symbol": "TEGA",
        "company_name": "Tega Industries",
        "identity_source": "NSE_UDIFF_PRIOR_SESSION",
        "is_deep_panel": False,
    }]
    m = entity_mentions("Tega Industries wins a new order", members)
    assert m["panel_symbols"] == []
    assert m["official_nse_symbols"] == ["TEGA"]


def test_duplicate_name_is_ambiguous_not_arbitrary_choice():
    members = panel()["members"] + [{"symbol": "OTHER", "company_name": "Infosys Limited"}]
    m = entity_mentions("Infosys reports results", members)
    assert m["panel_symbols"] == [] and len(m["ambiguous_mentions"]) == 1


def test_article_excludes_boilerplate_entities_and_keeps_negated_topic_as_review():
    parsed = document_body(article(), source())
    mentions = entity_mentions(parsed["lead"], panel()["members"])
    assert mentions["panel_symbols"] == ["INFY"]
    assert "WRONG" not in mentions["unverified_nse_symbols"]
    topics = topic_candidates(parsed["lead"])
    assert all(row["status"] == "TEXT_TOPIC_NOT_CONFIRMED_EVENT" for row in topics)
    for row in topics:
        assert parsed["lead"][row["match_start"]:row["match_end"]] == row["matched_text"]


def test_publication_metadata_conflict_is_quarantined():
    raw = article(metadata='<script type="application/ld+json">{"@type":["NewsArticle"],"datePublished":"2026-09-16T07:00:00Z"}</script>')
    assert document_body(raw, source())["publication"]["precision"] == "CONFLICTING"


def test_listing_requires_article_cards_and_keeps_time_only_unknown():
    listing_source = source(kind="prn_listing", url='https://www.prnewswire.com/in/news-releases/news-releases-list/')
    raw = f'<h1>All News Releases</h1><a href="{URL}"><h3><small>14:12 IST</small>Infosys expands</h3></a><a href="?page=2">2</a><a href="/marketing.html">Fake</a>'.encode()
    rows, pages = parse_listing(raw, listing_source)
    assert len(rows) == 1 and rows[0]["publication"]["value"] is None
    assert len(pages) == 1
    with pytest.raises(EvidenceError):
        parse_listing(b'<h1>All News Releases</h1>', listing_source)


@pytest.mark.parametrize("field,value", [("article_budget", -1), ("max_pages_per_source", 6), ("lookback_days", 0)])
def test_limits_cannot_be_unbounded(field, value):
    with pytest.raises(EvidenceError):
        validate_config(config(**{field: value}))


def test_repeated_discovery_preserves_first_seen_and_all_observations(tmp_path):
    with ResearchStore(tmp_path) as store:
        fetcher = Fetcher()
        discover_source(store, source(), panel(), fetcher, 1)
        first = store.records("news_item")
        discover_source(store, source(), panel(), fetcher, 1)
        assert store.records("news_item") == first
        assert len(store.records("news_attempt")) == 2


def test_network_failure_keeps_prior_items_and_new_failure(tmp_path):
    with ResearchStore(tmp_path) as store:
        discover_source(store, source(), panel(), Fetcher(), 1)
        discover_source(store, source(), panel(), Fetcher({FEED: SourceBlocked("403")}), 1)
        assert len(store.records("news_item")) == 1
        assert {r["status"] for r in store.records("news_attempt")} == {"SNAPSHOT_CAPTURED", "BLOCKED"}


def test_headline_only_source_is_never_fetched_as_article(tmp_path):
    with ResearchStore(tmp_path) as store:
        c = config(sources=[source(access="HEADLINES_ONLY")])
        fetcher = Fetcher()
        run = run_discovery(store, panel(), c, fetcher)
        assert fetcher.calls == [FEED]
        assert run["deferred"][0]["reason"] == "HEADLINES_ONLY_SOURCE"
        assert store.records("news_document") == []



def test_reviewed_nse_feed_uses_dedicated_fetcher(tmp_path):
    nse_source = {
        "source_id": "nse-announcements",
        "kind": "nse_feed",
        "url": NSE_ANNOUNCEMENTS_URL,
        "publisher": "NSE",
        "region": "IN",
        "timezone": "Asia/Kolkata",
        "source_class": "EXCHANGE_DISCLOSURE",
        "access": "HEADLINES_ONLY",
        "document_parser": None,
        "article_hosts": [],
        "article_path_pattern": "(?!)",
    }

    class NeverGeneric:
        def fetch(self, *_args, **_kwargs):
            raise AssertionError("generic public fetcher must not handle reviewed NSE RSS")

    class NSEFetcher:
        def __init__(self):
            self.calls = []
        def fetch(self, url, *, url_guard=None):
            self.calls.append(url)
            assert url_guard is None or url_guard(url)
            return feed(), {
                "resolved_url": url,
                "content_type": "application/xml",
                "status_code": 200,
                "observed_at": now_text(),
                "source_contract_id": "NSE-ONLINE-ANNOUNCEMENTS-RSS-V1",
            }

    nse_fetcher = NSEFetcher()
    with ResearchStore(tmp_path) as store:
        run = run_discovery(
            store,
            panel(),
            config(sources=[nse_source]),
            NeverGeneric(),
            nse_fetcher=nse_fetcher,
        )
        assert run["status"] == "BOUNDED_CAPTURE_COMPLETE"
        assert len(store.records("news_item")) == 1
    assert nse_fetcher.calls == [NSE_ANNOUNCEMENTS_URL]

def test_budget_and_stale_deferred_items_are_explicit(tmp_path):
    with ResearchStore(tmp_path) as store:
        entries = discover_source(store, source(), panel(), Fetcher(), 1)
        chosen, deferred = select_documents(entries, as_of='2026-09-17T09:00:00Z', budget=0, lookback_days=7)
        assert not chosen and deferred[0]["reason"] == "ARTICLE_BUDGET_DEFERRED"
        chosen, deferred = select_documents(entries, as_of='2026-10-17T09:00:00Z', budget=2, lookback_days=7)
        assert not chosen and deferred[0]["reason"] == "OUTSIDE_LOOKBACK"


def test_end_to_end_original_article_integrity_and_past_rebuild(tmp_path):
    with ResearchStore(tmp_path) as store:
        c, p = config(), panel()
        run_discovery(store, p, c, Fetcher())
        assert verify_discovery(store, p)["verified_original_documents"] == 1
        cutoff = now_text()
        report = build_discovery_report(store, p, {"sources": []}, c, as_of=cutoff)
        assert report["news_discovery"]["panel_companies_with_mentions"] == ["INFY"]
        assert report["packets"][0]["news_discovery"]["document_ids"]
        assert report["packets"][0]["forecast"] is None
        assert not report["news_discovery"]["full_market_coverage"]
        past = build_discovery_report(store, p, {"sources": []}, c, as_of='2026-01-01T00:00:00Z')
        assert past["news_discovery"]["item_count"] == 0
        assert past["news_discovery"]["document_count"] == 0
        assert past["news_discovery"]["attempts"] == []
        # Wrapper metadata changes but substantive article identity stays the same.
        changed = Fetcher({FEED: feed(), URL: article() + b'<!-- wrapper v2 -->'})
        run_discovery(store, p, c, changed)
        assert len(store.records("news_document")) == 1
        assert build_discovery_report(store, p, {"sources": []}, c, as_of=cutoff) == report


def test_changed_article_creates_new_version_without_rewriting_old(tmp_path):
    with ResearchStore(tmp_path) as store:
        run_discovery(store, panel(), config(), Fetcher())
        first = store.records("news_document")[0]
        body = 'Infosys (NSE: INFY) corrects its prior announcement. The investment is cancelled. ' * 3
        run_discovery(store, panel(), config(), Fetcher({FEED: feed(), URL: article(body=body)}))
        assert len(store.records("news_document")) == 2
        assert first in store.records("news_document")
        assert verify_discovery(store, panel())["verified_original_documents"] == 2


def test_corrupted_article_is_not_validated_by_record_hash_only(tmp_path):
    with ResearchStore(tmp_path) as store:
        run_discovery(store, panel(), config(), Fetcher())
        doc = store.records("news_document")[0]
        (store.objects / doc["raw_sha256"]).write_bytes(b'changed')
        with pytest.raises(EvidenceError, match="digest"):
            verify_discovery(store, panel())


def test_future_date_and_current_day_uncertainty_are_different():
    now = '2026-09-17T09:00:00Z'
    assert temporal_state({"publication": publication('2026-09-18T09:00:00Z')}, now, 7) == 'FUTURE_PUBLICATION'
    assert temporal_state({"publication": publication('2026-09-17')}, now, 7) == 'DATE_ONLY_CURRENT_DAY'


def test_no_record_is_promoted_to_numeric_evidence(tmp_path):
    with ResearchStore(tmp_path) as store:
        run_discovery(store, panel(), config(), Fetcher())
        assert store.records("evidence") == []


def test_scope_rejects_redirect_before_requesting_other_resource():
    class Response:
        def __init__(self, status, **headers):
            self.status_code, self.headers = status, headers
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def iter_content(self, chunk_size):
            yield b''
    class Session:
        def __init__(self):
            self.headers, self.urls = {}, []
            self.results = [Response(404), Response(302, Location='/news-releases/another-302899999.html')]
        def get(self, url, **kwargs):
            self.urls.append(url)
            return self.results.pop(0)
    session = Session()
    with pytest.raises(SourceBlocked, match='scope'):
        PublicFetcher(session=session, delay=0).fetch(URL, url_guard=lambda u: resource_key(u) == resource_key(URL))
    assert len(session.urls) == 2


def test_reverted_article_is_latest_observation_without_retimestamping(tmp_path):
    with ResearchStore(tmp_path) as store:
        run_discovery(store, panel(), config(), Fetcher())
        original = store.records("news_document")[0]
        changed = article(body='Infosys revises its release. The announced order is cancelled. ' * 4)
        run_discovery(store, panel(), config(), Fetcher({FEED: feed(), URL: changed}))
        run_discovery(store, panel(), config(), Fetcher())
        report = build_discovery_report(store, panel(), {"sources": []}, config(), as_of=now_text())
        latest = [r for r in report["news_discovery"]["stories"] if r["version_state"] == 'LATEST_OBSERVED_VERSION']
        assert len(latest) == 1
        assert latest[0]["document_id"] == original["document_id"]
        assert latest[0]["first_seen_at"] == original["first_seen_at"]


def test_failed_latest_document_fetch_remains_visible_with_old_document(tmp_path):
    with ResearchStore(tmp_path) as store:
        run_discovery(store, panel(), config(), Fetcher())
        run_discovery(store, panel(), config(), Fetcher({FEED: feed(), URL: SourceBlocked('403')}))
        report = build_discovery_report(store, panel(), {"sources": []}, config(), as_of=now_text())
        assert report['news_discovery']['stories'][0]['latest_fetch_status'] == 'BLOCKED'
        assert report['news_discovery']['stories'][0]['version_state'] == 'LATEST_OBSERVED_VERSION'


