"""Request/response schemas for the prediction API."""

from typing import Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Input for /predict."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Stock symbol (e.g. AAPL)")
    as_of: str = Field(..., description="As-of date for features (YYYY-MM-DD)")
    horizon: Optional[int] = Field(1, ge=1, le=30, description="Forward horizon in days (default 1)")


class PredictResponse(BaseModel):
    """Output from /predict."""

    prediction: float = Field(..., description="Predicted trend score in [-1, 1]")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in [0, 1]")
    ticker: str = Field(..., description="Echo of requested ticker")
    as_of: str = Field(..., description="Date used for features")
    horizon: int = Field(1, description="Horizon in days")


class ModelInfoResponse(BaseModel):
    """Output from /model_info."""

    model_version: str = Field(..., description="Run ID / model artifact version")
    training_window: dict = Field(..., description="Train/val date boundaries")
    dataset_version: str = Field(..., description="Processed dataset version used for training")
    feature_columns: list = Field(default_factory=list, description="Feature names expected by model")
