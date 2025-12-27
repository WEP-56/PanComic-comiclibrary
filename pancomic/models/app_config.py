"""Application configuration data model."""

from dataclasses import dataclass, field
from typing import Dict, Any
import os


@dataclass
class AppConfig:
    """Application configuration model.
    
    Contains all application settings including general settings and
    source-specific configurations.
    """
    
    # General settings
    theme: str = "dark"  # "dark", "light", "system"
    language: str = "zh_CN"  # "zh_CN", "en_US"
    auto_check_updates: bool = True
    
    # Download settings
    download_path: str = ""  # Will be set to default if empty
    concurrent_downloads: int = 3
    auto_retry: bool = True
    max_retries: int = 3
    cache_size_mb: int = 500
    
    # Source-specific configs
    jmcomic_config: Dict[str, Any] = field(default_factory=dict)
    picacg_config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate all configuration values.
        
        Raises:
            ValueError: If any configuration value is invalid.
        """
        # Validate theme
        valid_themes = ["dark", "light", "system"]
        if self.theme not in valid_themes:
            raise ValueError(f"theme must be one of {valid_themes}, got '{self.theme}'")
        
        # Validate language
        valid_languages = ["zh_CN", "en_US"]
        if self.language not in valid_languages:
            raise ValueError(f"language must be one of {valid_languages}, got '{self.language}'")
        
        # Validate boolean fields
        if not isinstance(self.auto_check_updates, bool):
            raise ValueError("auto_check_updates must be a boolean")
        if not isinstance(self.auto_retry, bool):
            raise ValueError("auto_retry must be a boolean")
        
        # Validate download_path (if set, must be a valid directory or creatable)
        if self.download_path:
            if not isinstance(self.download_path, str):
                raise ValueError("download_path must be a string")
            # Note: We don't check if path exists here as it might be created later
        
        # Validate concurrent_downloads (must be positive integer, reasonable limit)
        if not isinstance(self.concurrent_downloads, int):
            raise ValueError("concurrent_downloads must be an integer")
        if not (1 <= self.concurrent_downloads <= 10):
            raise ValueError("concurrent_downloads must be between 1 and 10")
        
        # Validate max_retries (must be non-negative integer, reasonable limit)
        if not isinstance(self.max_retries, int):
            raise ValueError("max_retries must be an integer")
        if not (0 <= self.max_retries <= 10):
            raise ValueError("max_retries must be between 0 and 10")
        
        # Validate cache_size_mb (must be positive integer, reasonable limit)
        if not isinstance(self.cache_size_mb, int):
            raise ValueError("cache_size_mb must be an integer")
        if not (10 <= self.cache_size_mb <= 10000):
            raise ValueError("cache_size_mb must be between 10 and 10000")
        
        # Validate source configs are dictionaries
        if not isinstance(self.jmcomic_config, dict):
            raise ValueError("jmcomic_config must be a dictionary")
        if not isinstance(self.picacg_config, dict):
            raise ValueError("picacg_config must be a dictionary")
    
    def validate_download_path(self) -> bool:
        """Validate that the download path exists and is writable.
        
        Returns:
            True if path is valid and writable, False otherwise.
        """
        if not self.download_path:
            return False
        
        # Check if path exists
        if not os.path.exists(self.download_path):
            # Try to create it
            try:
                os.makedirs(self.download_path, exist_ok=True)
                return True
            except (OSError, PermissionError):
                return False
        
        # Check if path is a directory
        if not os.path.isdir(self.download_path):
            return False
        
        # Check if path is writable
        return os.access(self.download_path, os.W_OK)
    
    def get_source_config(self, source: str) -> Dict[str, Any]:
        """Get configuration for a specific comic source.
        
        Args:
            source: Source name ("jmcomic", or "picacg").
            
        Returns:
            Configuration dictionary for the specified source.
            
        Raises:
            ValueError: If source is invalid.
        """
        valid_sources = ["jmcomic", "picacg"]
        if source not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}, got '{source}'")
        
        if source == "jmcomic":
            return self.jmcomic_config
        elif source == "picacg":
            return self.picacg_config
    
    def update_source_config(self, source: str, config: Dict[str, Any]) -> None:
        """Update configuration for a specific comic source.
        
        Args:
            source: Source name ("jmcomic", or "picacg").
            config: New configuration dictionary.
            
        Raises:
            ValueError: If source is invalid or config is not a dictionary.
        """
        valid_sources = ["jmcomic", "picacg"]
        if source not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}, got '{source}'")
        
        if not isinstance(config, dict):
            raise ValueError("config must be a dictionary")
        
        if source == "jmcomic":
            self.jmcomic_config = config
        elif source == "picacg":
            self.picacg_config = config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert AppConfig to dictionary for serialization.
        
        Returns:
            Dictionary representation of the AppConfig.
        """
        return {
            'theme': self.theme,
            'language': self.language,
            'auto_check_updates': self.auto_check_updates,
            'download_path': self.download_path,
            'concurrent_downloads': self.concurrent_downloads,
            'auto_retry': self.auto_retry,
            'max_retries': self.max_retries,
            'cache_size_mb': self.cache_size_mb,
            'jmcomic_config': self.jmcomic_config.copy(),
            'picacg_config': self.picacg_config.copy(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create AppConfig from dictionary.
        
        Args:
            data: Dictionary containing configuration data.
            
        Returns:
            AppConfig instance created from the dictionary.
        """
        return cls(
            theme=data.get('theme', 'dark'),
            language=data.get('language', 'zh_CN'),
            auto_check_updates=data.get('auto_check_updates', True),
            download_path=data.get('download_path', ''),
            concurrent_downloads=data.get('concurrent_downloads', 3),
            auto_retry=data.get('auto_retry', True),
            max_retries=data.get('max_retries', 3),
            cache_size_mb=data.get('cache_size_mb', 500),
            jmcomic_config=data.get('jmcomic_config', {}),
            picacg_config=data.get('picacg_config', {}),
        )
    
    @classmethod
    def get_default(cls) -> 'AppConfig':
        """Create AppConfig with default values.
        
        Returns:
            AppConfig instance with default configuration.
        """
        return cls(
            theme='dark',
            language='zh_CN',
            auto_check_updates=True,
            download_path='',
            concurrent_downloads=3,
            auto_retry=True,
            max_retries=3,
            cache_size_mb=500,
            jmcomic_config={
                'auto_login': False,
                'username': '',
                'password': '',
                'domain': 'jmcomic.com',
                'proxy_enabled': False,
                'proxy_address': '',
                'proxy_port': 0,
            },
            picacg_config={
                'auto_login': False,
                'email': '',
                'password': '',
                'api_endpoint': 'https://picaapi.picacomic.com',
                'image_quality': 'original',
                'proxy_enabled': False,
                'proxy_address': '',
                'proxy_port': 0,
            },
        )
