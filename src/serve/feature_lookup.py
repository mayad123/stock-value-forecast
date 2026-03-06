"""
Feature lookup: find a feature row by (ticker, as_of) from loaded features data.

Used when the client does not send features in the request; we look up from processed data.
"""

from typing import Any, Dict, Optional

from src.serve.state import ServeContext


def lookup_features(ctx: ServeContext, ticker: str, as_of: str) -> Optional[Dict[str, Any]]:
    """
    Return feature row for (ticker, date <= as_of), latest date first, as a dict.
    Returns None if no row found or features_df is empty.
    """
    if ctx.features_df is None or ctx.features_df.empty:
        return None
    df = ctx.features_df
    subset = df[
        (df["ticker"].astype(str).str.upper() == ticker.upper())
        & (df["date"].astype(str) <= as_of)
    ]
    if subset.empty:
        return None
    subset = subset.sort_values("date", ascending=False)
    row = subset.iloc[0]
    return row.to_dict() if hasattr(row, "to_dict") else dict(row)
