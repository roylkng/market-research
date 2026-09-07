from marketlab.nifty200_history import load_registry, reconstruct_freezes


REGISTRY = "registry/nifty200_historical_membership_v1.yaml"


def _snapshots():
    return {item["quarter_id"]: item for item in reconstruct_freezes(load_registry(REGISTRY))}


def test_every_freeze_has_exactly_200_regular_nifty200_members():
    snapshots = _snapshots()
    assert set(snapshots) == {"FY25-Q4", "FY26-Q1", "FY26-Q2", "FY26-Q3", "FY26-Q4", "FY27-Q1"}
    assert all(item["regular_member_count"] == 200 for item in snapshots.values())
    assert all(item["investable_member_count"] == 200 for item in snapshots.values())
    assert all(item["non_financial_member_count"] < 200 for item in snapshots.values())


def test_demerger_dummies_exist_only_at_the_freezes_where_they_should():
    snapshots = _snapshots()
    assert snapshots["FY25-Q4"]["dummy_symbols"] == []
    assert snapshots["FY26-Q1"]["dummy_symbols"] == ["DUMMYABFRL", "DUMMYSIEMS"]
    assert snapshots["FY26-Q2"]["dummy_symbols"] == []
    assert snapshots["FY26-Q3"]["dummy_symbols"] == ["DUMMYHDLVR"]
    assert snapshots["FY26-Q4"]["dummy_symbols"] == []
    assert snapshots["FY27-Q1"]["dummy_symbols"] == [
        "DUMMYVEDL1",
        "DUMMYVEDL2",
        "DUMMYVEDL3",
        "DUMMYVEDL4",
    ]


def test_symbol_renames_are_point_in_time_and_preserve_membership():
    snapshots = _snapshots()
    q1_symbols = {item["symbol"] for item in snapshots["FY26-Q1"]["regular_members"]}
    q3_symbols = {item["symbol"] for item in snapshots["FY26-Q3"]["regular_members"]}
    q4_symbols = {item["symbol"] for item in snapshots["FY26-Q4"]["regular_members"]}

    assert "ETERNAL" in q1_symbols and "ZOMATO" not in q1_symbols
    assert "TMPV" in q3_symbols and "TATAMOTORS" not in q3_symbols
    assert "LTM" in q4_symbols and "LTIM" not in q4_symbols


def test_financial_filter_is_explicit_and_dummies_never_enter_nonfinancial_universe():
    snapshots = _snapshots()
    for snapshot in snapshots.values():
        non_financial = set(snapshot["non_financial_symbols"])
        assert not any(symbol.startswith("DUMMY") for symbol in non_financial)
        financial = {
            item["symbol"]
            for item in snapshot["regular_members"]
            if item["financial"]
        }
        assert financial.isdisjoint(non_financial)
