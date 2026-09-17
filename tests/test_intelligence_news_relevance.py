from marketlab.intelligence_discovery import select_documents


def entry(symbol=None, exploration=0):
    return {"item": {"item_id": "test-id", "resource_key": "prn:302800001",
        "url": "https://www.prnewswire.com/news-releases/test-302800001.html",
        "item_status": "DISCOVERED", "publication": {"value": None, "precision": "UNKNOWN"},
        "topics": [], "mentions": {"panel_symbols": [],
        "unverified_nse_symbols": [symbol] if symbol else [], "bse_codes_for_review": []}},
        "source": {"source_id": "test", "access": "PUBLIC_DOCUMENTS", "region": "IN",
        "unlinked_document_budget": exploration, "article_hosts": ["www.prnewswire.com"],
        "article_path_pattern": r"/news-releases/[^/]+-\d{8,12}\.html"}}


def select(rows):
    return select_documents(rows, as_of="2026-09-17T09:00:00Z", budget=12, lookback_days=7)


def test_unrelated_promotional_releases_cannot_exhaust_document_budget():
    chosen, deferred = select([entry()])
    assert not chosen and deferred[0]["reason"] == "NO_COMPANY_LINK_EXPLORATION_LIMIT"
    chosen, deferred = select([entry(exploration=1)])
    assert len(chosen) == 1 and not deferred


def test_outside_panel_exchange_identifier_is_not_filtered_out():
    chosen, _ = select([entry(symbol="NEWCO")])
    assert len(chosen) == 1
    assert chosen[0]["item"]["mentions"]["unverified_nse_symbols"] == ["NEWCO"]
