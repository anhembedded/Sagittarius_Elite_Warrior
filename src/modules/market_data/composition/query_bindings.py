"""market_data's read side: the seven queries and their handlers.

Same routing table as `command_bindings.py`, opposite direction: a query
returns an answer and writes nothing. Separate file because the two lists change
independently — a new report is a query, a new repair is a command, and neither
edit should make a reader scroll past the other.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    AuditDatabaseIntegrityQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_database_gaps import (
    GetDatabaseGapsQuery,
    GetDatabaseGapsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_database_status import (
    GetDatabaseStatusQuery,
    GetDatabaseStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.scan_all_databases import (
    ScanAllDatabasesQuery,
    ScanAllDatabasesQueryHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_queries(container: IContainer) -> None:
    """Route each market_data query type to the handler that answers it."""
    container.bind(GetDatabaseStatusQuery, GetDatabaseStatusQueryHandler)
    container.bind(GetDatabaseGapsQuery, GetDatabaseGapsQueryHandler)
    container.bind(AuditDatabaseIntegrityQuery, AuditDatabaseIntegrityQueryHandler)
    container.bind(ScanAllDatabasesQuery, ScanAllDatabasesQueryHandler)
