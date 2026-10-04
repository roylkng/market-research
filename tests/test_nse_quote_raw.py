from marketlab.nse import NSEClient


def test_quote_equity_with_raw_preserves_exact_bytes(monkeypatch):
    client = NSEClient()
    payload = {
        "info": {"symbol": "RELIANCE", "isin": "INE002A01018"},
        "industryInfo": {"basicIndustry": "Refineries & Marketing"},
    }
    raw = b'{"info":{"symbol":"RELIANCE"}}'
    calls = []

    def fake(endpoint, *, params):
        calls.append((endpoint.name, params))
        return payload, raw

    monkeypatch.setattr(client, "_json_get_with_raw", fake)
    observed_payload, observed_raw = client.quote_equity_with_raw("RELIANCE")

    assert observed_payload == payload
    assert observed_raw == raw
    assert calls == [("quote_equity", {"symbol": "RELIANCE"})]


def test_quote_equity_trade_info_with_raw_preserves_exact_bytes(monkeypatch):
    client = NSEClient()
    payload = {
        "marketDeptOrderBook": {
            "tradeInfo": {
                "totalMarketCap": 1000.0,
                "ffmc": 400.0,
            }
        }
    }
    raw = b'{"marketDeptOrderBook":{"tradeInfo":{}}}'
    calls = []

    def fake(endpoint, *, params):
        calls.append((endpoint.name, params))
        return payload, raw

    monkeypatch.setattr(client, "_json_get_with_raw", fake)
    observed_payload, observed_raw = client.quote_equity_trade_info_with_raw("TEST")

    assert observed_payload == payload
    assert observed_raw == raw
    assert calls == [
        ("quote_equity", {"symbol": "TEST", "section": "trade_info"})
    ]
