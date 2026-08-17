"""TenantAIHandlerFactory: builds one full AIHandler stack per tenant.

See specs/in-progress/055-multiple-clients-godfathers/research.md §8 and
contracts/tenant-scoped-data-managers.md for the design this implements: `AIHandler`
(and everything it constructs internally — `UserManager`, `SessionManager`,
`MemoryManager`, `LedgerEventManager`) is already constructor-scoped, so multi-tenancy
is achieved by constructing one full, independent stack per tenant, sourcing values
from that tenant's own `Tenant` object into a tenant-scoped `AppConfiguration` view —
not by threading `tenant_id` through method calls. `AIHandler` itself is not modified.

REQ-PARITY-001: this factory is purely additive. `denidin.py`'s existing single-tenant
`initialize_app` path, and anything else that constructs `AIHandler` directly
(including `tests/billed/`/`tests/expensive/`), is completely unaffected.

Multi-godfather (Phase 4/US2, tasks.md T015): every configured godfather is passed
through via `user_roles["godfather_phones"]`, resolved by `UserManager`'s additive
`godfather_phones` parameter (T015b). The first godfather is ALSO still set on the
original singular `godfather_phone` field (harmless duplication - `UserManager`
checks both independently) purely so nothing else reading `config.godfather_phone`
directly sees an unset value for a tenant that has at least one godfather.
"""

from dataclasses import replace

from openai import OpenAI

from src.capabilities.registry import CapabilityRegistry
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.tenant import Tenant


class TenantAIHandlerFactory:
    """Builds one fully independent AIHandler stack per tenant."""

    @staticmethod
    def build(tenant: Tenant, base_config: AppConfiguration) -> AIHandler:
        """Construct one AIHandler for `tenant`, sourcing tenant-specific values from
        it and carrying over environment-wide values (e.g. ai_embedding_model,
        feature_flags) from `base_config` unchanged."""
        tenant_config = TenantAIHandlerFactory._build_tenant_config(tenant, base_config)
        ai_client = OpenAI(api_key=tenant.openai["api_key"], timeout=30.0)
        return AIHandler(ai_client, tenant_config)

    @staticmethod
    def _build_tenant_config(tenant: Tenant, base_config: AppConfiguration) -> AppConfiguration:
        """A tenant-scoped AppConfiguration view: overrides credentials/data paths/RBAC
        lists from `tenant`, keeps everything else from `base_config` as-is."""
        memory = dict(base_config.memory) if base_config.memory else {}
        memory["session"] = dict(memory.get("session", {}))
        memory["session"]["storage_dir"] = str(tenant.data_root / "sessions")
        memory["longterm"] = dict(memory.get("longterm", {}))
        memory["longterm"]["storage_dir"] = str(tenant.data_root / "memory")

        first_godfather = tenant.godfathers[0] if tenant.godfathers else None

        # Feature 055 Phase 6 (REQ-CAP-002/005/006, contracts/invoicing-capability.md):
        # the invoicing provider is a DI-resolved capability, selected per tenant.
        # CapabilityRegistry.resolve returns None for a tenant with no working
        # invoicing provider (REQ-CAP-005) - in that case any morning_auth_token
        # inherited from base_config.mcp is explicitly dropped, never silently
        # carried through. This closes a real cross-tenant credential-leak gap: before
        # this wiring, AIHandler._build_morning_mcp_tools read morning_auth_token
        # straight from base_config.mcp, so every tenant sharing one process would
        # have received the SAME token if the environment config still carried the
        # old, pre-multi-tenancy shared value.
        mcp = dict(base_config.mcp) if base_config.mcp else {}
        invoicing_provider = CapabilityRegistry.resolve(tenant, "invoicing_provider")
        if invoicing_provider is not None:
            mcp.update(invoicing_provider.mcp_config_overrides(tenant))
        else:
            mcp.pop("morning_auth_token", None)

        return replace(
            base_config,
            green_api_instance_id=tenant.green_api["instance_id"],
            green_api_token=tenant.green_api["api_token"],
            ai_api_key=tenant.openai["api_key"],
            data_root=str(tenant.data_root),
            godfather_phone=first_godfather,
            user_roles={
                "admin_phones": list(tenant.admins),
                "blocked_phones": [],
                "godfather_phones": list(tenant.godfathers),
            },
            memory=memory,
            mcp=mcp,
        )
