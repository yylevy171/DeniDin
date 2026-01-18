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
    ai_model: str
    system_message: str
    max_tokens: int
    temperature: float
    log_level: str
    poll_interval_seconds: int
    max_retries: int
    
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
            memory_defaults = {
                'session': {
                    'storage_dir': 'data/sessions',
                    'max_tokens_by_role': {'client': 4000, 'godfather': 100000},
                    'session_timeout_hours': 24
                },
                'longterm': {
                    'enabled': True,
                    'storage_dir': 'data/memory',
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

    @classmethod
    def from_env(cls) -> 'BotConfiguration':
        """
        Load configuration from environment variables.
        
        Returns:
            BotConfiguration instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        missing_vars = []
        
        # Check for required environment variables
        required_env_vars = {
            'GREEN_API_INSTANCE_ID': 'green_api_instance_id',
            'GREEN_API_TOKEN': 'green_api_token',
            'OPENAI_API_KEY': 'openai_api_key'
        }
        
        for env_var in required_env_vars.keys():
            if not os.getenv(env_var):
                missing_vars.append(env_var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return cls(
            green_api_instance_id=os.getenv('GREEN_API_INSTANCE_ID'),
            green_api_token=os.getenv('GREEN_API_TOKEN'),
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            ai_model=os.getenv('AI_MODEL', 'gpt-4'),
            system_message=os.getenv('SYSTEM_MESSAGE', 'You are a helpful assistant.'),
            max_tokens=int(os.getenv('MAX_TOKENS', '1000')),
            temperature=float(os.getenv('TEMPERATURE', '0.7')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            poll_interval_seconds=int(os.getenv('POLL_INTERVAL_SECONDS', '5')),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )
