from __future__ import annotations

import runpy

from marketlab.pf001_marketdata import PF001BenchmarkDailyBar

_ORIGINAL_TO_DICT = PF001BenchmarkDailyBar.to_dict


def _h024_attribution_dict(self: PF001BenchmarkDailyBar) -> dict[str, object]:
    """Expose the frozen H024 benchmark attribution keys without changing PF001."""
    payload = _ORIGINAL_TO_DICT(self)
    payload["open"] = self.open_price
    payload["close"] = self.close_price
    return payload


PF001BenchmarkDailyBar.to_dict = _h024_attribution_dict
runpy.run_path("scripts/run_h024_historical_challenge.py", run_name="__main__")
