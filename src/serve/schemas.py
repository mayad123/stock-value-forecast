"""Request/response schemas for the prediction API."""

from typing import Dict, List, Optional


from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Input for /predict.
    Either provide (ticker, as_of) and features are looked up from processed data, or
    provide (ticker, as_of) and optional features: a named mapping of feature name -> value.
    When features is provided, it must contain exactly the trained feature_columns (no missing,
    no extra); values are re-ordered into trained order for inference.
    """

    ticker: str = Field(..., min_length=1, max_length=10, description="Stock symbol (e.g. AAPL)")
    as_of: str = Field(..., description="As-of date for features (YYYY-MM-DD)")
    horizon: Optional[int] = Field(1, ge=1, le=30, description="Forward horizon in days (default 1)")
    features: Optional[Dict[str, float]] = Field(
        None,
        description="Optional: feature name -> value. Must match trained feature_columns exactly (re-ordered internally)",
    )


class PredictResponse(BaseModel):
    """Output from /predict."""

    prediction: float = Field(..., description="Predicted trend score in [-1, 1]")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in [0, 1]")
    ticker: str = Field(..., description="Echo of requested ticker")
    as_of: str = Field(..., description="Date used for features")
    horizon: int = Field(1, description="Horizon in days")
    model_version: Optional[str] = Field(None, description="Model/run ID used for this prediction")


class ModelInfoResponse(BaseModel):
    """Output from /model_info."""

    model_version: str = Field(..., description="Run ID / model artifact version")
    dataset_version: str = Field(..., description="Processed dataset version used for training")
    num_features: int = Field(..., description="Number of feature columns expected by the model")
    feature_schema_fingerprint: str = Field(
        ...,
        description="Stable identifier derived from feature_columns (for contract validation)",
    )
    feature_columns: list = Field(default_factory=list, description="Feature names in trained order")
    training_window: dict = Field(default_factory=dict, description="Train/val date boundaries")
    tickers: Optional[List[str]] = Field(
        None,
        description="Tickers supported by the model (trained ticker set). None if no ticker encoding.",
    )
    ticker_encoding_fingerprint: Optional[str] = Field(
        None,
        description="Fingerprint of the ticker encoding mapping (for train/serve consistency).",
    )


class PredictionOptionsResponse(BaseModel):
    """Output from /prediction_options. Valid (ticker, date, horizon) choices for the UI."""

    tickers: List[str] = Field(default_factory=list, description="Tickers that have processed feature rows.")
    dates_by_ticker: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Per ticker, sorted list of as-of dates available in processed data.",
    )
    horizons: List[int] = Field(
        default_factory=lambda: [1],
        description="Horizon values (days) supported by the model (e.g. [1] for 1-day forward return).",
    )
