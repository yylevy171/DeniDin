"""Messaging provider capability interface (Feature 055: Multi-Tenancy, REQ-CAP-001).

See specs/in-progress/055-multiple-clients-godfathers/spec.md REQ-CAP-001/003/004 and
research.md §5: a messaging provider is a DI-resolved interface + implementation,
selected per tenant via `Tenant.capability_selection['messaging_provider']`
(`src/capabilities/registry.py`). Adding a new implementation (a future WhatsApp
Cloud API provider, say) means writing a new class here and registering it in
`registry.py` - never touching `Tenant`/`AIHandler`/`denidin.py` dispatch code.

Unlike the invoicing capability, messaging is NOT eligible for degraded start
(REQ-CAP-005 explicitly excludes it) - every tenant MUST have a working messaging
provider to start at all, since it's the tenant's only way to be reached.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable


class MessagingProvider(ABC):
    """Builds the concrete bot/client instance a tenant listens for messages
    through, from that tenant's own credentials."""

    @abstractmethod
    def build_bot(self, tenant: Any, bot_factory: Callable[..., Any]) -> Any:
        """Construct and return this tenant's bot/client instance.

        Args:
            tenant: the `Tenant` this bot belongs to (reads its own credentials,
                e.g. `tenant.green_api`, from here).
            bot_factory: the concrete class/callable to construct with - injectable
                so tests can supply a fake instead of making a real network call
                (real bot construction always makes at least one real HTTP call).
        """
