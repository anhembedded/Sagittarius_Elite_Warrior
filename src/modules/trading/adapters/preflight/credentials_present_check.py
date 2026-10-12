"""Each venue has a key, and which source it came from (`EPIC-038F`).

Reports the *source* (environment, file, keyring, ...) and never a value: the
finding holds `CredentialsSource.value` and nothing from `ExchangeCredentials`.
It asks the venue's *stored* key (`VenueContext.credentials_provider`), not the
gated one adapters use, so a mainnet key that can withdraw is present here and
is failed once, by `NoWithdrawPermissionCheck`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)

_PROVIDE = (
    "Provide the key: set the venue's API key and secret environment variables, "
    "or save them in the app's credentials page (a mainnet key goes to the keyring)."
)


class CredentialsPresentCheck(PerVenueCheck):
    check_id = "credentials-present"
    title = "API credentials are present"

    def when_no_venue_is_in_use(self) -> CheckResult:
        return CheckResult.single(
            self.check_id,
            self.title,
            CheckFinding(
                "",
                CheckStatus.FAIL,
                "no venue has a key",
                _PROVIDE,
                CheckCause.CONFIGURATION,
            ),
        )

    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        resolved = self._reads.credentials(scope, name, context)
        if resolved.credentials is not None:
            return CheckFinding(
                name,
                CheckStatus.PASS,
                f"a key is present (source: {resolved.source.value})",
            )
        return CheckFinding(
            name,
            CheckStatus.FAIL,
            "no key is configured",
            _PROVIDE,
            CheckCause.CONFIGURATION,
        )
