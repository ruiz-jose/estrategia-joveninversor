import pandas as pd
import numpy as np

def calculate_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Calculate Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False).mean()

def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = "close"):
    """Calculate Moving Average Convergence Divergence (MACD)."""
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calculate_adx(df: pd.DataFrame, period: int = 14):
    """Calculate ADX (Average Directional Index) and +DI / -DI."""
    df_copy = df.copy()
    
    up_move = df_copy["high"] - df_copy["high"].shift()
    down_move = df_copy["low"].shift() - df_copy["low"]
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr = calculate_atr(df_copy, period)
    
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr)
    
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1/period, adjust=False).mean().fillna(0)
    
    return adx, plus_di, minus_di

def calculate_squeeze_momentum(df: pd.DataFrame, bb_length: int = 20, bb_mult: float = 2.0, kc_length: int = 20, kc_mult: float = 1.5):
    """Calculate Squeeze Momentum Indicator."""
    basis = df["close"].rolling(window=bb_length).mean()
    dev = bb_mult * df["close"].rolling(window=bb_length).std()
    upper_bb = basis + dev
    lower_bb = basis - dev
    
    ma_kc = df["close"].rolling(window=kc_length).mean()
    range_kc = calculate_atr(df, kc_length)
    upper_kc = ma_kc + range_kc * kc_mult
    lower_kc = ma_kc - range_kc * kc_mult
    
    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    
    highest_high = df["high"].rolling(window=kc_length).max()
    lowest_low = df["low"].rolling(window=kc_length).min()
    m1 = (highest_high + lowest_low) / 2
    m2 = df["close"].rolling(window=kc_length).mean()
    val = df["close"] - ((m1 + m2) / 2)
    
    momentum = val.ewm(span=5, adjust=False).mean()
    return squeeze_on, momentum

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    """
    Calculate Supertrend Indicator.
    Returns (supertrend_line, direction) where direction is 1 (bullish green) or -1 (bearish red).
    """
    df = df.copy()
    atr = calculate_atr(df, period)
    
    hl2 = (df["high"] + df["low"]) / 2
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)
    
    final_ub = np.zeros(len(df))
    final_lb = np.zeros(len(df))
    supertrend = np.zeros(len(df))
    direction = np.zeros(len(df))
    
    for i in range(1, len(df)):
        if basic_ub.iloc[i] < final_ub[i-1] or df["close"].iloc[i-1] > final_ub[i-1]:
            final_ub[i] = basic_ub.iloc[i]
        else:
            final_ub[i] = final_ub[i-1]
            
        if basic_lb.iloc[i] > final_lb[i-1] or df["close"].iloc[i-1] < final_lb[i-1]:
            final_lb[i] = basic_lb.iloc[i]
        else:
            final_lb[i] = final_lb[i-1]
            
        if direction[i-1] == 1:
            if df["close"].iloc[i] < final_lb[i]:
                direction[i] = -1
                supertrend[i] = final_ub[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lb[i]
        else:
            if df["close"].iloc[i] > final_ub[i]:
                direction[i] = 1
                supertrend[i] = final_lb[i]
            else:
                direction[i] = -1
                supertrend[i] = final_ub[i]
                
    return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

def calculate_volume_profile(df: pd.DataFrame, bins: int = 24):
    """Calculate Volume Profile Point of Control (POC) and Value Area High/Low safely."""
    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    if price_min == price_max:
        return {"poc": price_min, "vah": price_max, "val": price_min}
    
    price_bins = np.linspace(price_min, price_max, bins + 1)
    price_categories = pd.cut(df["close"], bins=price_bins)
    
    vol_by_bin = df.groupby(price_categories, observed=False)["volume"].sum()
    poc_idx = vol_by_bin.idxmax()
    
    if poc_idx is not None and hasattr(poc_idx, 'left') and hasattr(poc_idx, 'right'):
        poc_price = (poc_idx.left + poc_idx.right) / 2
    else:
        poc_price = (price_min + price_max) / 2
    
    return {
        "poc": float(poc_price),
        "vah": float(price_max * 0.98),
        "val": float(price_min * 1.02)
    }

def add_all_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Add all technical indicators including Supertrend to DataFrame."""
    df = df.copy()
    
    # EMAs
    df["ema_20"] = calculate_ema(df, int(config.get("ema_fast", 20)))
    df["ema_50"] = calculate_ema(df, int(config.get("ema_medium", 50)))
    df["ema_200"] = calculate_ema(df, int(config.get("ema_slow", 200)))
    
    # RSI
    df["rsi"] = calculate_rsi(df, int(config.get("rsi_period", 14)))
    
    # MACD
    macd, signal, hist = calculate_macd(
        df, 
        int(config.get("macd_fast", 12)), 
        int(config.get("macd_slow", 26)), 
        int(config.get("macd_signal", 9))
    )
    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = hist
    
    # ATR
    df["atr"] = calculate_atr(df, int(config.get("atr_period", 14)))
    
    # ADX
    adx, plus_di, minus_di = calculate_adx(df, int(config.get("adx_period", 14)))
    df["adx"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di
    
    # Squeeze Momentum
    squeeze_on, sqz_mom = calculate_squeeze_momentum(
        df,
        int(config.get("squeeze_bb_length", 20)),
        float(config.get("squeeze_bb_mult", 2.0)),
        int(config.get("squeeze_kc_length", 20)),
        float(config.get("squeeze_kc_mult", 1.5))
    )
    df["squeeze_on"] = squeeze_on
    df["squeeze_mom"] = sqz_mom
    
    # Supertrend
    st_line, st_dir = calculate_supertrend(
        df,
        int(config.get("supertrend_period", 10)),
        float(config.get("supertrend_mult", 3.0))
    )
    df["supertrend"] = st_line
    df["st_direction"] = st_dir
    
    return df
