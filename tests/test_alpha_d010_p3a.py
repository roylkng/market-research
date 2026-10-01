from datetime import date

from marketlab.alpha_d010_p3a import inspect_short_raw


def test_p3a_records_raw_row_shape_without_semantic_coercion():
    raw = (
        b"Security Name,Symbol Name,Trade Date,Quantity\n"
        b"STATE BANK OF INDIA,SBIN,25-SEP-2026,100\n"
        b",,Total,100\n"
    )
    result = inspect_short_raw(
        raw,
        session_date=date(2026, 9, 25),
    )
    assert result["header"][1] == "Symbol Name"
    assert result["nonempty_data_row_count"] == 2
    assert result["trade_date_counts"]["25-SEP-2026"] == 1
    assert result["trade_date_counts"]["Total"] == 1
    assert result["empty_symbol_count"] == 1
    assert result["quantity_parse_failure_count"] == 0
