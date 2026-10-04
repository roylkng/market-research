from marketlab.ha001_assets import derive_asset_anomalies


def _f(v):
    return {"status":"READY","unit_ref":"INR","value":v}

def test_asset_flags_follow_frozen_thresholds():
    facts={
      "total_equity":_f(100),"total_assets":_f(200),"cash":_f(40),
      "current_investments":_f(20),"noncurrent_investments":_f(30),
      "borrowings_current":_f(10),"borrowings_noncurrent":_f(10),
      "investment_property":_f(20),"ppe":_f(40),"capital_work_in_progress":_f(20),
      "goodwill":_f(5),"other_intangibles":_f(5),"inventories":_f(20),"trade_receivables":_f(20),
    }
    r=derive_asset_anomalies(facts)
    assert "LIQUID_ASSET_HEAVY" in r["opportunity_flags"]
    assert "INVESTMENT_HOLDING_HEAVY" in r["opportunity_flags"]
    assert "INVESTMENT_PROPERTY_MATERIAL" in r["opportunity_flags"]
    assert "CWIP_CAPACITY_INFLECTION" in r["opportunity_flags"]
    assert not r["caution_flags"]

def test_missing_fact_is_not_imputed():
    facts={"total_equity":_f(100),"cash":_f(100)}
    r=derive_asset_anomalies(facts)
    assert r["ratios"]["net_financial_assets_to_equity"] is None
    assert "LIQUID_ASSET_HEAVY" not in r["opportunity_flags"]
