
from typing import TypedDict


class SpendlyContext(TypedDict):
    """Trusted context supplied by the authenticated backend."""

    user_id: int
