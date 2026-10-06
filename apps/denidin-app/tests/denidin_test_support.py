"""Building DeniDin objects in tests (Feature 063, REQ-063-08).

Every DeniDin manager - and the AI implementation - takes the DeniDin object as its
only constructor argument and reads its settings off DeniDin's config. Tests build a
real `denidin.DeniDin` holding just what they exercise (`make_denidin`), or, for a
single manager, use the `make_*` helpers below: each builds that manager on its own
DeniDin, configured so the manager lands exactly where the test says.
"""
import copy
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.managers.doc_template_engine import DocTemplateEngine
from src.managers.ledger_event_manager import LedgerEventManager
from src.managers.memory_manager import MemoryManager
from src.managers.reminder_manager import ReminderManager
from src.managers.roll_marker_store import RollMarkerStore
from src.managers.session_manager import SessionManager
from src.managers.telemetry_manager import TelemetryManager
from src.managers.user_manager import UserManager
from src.models.config import AppConfiguration

PathLike = Union[str, Path]


def make_config(**fields: Any) -> AppConfiguration:
    """An AppConfiguration with placeholder credentials; `fields` set any field."""
    values: Dict[str, Any] = {
        "green_api_instance_id": "test-instance",
        "green_api_token": "test-token",
        "ai_api_key": "test-key",
    }
    values.update(fields)
    return AppConfiguration(**values)


def make_denidin(config: Optional[AppConfiguration] = None, *, ai_client: Any = None,
                 **objects: Any) -> Any:
    """A real DeniDin on `config` (default: make_config() on a throwaway data root),
    holding `objects` (session_manager=..., user_manager=..., ...) - every other
    object is None."""
    import denidin  # pylint: disable=import-outside-toplevel - loads the app's config at import
    if config is None:
        config = make_config(data_root=tempfile.mkdtemp(prefix="denidin_test_"))
    app = denidin.DeniDin(config, ai_client=ai_client)
    for name, value in objects.items():
        setattr(app, name, value)
    return app


def with_storage(config: AppConfiguration, data_root: PathLike, *,
                 longterm_enabled: Optional[bool] = None) -> AppConfiguration:
    """`config` with everything stored under `data_root` (sessions/, memory/, events/,
    ...); the rest of its memory settings kept. `longterm_enabled` overrides
    memory.longterm.enabled."""
    import dataclasses  # pylint: disable=import-outside-toplevel
    memory = copy.deepcopy(config.memory or {})
    memory.setdefault("session", {})["storage_dir"] = str(Path(data_root) / "sessions")
    memory.setdefault("longterm", {})["storage_dir"] = str(Path(data_root) / "memory")
    if longterm_enabled is not None:
        memory["longterm"]["enabled"] = longterm_enabled
    return dataclasses.replace(config, data_root=str(data_root), memory=memory)


def _default_mock_config_fields(config: Any) -> None:
    """Many tests hand a Mock(spec=AppConfiguration) config; a spec'd Mock lacks the
    dataclass fields built by default_factory (feature_flags, ...), so give the ones
    DeniDin reads at construction their real defaults when the test didn't set them."""
    from unittest.mock import Mock  # pylint: disable=import-outside-toplevel
    if not isinstance(config, Mock):
        return
    for name, value in AppConfiguration.__dataclass_fields__.items():
        if name in vars(config):
            continue
        if not callable(value.default_factory):  # type: ignore[misc]
            continue
        setattr(config, name, value.default_factory())  # type: ignore[misc]


def _keep_storage_out_of_real_data(config: Any) -> None:
    """build_denidin_objects builds every manager, including the ones a test never set
    a location for: TelemetryManager under {data_root}/telemetry, MemoryManager under
    memory.longterm.storage_dir (default data/memory, not relative to data_root). Left
    as is, a test config with the default data_root ("data") or no longterm storage_dir
    writes into the app's real data/ folder - so point both at a throwaway dir."""
    if str(config.data_root) in ("data", "data/"):
        config.data_root = tempfile.mkdtemp(prefix="denidin_test_")
    memory = config.memory if isinstance(config.memory, dict) else {}
    longterm = memory.get("longterm")
    if not isinstance(longterm, dict):
        longterm = {}
    if "storage_dir" not in longterm:
        memory = {**memory, "longterm": {**longterm, "storage_dir": str(Path(config.data_root) / "memory")}}
        config.memory = memory


