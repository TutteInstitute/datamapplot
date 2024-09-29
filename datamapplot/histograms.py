import pandas as pd
import numpy as np
from typing import Tuple, Optional

_NAME_TO_FREQ_CODE = {
    "year": "YS",
    "y": "YS",
    "quarter": "QS",
    "Q": "QS",
    "q": "QS",
    "month": "MS",
    "M": "MS",
    "day": "D",
    "d": "D",
    "hour": "H",
    "h": "H",
    "minute": "T",
    "min": "T",
    "m": "T",
    "second": "S",
    "sec": "S",
    "s": "S",
}

_NAME_TO_PERIOD_CODE = {
    "year": "Y",
    "y": "Y",
    "quarter": "Q",
    "Q": "Q",
    "q": "Q",
    "month": "M",
    "M": "",
    "day": "D",
    "d": "D",
    "hour": "h",
    "h": "h",
    "minute": "min",
    "min": "min",
    "m": "min",
    "second": "s",
    "sec": "s",
    "s": "s",
}


def generate_bins_from_numeric_data(
    data: pd.Series,
    n_bins: int = 20,
    histogram_range: Optional[Tuple[float, float]] = None,
):
    """
    Generate bins for numeric data.

    Parameters
    ----------
    data : pd.Series or np.ndarray
        The data to bin.
    n_bins : int
        The number of bins to generate.

    Returns
    -------
    pd.DataFrame
    A DataFrame with the following columns:
        - id: The bin id.
        - count: The number of data points in the bin.
        - indices: The indices of the data points in the bin.
        - min_value: The minimum value of the bin.
        - max_value: The maximum value of the bin.
        - mean_value: The mean value of the bin.

    pd.Series
    A Series with the bin ids, one per entry in the data.
    """
    if isinstance(data, np.ndarray):
        data = pd.Series(data)

    if histogram_range is None:
        bins_ids, bin_edges = pd.cut(data, bins=n_bins, labels=False, retbins=True)
    else:
        from_value, to_value = histogram_range
        if isinstance(from_value, pd.Timestamp):
            bins = pd.date_range(from_value, to_value, periods=n_bins)
        else:
            bins = np.linspace(from_value, to_value, n_bins)
        bins_ids, bin_edges = pd.cut(data, bins, labels=False, retbins=True)
        if not np.all(np.isfinite(bins_ids)):
            bins_ids = np.where(data < from_value, 0, bins_ids)
            bins_ids = np.where(data > to_value, len(bin_edges) - 1, bins_ids)

    all_bins = pd.DataFrame({"id": range(n_bins)})

    bin_data = (
        data.groupby(bins_ids, group_keys=True)
        .agg(count="count", indices=lambda x: list(x.index))
        .reset_index(names=["id"])
    )

    bin_data = all_bins.merge(bin_data, on="id", how="left")

    bin_data["min_value"] = bin_edges[:-1]
    bin_data["max_value"] = bin_edges[1:]
    # lower bin plus difference over two to allow to dates/times to work with averages as well
    bin_data["mean_value"] = bin_edges[:-1] + (bin_edges[1:] - bin_edges[:-1]) / 2
    bin_data["count"] = bin_data["count"].fillna(0)
    bin_data["indices"] = bin_data["indices"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    return bin_data, bins_ids.astype(np.int16).rename("bin_id")


def generate_bins_from_categorical_data(
    data: pd.Series,
    max_bins: int = 20,
    histogram_range: Optional[Tuple[float, float]] = None,
):
    """
    Generate bins for categorical data.

    Parameters
    ----------
    data : pd.Series or np.ndarray
        The data to bin.
    max_bins : int
        The maximum number of bins to generate.

    Returns
    -------
    pd.DataFrame
    A DataFrame with the following columns:
        - id: The bin id.
        - count: The number of data points in the bin.
        - indices: The indices of the data points in the bin.
        - min_value: The minimum value of the bin.
        - max_value: The maximum value of the bin.
        - mean_value: The mean value of the bin.

    pd.Series
    A Series with the bin ids, one per entry in the data.
    """
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    top_values = data.value_counts().head(max_bins - 1).index
    bins_ids = data.apply(lambda x: x if x in top_values else "Other")
    bin_data = (
        data.groupby(bins_ids)
        .agg(count="count", indices=lambda x: list(x.index))
        .reset_index(names=["label"])
        .reset_index(names=["id"])
    )

    bin_data["min_value"] = bin_data["id"]
    bin_data["max_value"] = bin_data["id"]
    bin_data["mean_value"] = bin_data["label"]
    bin_data["count"] = bin_data["count"].fillna(0)
    bin_data["indices"] = bin_data["indices"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    return bin_data, bins_ids.map(dict(bin_data[["label", "id"]].values)).astype(
        np.int16
    ).rename("bin_id")


def generate_bins_from_temporal_data(
    data: pd.Series,
    group_by: str = "year",
    histogram_range: Optional[Tuple[float, float]] = None,
):
    """
    Generate bins for temporal data.

    Parameters
    ----------
    data : pd.Series or np.ndarray
        The data to bin.
    group_by : str
        The temporal unit to group by. Can be one of "year", "quarter", "month", "day", "hour", "minute", or "second".

    Returns
    -------
    pd.DataFrame
    A DataFrame with the following columns:
        - id: The bin id.
        - count: The number of data points in the bin.
        - indices: The indices of the data points in the bin.
        - min_value: The minimum value of the bin.
        - max_value: The maximum value of the bin.
        - mean_value: The mean value of the bin.

    pd.Series
    A Series with the bin ids, one per entry in the data.
    """
    if isinstance(data, np.ndarray):
        data = pd.Series(data)
    frequency_code = _NAME_TO_FREQ_CODE.get(group_by, group_by)
    period_code = _NAME_TO_PERIOD_CODE[group_by]

    if histogram_range is None:
        from_date = data.min().to_period(period_code).to_timestamp()
        to_date = (data.max().to_period(period_code) + 1).to_timestamp()
    else:
        from_date, to_date = histogram_range

    bins_ids, bin_edges = pd.cut(
        data,
        pd.date_range(from_date, to_date, freq=frequency_code),
        labels=False,
        retbins=True,
    )
    if not np.all(np.isfinite(bins_ids)):
        bins_ids = np.where(data <= from_date, 0, bins_ids)
        bins_ids = np.where(data >= to_date, len(bin_edges) - 1, bins_ids)
        bins_ids = pd.Series(bins_ids)

    all_bins = pd.DataFrame({"id": range(len(bin_edges) - 1)})

    bin_data = (
        data.groupby(bins_ids, group_keys=True)
        .agg(count="count", indices=lambda x: list(x.index))
        .reset_index(names=["id"])
    )

    bin_data = all_bins.merge(bin_data, on="id", how="left")

    bin_data["min_value"] = bin_edges[:-1]
    bin_data["max_value"] = bin_edges[1:]
    # lower bin plus difference over two to allow to dates/times to work with averages as well
    bin_data["mean_value"] = bin_edges[:-1] + (bin_edges[1:] - bin_edges[:-1]) / 2
    bin_data["count"] = bin_data["count"].fillna(0)
    bin_data["indices"] = bin_data["indices"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    return bin_data, bins_ids.fillna(0).astype(np.int16).rename("bin_id")
