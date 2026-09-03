"""
AppConfiguration model for managing application configuration.
Supports loading from JSON/YAML files and validation.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Dict


@dataclass
class AppConfiguration:
    """Configuration model for the DeniDin application."""

    green_api_instance_id: str
    green_api_token: str
    ai_api_key: str
    # Which environment this container/process IS (not a switch - declares
    # identity). Read by watchdog.py against shared/active_env.json to
    # detect a stale/mismatched container (2026-07-21 incident: a container
    # for one environment was silently reachable while the other was
    # supposed to be exclusively active). 'dev', 'prod', or 'test'.
    environment: Optional[str] = None
    ai_model: str = 'gpt-5.6-luna'
    # Vision model for image/document processing - not a mini/lightweight variant
    # (Feature 024: gpt-4o-mini silently declined to call the ledger-event tool
    # alongside extraction).
    ai_vision_model: str = 'gpt-5.6-luna'
    ai_embedding_model: str = 'text-embedding-3-large'  # Embedding model for long-term memory (ChromaDB)
    ai_reply_max_tokens: int = 1000
    # Retries-after-the-initial-attempt for every OpenAI Responses API call
    # (2026-08-19 fix - this field was declared in config.test.json/
    # config.example.json for a long time but never actually reached this
    # dataclass, so it did nothing; the real retry count was silently the
    # OpenAI SDK's own hardcoded default of 2, doubled up with this app's own
    # tenacity retry decorators wrapping the SAME calls - up to 6 real HTTP
    # attempts for one logical call, several of which could each sleep a
    # real server-suggested Retry-After delay, occasionally summing to 100+
    # seconds for what looked like it should take ~5s). Passed straight into
    # the OpenAI() client constructor's own max_retries= (denidin.py) - the
    # SDK's own retry/backoff/Retry-After-honoring implementation is now the
    # SINGLE retry mechanism for every OpenAI call in this app, replacing the
    # ad-hoc per-method tenacity decorators that used to double up with it
    # (and, for two follow-up methods, weren't present at all).
    max_retries: int = 1
    log_level: str = 'INFO'

    # Data storage configuration
    data_root: str = 'data'  # Root directory for all data storage (sessions, memory, etc.)

    # Memory system configuration (Feature 002+007)
    godfather_phone: Optional[str] = None
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    memory: Dict = field(default_factory=dict)
    constitution_config: Dict = field(default_factory=dict)
    user_roles: Dict = field(default_factory=dict)

    # Morning MCP integration (Feature 018)
    mcp: Dict = field(default_factory=dict)

    # Reminders (Feature 054) - no feature flag, RBAC (GODFATHER/ADMIN) is the only gate
    reminders: Dict = field(default_factory=dict)

    # Accounting document reconciliation (Feature 025) - minutes between background
    # polls of Morning for documents created there directly. 0 = inactive (the
    # scheduler never starts at all) - an environment that hasn't set this key yet
    # must never accidentally start polling. Not a config.feature_flags entry (the
    # record-shape side of this feature is gated by CURRENT_SCHEMA_VERSION instead)
    # - this field only controls whether the background poller runs.
    accounting_ledger_update_freq: int = 0

    # Log retention (Feature 070, US5). Top-level (not under `memory`) - this is an
    # operational concern, not part of the memory model. `rotation_when` feeds
    # logging.handlers.TimedRotatingFileHandler(when=...); `backup_count` 0 = keep
    # every rotated (gzipped) segment forever. No env vars.
    logging: Dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: str) -> 'AppConfiguration':
        """
        Load configuration from a JSON or YAML file.

        Args:
            file_path: Path to the configuration file

        Returns:
            AppConfiguration instance

        Raises:
            ValueError: If required fields are missing
            FileNotFoundError: If config file doesn't exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file not found: {file_path}")

        # Determine file type by extension
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            import yaml
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        else:
            # Default to JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

        # Validate required fields (critical API credentials)
        required_fields = [
            'green_api_instance_id',
            'green_api_token',
            'ai_api_key'
        ]

        missing_fields = [field for field in required_fields if field not in config_data or not config_data.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        # Set defaults for optional fields
        defaults: Dict[str, Any] = {
            'environment': None,
            'ai_model': 'gpt-5.6-luna',
            'ai_vision_model': 'gpt-5.6-luna',
            'ai_embedding_model': 'text-embedding-3-large',
            'ai_reply_max_tokens': 1000,
            'max_retries': 1,
            'log_level': 'INFO',
            'data_root': 'data',
            'godfather_phone': None,
            'feature_flags': {},
            'memory': {},
            'constitution_config': {},
            'user_roles': {},
            'mcp': {},
            'reminders': {},
            'accounting_ledger_update_freq': 0,
            'logging': {}
        }

        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in config_data:
                config_data[key] = default_value

        # Set memory sub-field defaults if memory key exists
        if 'memory' in config_data and config_data['memory']:
            data_root = config_data.get('data_root', 'data')
            memory_defaults = {
                'session': {
                    'storage_dir': 'sessions',  # Relative to data_root
                    'max_tokens_by_role': {'client': 4000, 'godfather': 100000},
                    # session_timeout_hours is retired (Feature 070 - no 24h idle
                    # expiry). Kept in the defaults so an old config file that
                    # still carries it loads without complaint; nothing reads it.
                    'session_timeout_hours': 24,
                    # Feature 070: rolling verbatim window length in Israel-local
                    # calendar days (REQ-MEM-008).
                    'window_days': 14
                },
                'longterm': {
                    'enabled': True,
                    'storage_dir': 'memory',  # Relative to data_root
                    'collection_name': 'godfather_memory',
                    'top_k_results': 5,
                    'min_similarity': 0.7,
                    # Feature 070: top_k for the single per-turn conversational
                    # recall call, which now also surfaces daily summaries
                    # (REQ-MEM-047, contracts/ai-handler-recall.md). The
                    # MemoryManager.recall parameter default stays 5.
                    'daily_summary_top_k': 10
                },
                # Feature 070: nightly daily-summary roll (US2).
                'roll': {
                    'hour': 2,                     # CronTrigger(hour=...), Israel local
                    'catchup_lookback_days': 21,   # startup catch-up sweep bound (REQ-MEM-028)
                    'stale_claim_minutes': 120     # a 'claimed' roll marker older than this is re-takeable
                }
            }

            for section, section_defaults in memory_defaults.items():
                if section not in config_data['memory']:
                    config_data['memory'][section] = section_defaults
                else:
                    # Merge section-level defaults
                    for key, value in section_defaults.items():
                        if key not in config_data['memory'][section]:
                            config_data['memory'][section][key] = value

            # Feature 070: top-level memory key (not a section) - archived-message
            # retention. 0 = retain forever by design; no pruner is built
            # (REQ-MEM-034).
            if 'archive_retention_days' not in config_data['memory']:
                config_data['memory']['archive_retention_days'] = 0

            # Combine data_root with storage_dir for each section
            for section in ['session', 'longterm']:
                if section in config_data['memory'] and 'storage_dir' in config_data['memory'][section]:
                    storage_dir = config_data['memory'][section]['storage_dir']
                    
                    # Skip absolute paths (start with / or drive letter on Windows)
                    if storage_dir.startswith('/') or (len(storage_dir) > 1 and storage_dir[1] == ':'):
                        continue
                    
                    # Backward compatibility: strip data_root prefix if present
                    # Old configs have "data/sessions", new configs have "sessions"
                    if storage_dir.startswith(f'{data_root}/'):
                        storage_dir = storage_dir[len(data_root)+1:]  # Strip "data/" prefix
                    
                    # Combine data_root with relative storage_dir
                    config_data['memory'][section]['storage_dir'] = f'{data_root}/{storage_dir}'

        # Set mcp sub-field defaults (Feature 018: Morning MCP integration)
        if 'mcp' in config_data and config_data['mcp']:
            mcp_defaults = {
                'morning_auth_token': '',
                'morning_status_file': 'data/morning_mcp_status.json',
                'morning_server_label': 'morning-invoices',
                'url_max_age_seconds': 0
            }
            for key, value in mcp_defaults.items():
                if key not in config_data['mcp']:
                    config_data['mcp'][key] = value

        # Set reminders sub-field defaults (Feature 054)
        if 'reminders' in config_data and config_data['reminders']:
            reminders_defaults = {
                'max_active_reminders': 20
            }
            for key, value in reminders_defaults.items():
                if key not in config_data['reminders']:
                    config_data['reminders'][key] = value

        # Set logging sub-field defaults (Feature 070, US5). Always applied - a
        # bare/missing `logging` block still gets the safe retention defaults.
        logging_defaults = {
            'rotation_when': 'midnight',  # TimedRotatingFileHandler(when=...)
            'backup_count': 0             # 0 = keep every rotated segment
        }
        config_data.setdefault('logging', {})
        for key, value in logging_defaults.items():
            if key not in config_data['logging']:
                config_data['logging'][key] = value

        # Filter out unknown keys (backward compatibility for removed config fields)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_config = {k: v for k, v in config_data.items() if k in valid_fields}

        return cls(**filtered_config)

    def validate(self) -> None:
        """
        Validate configuration values are within acceptable ranges.

        Raises:
            ValueError: If any configuration value is invalid
        """
        # Validate ai_reply_max_tokens is positive
        if self.ai_reply_max_tokens < 1:
            raise ValueError(f"ai_reply_max_tokens must be >= 1, got {self.ai_reply_max_tokens}")

        # Validate max_retries is a non-negative integer (0 is valid - no retries at all)
        if not isinstance(self.max_retries, int) or isinstance(self.max_retries, bool) or self.max_retries < 0:
            raise ValueError(f"max_retries must be a non-negative integer, got {self.max_retries!r}")

        # Validate log_level is INFO or DEBUG
        if self.log_level not in ['INFO', 'DEBUG']:
            raise ValueError(f"log_level must be 'INFO' or 'DEBUG', got '{self.log_level}'")

        # Validate data_root is not empty
        if not self.data_root or not self.data_root.strip():
            raise ValueError("data_root must not be empty")

        # Validate model fields are not empty
        for field_name in ('ai_model', 'ai_vision_model', 'ai_embedding_model'):
            value = getattr(self, field_name)
            if not value or not value.strip():
                raise ValueError(f"{field_name} must not be empty")

        # Validate mcp.url_max_age_seconds is non-negative, if configured
        if self.mcp:
            max_age = self.mcp.get('url_max_age_seconds', 0)
            if not isinstance(max_age, (int, float)) or max_age < 0:
                raise ValueError(f"mcp.url_max_age_seconds must be a non-negative number, got {max_age!r}")

        # Validate reminders.max_active_reminders is a positive integer, if configured
        if self.reminders:
            max_active = self.reminders.get('max_active_reminders', 20)
            if not isinstance(max_active, int) or isinstance(max_active, bool) or max_active < 1:
                raise ValueError(
                    f"reminders.max_active_reminders must be a positive integer, got {max_active!r}"
                )

        # Validate Feature 070 memory tunables, if a memory block is configured
        if self.memory:
            session_cfg = self.memory.get('session', {})
            window_days = session_cfg.get('window_days', 14)
            if not isinstance(window_days, int) or isinstance(window_days, bool) or window_days < 1:
                raise ValueError(f"memory.session.window_days must be a positive integer, got {window_days!r}")

            longterm_cfg = self.memory.get('longterm', {})
            ds_top_k = longterm_cfg.get('daily_summary_top_k', 10)
            if not isinstance(ds_top_k, int) or isinstance(ds_top_k, bool) or ds_top_k < 1:
                raise ValueError(
                    f"memory.longterm.daily_summary_top_k must be a positive integer, got {ds_top_k!r}"
                )

            retention = self.memory.get('archive_retention_days', 0)
            if not isinstance(retention, int) or isinstance(retention, bool) or retention < 0:
                raise ValueError(
                    f"memory.archive_retention_days must be a non-negative integer, got {retention!r}"
                )

            roll_cfg = self.memory.get('roll', {})
            for key, minimum in (('hour', 0), ('catchup_lookback_days', 1), ('stale_claim_minutes', 1)):
                val = roll_cfg.get(key, {'hour': 2, 'catchup_lookback_days': 21, 'stale_claim_minutes': 120}[key])
                if not isinstance(val, int) or isinstance(val, bool) or val < minimum:
                    raise ValueError(f"memory.roll.{key} must be an integer >= {minimum}, got {val!r}")
            if roll_cfg.get('hour', 2) > 23:
                raise ValueError(f"memory.roll.hour must be 0-23, got {roll_cfg.get('hour')!r}")

        # Validate logging tunables (Feature 070, US5)
        if self.logging:
            rotation_when = self.logging.get('rotation_when', 'midnight')
            valid_when = {'midnight', 'S', 'M', 'H', 'D', 'W0', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6'}
            if rotation_when not in valid_when:
                raise ValueError(
                    f"logging.rotation_when must be one of {sorted(valid_when)}, got {rotation_when!r}"
                )
            backup_count = self.logging.get('backup_count', 0)
            if not isinstance(backup_count, int) or isinstance(backup_count, bool) or backup_count < 0:
                raise ValueError(f"logging.backup_count must be a non-negative integer, got {backup_count!r}")
