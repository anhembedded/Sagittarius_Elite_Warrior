from enum import Enum


class ExportFileFormat(str, Enum):
    """
    @brief The file formats `ExportMarketDataCommand` can write klines to.
    """

    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"