def make_app_denidin(ai_client: Any, config: AppConfiguration, **objects: Any) -> Any:
    """A DeniDin with every object initialize_app builds except the AI implementation
    (denidin.build_denidin_objects), on `config` as given; `objects` then replace any
    of them."""
    import denidin  # pylint: disable=import-outside-toplevel
    _default_mock_config_fields(config)
    _keep_storage_out_of_real_data(config)
    app = denidin.DeniDin(config, ai_client=ai_client)
    denidin.build_denidin_objects(app)
    for name, value in objects.items():
        setattr(app, name, value)
    return app


def _data_root_for(storage_dir: PathLike, dir_name: str) -> str:
    """The data_root a manager storing under {data_root}/<dir_name> needs to land in
    `storage_dir`."""
    path = Path(storage_dir)
    assert path.name == dir_name, f"{path} must be named {dir_name!r} ({{data_root}}/{dir_name})"
    return str(path.parent)


def make_session_manager(storage_dir: Optional[PathLike] = None) -> SessionManager:
    """A SessionManager storing under `storage_dir` (default: a throwaway dir)."""
    storage_dir = storage_dir or tempfile.mkdtemp(prefix="sessions_")
    return SessionManager(make_denidin(make_config(memory={"session": {"storage_dir": str(storage_dir)}})))


def make_user_manager(godfather_phone: Optional[str] = None, admin_phones: Optional[List[str]] = None,
                      blocked_phones: Optional[List[str]] = None) -> UserManager:
    return UserManager(make_denidin(make_config(
        godfather_phone=godfather_phone,
        user_roles={"admin_phones": admin_phones or [], "blocked_phones": blocked_phones or []},
    )))


def make_ledger_event_manager(storage_dir: PathLike, session_manager: Any = None) -> LedgerEventManager:
    """A LedgerEventManager storing in `storage_dir` (named "events"), back-linking
    through `session_manager` when given."""
    app = make_denidin(make_config(data_root=_data_root_for(storage_dir, "events")),
                       session_manager=session_manager)
    return LedgerEventManager(app)


def make_reminder_manager(storage_dir: PathLike, max_active_reminders: int = 20) -> ReminderManager:
    """A ReminderManager storing in `storage_dir` (named "reminders")."""
    return ReminderManager(make_denidin(make_config(
        data_root=_data_root_for(storage_dir, "reminders"),
        reminders={"max_active_reminders": max_active_reminders},
    )))


def make_roll_marker_store(storage_dir: PathLike, stale_claim_minutes: int = 120) -> RollMarkerStore:
    """A RollMarkerStore storing in `storage_dir` (named "memory_rolls")."""
    return RollMarkerStore(make_denidin(make_config(
        data_root=_data_root_for(storage_dir, "memory_rolls"),
        memory={"roll": {"stale_claim_minutes": stale_claim_minutes}},
    )))


def make_memory_manager(storage_dir: PathLike, embedding_model: str = "text-embedding-3-small",
                        ai_client: Any = None) -> MemoryManager:
    """A MemoryManager (ChromaDB) storing in `storage_dir`."""
    return MemoryManager(make_denidin(
        make_config(memory={"longterm": {"storage_dir": str(storage_dir)}}, ai_embedding_model=embedding_model),
        ai_client=ai_client,
    ))


def make_telemetry_manager(data_root: PathLike) -> TelemetryManager:
    """A TelemetryManager storing under {data_root}/telemetry."""
    return TelemetryManager(make_denidin(make_config(data_root=str(data_root))))


def make_doc_template_engine(templates_dir: PathLike, tmp_dir: PathLike) -> DocTemplateEngine:
    """A DocTemplateEngine reading `templates_dir`, generating documents into `tmp_dir`."""
    tmp_dir = Path(tmp_dir)
    return DocTemplateEngine(make_denidin(make_config(
        data_root=str(tmp_dir.parent),
        fee_agreements={"templates_dir": str(templates_dir), "tmp_dir": tmp_dir.name},
    )))
