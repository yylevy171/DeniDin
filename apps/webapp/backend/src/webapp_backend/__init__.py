"""webapp-backend — read-only Ledger Web UI BFF (Feature 068).

Importing this package makes a best-effort attempt to put ``apps/denidin-app/src`` on
``sys.path`` so the reused managers (``LedgerEventManager``/``SessionManager``/
``MediaFileManager``) and shared helpers (``utils.time_utils``) resolve. In a container the
real path comes from ``config.denidin_src_path`` and is inserted by ``server.main()``; this
in-repo fallback is what makes host-side pytest and ``python -m`` work with zero setup.
"""
import sys
from pathlib import Path

_DENIDIN_APP = Path(__file__).resolve().parents[4] / "denidin-app"
# Both are needed: `apps/denidin-app/src` so `managers`/`utils` import as top-level packages,
# and `apps/denidin-app` so those modules' own `from src.utils...` imports resolve too.
for _p in (_DENIDIN_APP / "src", _DENIDIN_APP):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
