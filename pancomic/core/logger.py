"""Logging system for PanComic application."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime


class Logger:
    """Centralized logging system with file rotation and source-specific logging."""
    
    _initialized = False
    _logger: Optional[logging.Logger] = None
    _log_dir: Optional[Path] = None
    
    @classmethod
    def setup(
        cls,
        log_dir: str,
        level: str = 'INFO',
        max_log_files: int = 7,
        log_to_file: bool = True,
        log_to_console: bool = True
    ) -> None:
        """
        Setup logging configuration.
        
        Args:
            log_dir: Directory to store log files
            level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            max_log_files: Maximum number of log files to keep
            log_to_file: Whether to log to file
            log_to_console: Whether to log to console
        """
        if cls._initialized:
            return
        
        cls._log_dir = Path(log_dir)
        cls._log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        cls._logger = logging.getLogger('PanComic')
        cls._logger.setLevel(cls._get_log_level(level))
        
        # Clear any existing handlers
        cls._logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add file handler if enabled
        if log_to_file:
            log_file = cls._log_dir / f'pancomic_{datetime.now().strftime("%Y%m%d")}.log'
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB per file
                backupCount=max_log_files - 1,
                encoding='utf-8'
            )
            file_handler.setLevel(cls._get_log_level(level))
            file_handler.setFormatter(formatter)
            cls._logger.addHandler(file_handler)
        
        # Add console handler if enabled
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(cls._get_log_level(level))
            console_handler.setFormatter(formatter)
            cls._logger.addHandler(console_handler)
        
        cls._initialized = True
        cls.info("Logger initialized successfully")
    
    @classmethod
    def _get_log_level(cls, level: str) -> int:
        """
        Convert string log level to logging constant.
        
        Args:
            level: String log level
            
        Returns:
            Logging level constant
        """
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return levels.get(level.upper(), logging.INFO)
    
    @classmethod
    def _get_logger(cls, source: Optional[str] = None) -> logging.Logger:
        """
        Get logger instance, optionally with source-specific name.
        
        Args:
            source: Optional source name for source-specific logging
            
        Returns:
            Logger instance
        """
        if not cls._initialized:
            # Initialize with defaults if not already initialized
            cls.setup('logs')
        
        if source:
            return logging.getLogger(f'PanComic.{source}')
        return cls._logger
    
    @classmethod
    def debug(cls, message: str, source: Optional[str] = None) -> None:
        """
        Log debug message.
        
        Args:
            message: Message to log
            source: Optional source name (e.g., 'jmcomic', 'picacg')
        """
        logger = cls._get_logger(source)
        logger.debug(message)
    
    @classmethod
    def info(cls, message: str, source: Optional[str] = None) -> None:
        """
        Log info message.
        
        Args:
            message: Message to log
            source: Optional source name (e.g., 'jmcomic', 'picacg')
        """
        logger = cls._get_logger(source)
        logger.info(message)
    
    @classmethod
    def warning(cls, message: str, source: Optional[str] = None) -> None:
        """
        Log warning message.
        
        Args:
            message: Message to log
            source: Optional source name (e.g., 'jmcomic', 'picacg')
        """
        logger = cls._get_logger(source)
        logger.warning(message)
    
    @classmethod
    def error(
        cls,
        message: str,
        source: Optional[str] = None,
        exc_info: bool = False
    ) -> None:
        """
        Log error message.
        
        Args:
            message: Message to log
            source: Optional source name (e.g., 'jmcomic', 'picacg')
            exc_info: Whether to include exception information
        """
        logger = cls._get_logger(source)
        logger.error(message, exc_info=exc_info)
    
    @classmethod
    def critical(
        cls,
        message: str,
        source: Optional[str] = None,
        exc_info: bool = False
    ) -> None:
        """
        Log critical message.
        
        Args:
            message: Message to log
            source: Optional source name (e.g., 'jmcomic', 'picacg')
            exc_info: Whether to include exception information
        """
        logger = cls._get_logger(source)
        logger.critical(message, exc_info=exc_info)
    
    @classmethod
    def exception(cls, message: str, source: Optional[str] = None) -> None:
        """
        Log exception with traceback.
        
        Args:
            message: Message to log
            source: Optional source name (e.g., 'jmcomic', 'picacg')
        """
        logger = cls._get_logger(source)
        logger.exception(message)
    
    @classmethod
    def set_level(cls, level: str, source: Optional[str] = None) -> None:
        """
        Set logging level.
        
        Args:
            level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            source: Optional source name to set level for specific source
        """
        logger = cls._get_logger(source)
        logger.setLevel(cls._get_log_level(level))
    
    @classmethod
    def cleanup_old_logs(cls, days_to_keep: int = 7) -> None:
        """
        Clean up old log files.
        
        Args:
            days_to_keep: Number of days of logs to keep
        """
        if not cls._log_dir:
            return
        
        try:
            current_time = datetime.now()
            for log_file in cls._log_dir.glob('pancomic_*.log*'):
                # Get file modification time
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                age_days = (current_time - file_time).days
                
                if age_days > days_to_keep:
                    log_file.unlink()
                    cls.debug(f"Deleted old log file: {log_file.name}")
        except Exception as e:
            cls.error(f"Failed to cleanup old logs: {e}", exc_info=True)
