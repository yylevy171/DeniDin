"""Capability registry (Feature 055: Multi-Tenancy, REQ-CAP-001/002/003/004/005).

Per-call resolution of a tenant's capability implementation, keyed by the
implementation name in `Tenant.capability_selection` - research.md §5: NOT a
startup-only cached/memoized singleton. Resolution is a plain in-memory dict
lookup (registered implementation instances are stateless, so sharing one
instance across every call/tenant is safe - see `test_capabilities.py`'s
`test_resolve_returns_the_same_registered_instance_every_call`), so there is
nothing to go stale across a tenant's lifetime.

Adding a new implementation of either capability (REQ-CAP-003) means writing the
new class (implementing `MessagingProvider`/`InvoicingProvider`) and adding one
line to the registries below - never touching `Tenant`, `AIHandler`, or
`denidin.py` dispatch code (REQ-CAP-004: no dynamic/runtime plugin loading, this
project's no-monkey-patching rule - CONSTITUTION §XVII).
"""

from typing import Any, Dict, Optional, Union

from src.capabilities.impl.green_api_messaging import GreenAPIMessagingProvider
from src.capabilities.impl.morning_invoicing import MorningInvoicingProvider
from src.capabilities.invoicing_provider import InvoicingProvider
from src.capabilities.messaging_provider import MessagingProvider

# capability_name -> {implementation_name: implementation instance}. Every
# implementation instance is stateless (holds no per-tenant data), so exactly
# one shared instance per implementation name is safe to register and reuse
# across every tenant/call.
_MESSAGING_PROVIDERS: Dict[str, MessagingProvider] = {
    "green_api": GreenAPIMessagingProvider(),
}
_INVOICING_PROVIDERS: Dict[str, InvoicingProvider] = {
    "morning": MorningInvoicingProvider(),
}

# capability_name -> whether it's required to start at all (REQ-CAP-005 excludes
# only messaging_provider from degraded-start eligibility).
_REQUIRED_CAPABILITIES = {"messaging_provider": True, "invoicing_provider": False}


class CapabilityRegistry:
    """Resolves a tenant's configured capability implementation, per call."""

    @staticmethod
    def resolve(
        tenant: Any, capability_name: str
    ) -> Optional[Union[MessagingProvider, InvoicingProvider]]:
        """Return `tenant`'s configured implementation for `capability_name`.

        Returns:
            The registered implementation instance for the name in
            `tenant.capability_selection[capability_name]`.
            `None` only for a legitimately-omitted OPTIONAL capability
            (REQ-CAP-005 - currently just `invoicing_provider`): no selection at
            all, or a selection with no working credential (mirrors
            `Tenant.has_invoicing_provider`'s own rule that a dangling
            selection with no token isn't a functioning capability).

        Raises:
            ValueError: `capability_name` isn't a known capability; the
                capability is required (`messaging_provider`) and has no
                selection at all; or a selection names an implementation that
                isn't registered (a real config error - a typo, or a
                not-yet-implemented provider referenced too early - distinct
                from REQ-CAP-005's legitimate "not configured" case).
        """
        if capability_name not in _REQUIRED_CAPABILITIES:
            raise ValueError(f"Unknown capability: {capability_name!r}")

        registry = (
            _MESSAGING_PROVIDERS if capability_name == "messaging_provider" else _INVOICING_PROVIDERS
        )
        required = _REQUIRED_CAPABILITIES[capability_name]

        implementation_name = tenant.capability_selection.get(capability_name)
        if implementation_name is None:
            if required:
                raise ValueError(
                    f"Tenant {getattr(tenant, 'account_name', '?')!r} has no "
                    f"{capability_name!r} selected (required to start at all)"
                )
            return None

        # REQ-CAP-005: invoicing_provider selected but with no working credential
        # (Tenant.has_invoicing_provider's own rule) is a legitimate degraded
        # state, not a config error - resolve to None, same as "not selected".
        if (
            capability_name == "invoicing_provider"
            and not getattr(tenant, "has_invoicing_provider", True)
        ):
            return None

        implementation = registry.get(implementation_name)
        if implementation is None:
            raise ValueError(
                f"Tenant {getattr(tenant, 'account_name', '?')!r} references unknown "
                f"{capability_name!r} implementation {implementation_name!r} "
                f"(known: {sorted(registry.keys())})"
            )
        return implementation
