import time

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

from .base import Action, BaseStrategy, Signal
from .indicators import macd, rsi

RETRAIN_INTERVAL_SECONDS = 7 * 24 * 3600
MIN_TRAINING_ROWS = 60
CONFIDENCE_THRESHOLD = 0.6
FEATURE_COLUMNS = ["return_1", "rsi", "macd_diff", "volatility", "volume_z"]


class MLPredictorStrategy(BaseStrategy):
    name = "ml_predictor"

    def __init__(self):
        self.model = None
        self.last_trained_at: float = 0.0

    def _build_features(self, candles: list[dict]) -> pd.DataFrame:
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        df = pd.DataFrame({"close": closes, "volume": volumes})
        df["return_1"] = df["close"].pct_change()
        df["rsi"] = rsi(closes, 14)
        macd_line, signal_line = macd(closes)
        df["macd_diff"] = macd_line - signal_line
        df["volatility"] = df["return_1"].rolling(10).std()
        volume_std = df["volume"].rolling(20).std().replace(0, 1e-12)
        df["volume_z"] = (df["volume"] - df["volume"].rolling(20).mean()) / volume_std
        return df

    def _train(self, df: pd.DataFrame) -> None:
        target = (df["close"].shift(-1) > df["close"]).astype(int)
        data = pd.concat([df[FEATURE_COLUMNS], target.rename("target")], axis=1).dropna()
        if len(data) > 0:
            data = data[:-1]  # Exclude last row to avoid spurious target from NaN comparison
        if len(data) < MIN_TRAINING_ROWS:
            self.model = None
            return
        model = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        model.fit(data[FEATURE_COLUMNS], data["target"])
        self.model = model
        self.last_trained_at = time.time()

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        if len(candles) < MIN_TRAINING_ROWS + 5:
            return Signal(Action.HOLD, symbol)

        df = self._build_features(candles)
        if self.model is None or (time.time() - self.last_trained_at) > RETRAIN_INTERVAL_SECONDS:
            self._train(df)
        if self.model is None:
            return Signal(Action.HOLD, symbol)

        latest = df[FEATURE_COLUMNS].iloc[[-1]]
        if latest.isnull().values.any():
            return Signal(Action.HOLD, symbol)

        proba_up = self.model.predict_proba(latest)[0][1]
        if proba_up >= CONFIDENCE_THRESHOLD:
            return Signal(Action.BUY, symbol, confidence=proba_up)
        if proba_up <= (1 - CONFIDENCE_THRESHOLD):
            return Signal(Action.SELL, symbol, confidence=1 - proba_up)
        return Signal(Action.HOLD, symbol)
