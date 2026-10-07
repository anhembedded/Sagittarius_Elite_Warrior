from dataclasses import dataclass


@dataclass(frozen=True)
class ListVenueKeysQuery:
    """@brief Which venues hold a key, as a fingerprint and where it comes from
    (`BUG-176`). Never the key or the secret."""
