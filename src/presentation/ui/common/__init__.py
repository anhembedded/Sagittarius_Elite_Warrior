"""What is left of `ui/common` re-exports only what still lives here.

`EPIC-025` PR 1.6c moved `ActionOwnershipTracker` and its three companion
types into `support/ui_kit`, and this file does **not** re-export them from
there. A re-export would work — the legacy tree may import `support/**`
whole — and that is exactly why it would be wrong: it leaves every consumer
naming a package the epic is dissolving (`EPIC-025E` step 4 deletes
`ui/common` outright), so the import would have to be rewritten later
anyway, one migration later, with nothing failing in between to say so.
The 42 import sites were rewritten instead.
"""

from .base_event_logger import BaseEventLogger

__all__ = ["BaseEventLogger"]
