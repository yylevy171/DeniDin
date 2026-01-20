"""
BotConfiguration model for managing chatbot configuration.
Supports loading from JSON/YAML files and validation.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class BotConfiguration:
    """Configuration model for the DeniDin chatbot."""
    
    green_api_instance_id: str
    green_api_token: str
    openai_api_key: str
    ai_model: str = 'gpt-4o-mini'
    system_message: str = 'You are a helpful assistant.'
    max_tokens: int = 1000
    temperature: float = 0.7
    log_level: str = 'INFO'
    poll_interval_seconds: int = 5
    max_retries: int = 3
    
    # Data storage configuration
    data_root: str = 'data'  # Root directory for all data storage (sessions, memory, etc.)
    
    # Memory system configuration (Feature 002+007)
    godfather_phone: Optional[str] = None
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    memory: Dict = field(default_factory=dict)
    constitution_config: Dict = field(default_factory=dict)
    user_roles: Dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, file_path: str) -> 'BotConfiguration':
        """
        Load configuration from a JSON or YAML file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            BotConfiguration instance
            
        Raises:
            ValueError: If required fields are missing
            FileNotFoundError: If config file doesn't exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        # Determine file type by extension
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            import yaml
            with open(file_path, 'r') as f:
                config_data = yaml.safe_load(f)
        else:
            # Default to JSON
            with open(file_path, 'r') as f:
                config_data = json.load(f)
        
        # Validate required fields (critical API credentials)
        required_fields = [
            'green_api_instance_id',
            'green_api_token',
            'openai_api_key'
        ]
        
        missing_fields = [field for field in required_fields if field not in config_data or not config_data.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
        
        # Set defaults for optional fields
        defaults = {
            'ai_model': 'gpt-4o-mini',
            'system_message': 'You are a helpful assistant.',
            'max_tokens': 1000,
            'temperature': 0.7,
            'log_level': 'INFO',
            'poll_interval_seconds': 5,
            'max_retries': 3,
            'data_root': 'data',
            'godfather_phone': None,
            'feature_flags': {},
            'memory': {},
            'constitution_config': {},
            'user_roles': {}
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
                    'storage_dir': f'{data_root}/sessions',
                    'max_tokens_by_role': {'client': 4000, 'godfather': 100000},
                    'session_timeout_hours': 24
                },
                'longterm': {
                    'enabled': True,
                    'storage_dir': f'{data_root}/memory',
                    'collection_name': 'godfather_memory',
                    'embedding_model': 'text-embedding-3-small',
                    'top_k_results': 5,
                    'min_similarity': 0.7
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
        
        return cls(**config_data)

    def validate(self) -> None:
        """
        Validate configuration values are within acceptable ranges.
        
        Raises:
            ValueError: If any configuration value is invalid
        """
        # Validate temperature range (0.0 - 1.0)
        if not (0.0 <= self.temperature <= 1.0):
            raise ValueError(f"temperature must be between 0.0 and 1.0, got {self.temperature}")
        
        # Validate max_tokens is positive
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")
        
        # Validate poll_interval_seconds is positive
        if self.poll_interval_seconds < 1:
            raise ValueError(f"poll_interval_seconds must be >= 1, got {self.poll_interval_seconds}")
        
        # Validate log_level is INFO or DEBUG
        if self.log_level not in ['INFO', 'DEBUG']:
            raise ValueError(f"log_level must be 'INFO' or 'DEBUG', got '{self.log_level}'")
        
        # Validate data_root is not empty
        if not self.data_root or not self.data_root.strip():
            raise ValueError("data_root must not be empty")
