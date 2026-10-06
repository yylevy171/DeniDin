"""Building denidin-app managers in the backfill tests (Feature 063, REQ-063-08).

Every DeniDin manager takes the DeniDin object as its only constructor argument and
reads its settings off DeniDin's config; these tools build their own minimal stand-in
(backfill_denidin.BackfillDeniDin). Each helper builds one manager on its own
BackfillDeniDin, configured so the manager lands exactly where the test says.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Union

from _denidin_loader import MemoryManager, RollMarkerStore, SessionManager
from backfill_denidin import BackfillConfig, BackfillDeniDin, backfill_config

PathLike = Union[str, Path]


def make_session_manager(storage_dir: PathLike) -> SessionManager:
    """A SessionManager storing under `storage_dir`."""
    storage_dir = Path(storage_dir)
    return SessionManager(BackfillDeniDin(BackfillConfig(
        data_root=str(storage_dir.parent),
        memory={"session": {"storage_dir": str(storage_dir)}},
    )))


def make_roll_marker_store(storage_dir: PathLike) -> RollMarkerStore:
    """A RollMarkerStore storing in `storage_dir` (named "memory_rolls" -
    {data_root}/memory_rolls)."""
    storage_dir = Path(storage_dir)
    assert storage_dir.name == "memory_rolls", f"{storage_dir} must be named 'memory_rolls'"
    return RollMarkerStore(BackfillDeniDin(BackfillConfig(data_root=str(storage_dir.parent), memory={})))


def make_memory_manager(storage_dir: PathLike, embedding_model: str, ai_client: Any) -> MemoryManager:
    """A MemoryManager (ChromaDB) storing in `storage_dir`."""
    storage_dir = Path(storage_dir)
    return MemoryManager(BackfillDeniDin(
        BackfillConfig(data_root=str(storage_dir.parent),
                       memory={"longterm": {"storage_dir": str(storage_dir)}},
                       ai_embedding_model=embedding_model),
        ai_client=ai_client,
    ))


def make_roll_context(data_root: PathLike, *, memory: Optional[Dict[str, Any]], ai_model: str,
                      ai_embedding_model: str, ai_client: Any) -> BackfillDeniDin:
    """The global context the nightly roll reads, built exactly as
    backfill_daily_summaries.py builds it: session/roll-marker/memory managers under
    `data_root`."""
    context = BackfillDeniDin(
        backfill_config(Path(data_root), memory=memory, ai_model=ai_model,
                        ai_embedding_model=ai_embedding_model),
        ai_client=ai_client,
    )
    context.session_manager = SessionManager(context)
    context.roll_marker_store = RollMarkerStore(context)
    context.memory_manager = MemoryManager(context)
    return context
