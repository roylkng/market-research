from marketlab.ss002_l001_pilot import FAMILIES, select_pilot_sample


def _sources():
    events=[]; docs=[]
    for family in FAMILIES:
        for i in range(8):
            eid=f"{family}-E{i}"
            doc=f"{family}-D{i}"
            symbol=f"{family[:3]}{i}"
            events.append({
                "announcement_id":eid,
                "symbol":symbol,
                "mapping_state":"CURRENT_INVESTABLE_IDENTITY",
                "special_situation_categories":[family],
                "exchange_published_at_utc":f"2026-10-{i+1:02d}T10:00:00Z",
            })
            docs.append({
                "document_id":doc,
                "extraction_state":"READY",
                "event_ids":[eid],
                "symbols":[symbol],
                "categories":[family],
                "source_url":"https://nsearchives.nseindia.com/x.pdf",
                "segment_manifest_sha256":"a"*64,
                "segment_count":1,
            })
    p2={
        "census_id":"SS002-D001-P2-v1",
        "census_sha256":"ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071",
        "events":events,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    d3={
        "corpus_id":"SS002-D003-v1",
        "corpus_sha256":"92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce",
        "promotion_allowed_to_l001":True,
        "documents":docs,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    return p2,d3


def test_sample_selects_six_latest_unique_per_family():
    p2,d3=_sources()
    result=select_pilot_sample(p2=p2,d003=d3)
    assert result["selected_document_count"]==30
    assert all(result["family_counts"][family]==6 for family in FAMILIES)
    for family in FAMILIES:
        rows=[r for r in result["selections"] if r["family"]==family]
        assert [r["family_rank"] for r in rows]==list(range(1,7))
        assert rows[0]["exchange_published_at_utc"] > rows[-1]["exchange_published_at_utc"]
