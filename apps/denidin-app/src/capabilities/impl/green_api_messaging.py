"""Green API messaging provider implementation (Feature 055, REQ-CAP-001).

The existing (and, as of this feature, only) messaging_provider implementation -
identical mechanics to what `Tenant.start()` did inline before this phase, just
moved behind the `MessagingProvider` interface so a future second implementation
needs only a new class + a registry entry (REQ-CAP-003), never a `Tenant`/
`AIHandler` code change.
"""

from typing import Any, Callable

from src.capabilities.messaging_provider import MessagingProvider


class GreenAPIMessagingProvider(MessagingProvider):
    """Builds a tenant's Green API bot from its own `green_api` credentials."""

    def build_bot(self, tenant: Any, bot_factory: Callable[..., Any]) -> Any:
        return bot_factory(tenant.green_api["instance_id"], tenant.green_api["api_token"])
