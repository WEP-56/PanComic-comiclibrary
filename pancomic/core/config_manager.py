"""Configuration management for PanComic application."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy


class ConfigManager:
    """Manages application configuration with validation and persistence."""
    
    def __init__(self, config_path: str):
        """
        Initialize ConfigManager.
        
        Args:
            config_path: Path to the configuration JSON file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._default_config: Dict[str, Any] = {}
        
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Returns:
            Dictionary containing the configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Store a copy as default config for validation
            if not self._default_config:
                self._default_config = deepcopy(self.config)
            
            # Validate the loaded configuration
            self._validate_config()
            
            return self.config
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in configuration file: {e.msg}",
                e.doc,
                e.pos
            )
    
    def save_config(self) -> None:
        """
        Save configuration to JSON file.
        
        Raises:
            OSError: If unable to write to config file
        """
        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Validate before saving
        self._validate_config()
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise OSError(f"Failed to save configuration: {e}")
    
    def get_source_config(self, source: str) -> Dict[str, Any]:
        """
        Get configuration for a specific comic source.
        
        Args:
            source: Source name ('jmcomic', or 'picacg')
            
        Returns:
            Dictionary containing source-specific configuration
            
        Raises:
            KeyError: If source is not found in configuration
        """
        if source not in self.config:
            raise KeyError(f"Source '{source}' not found in configuration")
        
        return deepcopy(self.config[source])
    
    def update_source_config(self, source: str, config: Dict[str, Any]) -> None:
        """
        Update configuration for a specific comic source.
        
        Args:
            source: Source name ('jmcomic', or 'picacg')
            config: Dictionary containing updated configuration
            
        Raises:
            KeyError: If source is not found in configuration
            ValueError: If configuration is invalid
        """
        if source not in self.config:
            raise KeyError(f"Source '{source}' not found in configuration")
        
        # Update the configuration
        self.config[source].update(config)
        
        # Save the updated configuration to file
        self.save_config()
        
        # Validate the updated configuration
        self._validate_source_config(source)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'general.theme')
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'general.theme')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def _validate_config(self) -> None:
        """
        Validate the entire configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate required top-level sections
        required_sections = ['general', 'download', 'cache', 'jmcomic', 'picacg']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate general settings
        self._validate_general_config()
        
        # Validate download settings
        self._validate_download_config()
        
        # Validate cache settings
        self._validate_cache_config()
        
        # Validate source configurations
        for source in ['jmcomic', 'picacg']:
            self._validate_source_config(source)
    
    def _validate_general_config(self) -> None:
        """Validate general configuration section."""
        general = self.config.get('general', {})
        
        # Validate theme
        valid_themes = ['dark', 'light', 'system']
        if general.get('theme') not in valid_themes:
            raise ValueError(f"Invalid theme. Must be one of: {valid_themes}")
        
        # Validate window size
        window_size = general.get('window_size', {})
        if window_size:
            width = window_size.get('width', 0)
            height = window_size.get('height', 0)
            if width < 1024 or height < 768:
                raise ValueError("Window size must be at least 1024x768")
    
    def _validate_download_config(self) -> None:
        """Validate download configuration section."""
        download = self.config.get('download', {})
        
        # Validate concurrent downloads
        concurrent = download.get('concurrent_downloads', 0)
        if not isinstance(concurrent, int) or concurrent < 1 or concurrent > 10:
            raise ValueError("concurrent_downloads must be between 1 and 10")
        
        # Validate max retries
        max_retries = download.get('max_retries', 0)
        if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 10:
            raise ValueError("max_retries must be between 0 and 10")
        
        # Validate download path if specified
        download_path = download.get('download_path', '')
        if download_path:
            path = Path(download_path)
            # Only validate if path is not empty and is absolute
            if path.is_absolute() and not path.parent.exists():
                raise ValueError(f"Download path parent directory does not exist: {download_path}")
    
    def _validate_cache_config(self) -> None:
        """Validate cache configuration section."""
        cache = self.config.get('cache', {})
        
        # Validate cache size
        cache_size = cache.get('cache_size_mb', 0)
        if not isinstance(cache_size, (int, float)) or cache_size < 10 or cache_size > 10000:
            raise ValueError("cache_size_mb must be between 10 and 10000")
    
    def _validate_source_config(self, source: str) -> None:
        """
        Validate source-specific configuration.
        
        Args:
            source: Source name to validate
            
        Raises:
            ValueError: If source configuration is invalid
        """
        source_config = self.config.get(source, {})
        
        # Validate proxy configuration if present
        proxy = source_config.get('proxy', {})
        if proxy.get('enabled'):
            address = proxy.get('address', '')
            port = proxy.get('port', 0)
            
            if not address:
                raise ValueError(f"{source}: Proxy address is required when proxy is enabled")
            
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError(f"{source}: Proxy port must be between 1 and 65535")
        
        # Validate PicACG-specific settings
        if source == 'picacg':
            endpoint = source_config.get('api_endpoint', '')
            available_endpoints = source_config.get('available_endpoints', [])
            
            if endpoint and endpoint not in available_endpoints:
                raise ValueError(f"PicACG endpoint '{endpoint}' not in available endpoints")
        
        # Validate image quality
        valid_qualities = ['low', 'medium', 'high', 'original']
        quality = source_config.get('image_quality', '')
        if quality and quality not in valid_qualities:
            raise ValueError(f"{source}: Invalid image quality. Must be one of: {valid_qualities}")
