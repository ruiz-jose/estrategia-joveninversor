import pandas as pd


def split_walk_forward(df: pd.DataFrame, n_folds: int = 4, train_ratio: float = 0.7):
    """
    Chronological walk-forward split: divides df into n_folds contiguous, non-overlapping
    blocks (in time order, no shuffling). Within each block, the first train_ratio portion
    is used to fit/select parameters and the remainder is held out as out-of-sample test data.

    Yields ``(train_df, test_df, test_warmup_df)``.  ``test_warmup_df`` contains
    only candles available before the test segment and must be used exclusively
    to initialize indicators, never to trade or select parameters.
    """
    n = len(df)
    fold_size = n // n_folds

    for k in range(n_folds):
        start = k * fold_size
        end = start + fold_size if k < n_folds - 1 else n
        fold = df.iloc[start:end].reset_index(drop=True)

        split_idx = int(len(fold) * train_ratio)
        train = fold.iloc[:split_idx].reset_index(drop=True)
        test = fold.iloc[split_idx:].reset_index(drop=True)
        test_warmup = df.iloc[:start + split_idx].reset_index(drop=True)

        yield train, test, test_warmup
