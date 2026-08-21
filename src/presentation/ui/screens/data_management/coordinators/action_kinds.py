from enum import Enum


class DataManagementActionKind(str, Enum):
    """Lifecycle action kinds tracked for the DataManagement screen."""

    AUTO_DISCOVER = "AUTO_DISCOVER"
    SCAN_STATUS = "SCAN_STATUS"
    SCAN_ALL = "SCAN_ALL"
    CLEAR_DATA = "CLEAR_DATA"
    PURGE_ALL = "PURGE_ALL"
    VACUUM = "VACUUM"
    SYNC_SINGLE = "SYNC_SINGLE"
    SYNC_BULK = "SYNC_BULK"
    INSPECT_GAPS = "INSPECT_GAPS"
    REPAIR_GAP = "REPAIR_GAP"
    REPAIR_ALL_GAPS = "REPAIR_ALL_GAPS"
    INSPECT_KLINES = "INSPECT_KLINES"
    RUN_AUDIT = "RUN_AUDIT"
