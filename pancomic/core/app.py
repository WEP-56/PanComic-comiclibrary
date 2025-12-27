"""Main application class."""

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from pancomic.core.config_manager import ConfigManager
from pancomic.core.logger import Logger
from pancomic.infrastructure.database import Database
from pancomic.infrastructure.image_cache import ImageCache
from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.adapters.jmcomic_adapter import JMComicAdapter
from pancomic.adapters.ehentai_adapter import EHentaiAdapter
from pancomic.adapters.picacg_adapter import PicACGAdapter
from pancomic.ui.main_window import MainWindow


class Application:
    """
    Main application class.
    
    Handles application initialization, lifecycle management, and coordination
    between core components.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Application.
        
        Args:
            config_path: Optional path to configuration file.
                        If not provided, uses default location.
        """
        # Determine project root directory (for portable data storage)
        self.project_root = Path(__file__).parent.parent.parent  # Go up from app.py to project root
        self.data_dir = self.project_root / 'downloads'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # App data dir for logs and cache (can be in user directory)
        self.app_data_dir = self._get_app_data_dir()
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Set config path to downloads folder for portability
        if config_path is None:
            config_path = str(self.data_dir / 'config.json')
        
        self.config_path = config_path
        
        # Core components
        self.qt_app: Optional[QApplication] = None
        self.config_manager: Optional[ConfigManager] = None
        self.database: Optional[Database] = None
        self.image_cache: Optional[ImageCache] = None
        self.download_manager: Optional[DownloadManager] = None
        
        # Adapters
        self.jmcomic_adapter: Optional[JMComicAdapter] = None
        self.ehentai_adapter: Optional[EHentaiAdapter] = None
        self.picacg_adapter: Optional[PicACGAdapter] = None
        
        # Main window
        self.main_window: Optional[MainWindow] = None
    
    def _get_app_data_dir(self) -> Path:
        """
        Get application data directory based on platform.
        
        Returns:
            Path to application data directory
        """
        if sys.platform == 'win32':
            # Windows: %APPDATA%/PanComic/
            app_data = Path.home() / 'AppData' / 'Roaming' / 'PanComic'
        elif sys.platform == 'darwin':
            # macOS: ~/Library/Application Support/PanComic/
            app_data = Path.home() / 'Library' / 'Application Support' / 'PanComic'
        else:
            # Linux: ~/.config/pancomic/
            app_data = Path.home() / '.config' / 'pancomic'
        
        return app_data
    
    def initialize(self) -> bool:
        """
        Initialize all application components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize Qt application
            self.qt_app = QApplication(sys.argv)
            self.qt_app.setApplicationName("PanComic")
            self.qt_app.setOrganizationName("PanComic")
            
            # Set application-wide attributes
            self.qt_app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            self.qt_app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            
            # Initialize logger
            log_dir = self.app_data_dir / 'logs'
            Logger.setup(
                log_dir=str(log_dir),
                level='INFO',
                max_log_files=7,
                log_to_file=True,
                log_to_console=True
            )
            Logger.info("Application starting...")
            
            # Initialize or create config
            self.config_manager = ConfigManager(self.config_path)
            
            if not Path(self.config_path).exists():
                Logger.info("Config file not found, creating default configuration")
                self._create_default_config()
            else:
                Logger.info("Loading configuration")
                self.config_manager.load_config()
            
            # Initialize database
            db_path = self.app_data_dir / 'pancomic.db'
            Logger.info(f"Initializing database at {db_path}")
            self.database = Database(str(db_path))
            self.database.initialize_schema()
            
            # Initialize image cache
            cache_dir = self.app_data_dir / 'cache'
            cache_size_mb = self.config_manager.get('cache.cache_size_mb', 500)
            Logger.info(f"Initializing image cache (size limit: {cache_size_mb} MB)")
            self.image_cache = ImageCache.instance()
            self.image_cache.__init__(str(cache_dir), cache_size_mb)
            
            # Initialize download manager
            concurrent_downloads = self.config_manager.get('download.concurrent_downloads', 3)
            Logger.info(f"Initializing download manager (concurrent: {concurrent_downloads})")
            self.download_manager = DownloadManager(concurrent_downloads)
            
            # Initialize adapters
            Logger.info("Initializing source adapters")
            self._initialize_adapters()
            
            # Create main window
            Logger.info("Creating main window")
            self.main_window = MainWindow(
                config_manager=self.config_manager,
                jmcomic_adapter=self.jmcomic_adapter,
                ehentai_adapter=self.ehentai_adapter,
                picacg_adapter=self.picacg_adapter,
                download_manager=self.download_manager
            )
            
            # Connect main window closing signal
            self.main_window.closing.connect(self._on_application_closing)
            
            Logger.info("Application initialized successfully")
            return True
            
        except Exception as e:
            Logger.error(f"Failed to initialize application: {e}", exc_info=True)
            
            # Show error dialog if Qt app is initialized
            if self.qt_app:
                QMessageBox.critical(
                    None,
                    "初始化失败",
                    f"应用程序初始化失败:\n{str(e)}\n\n请查看日志文件获取详细信息。"
                )
            
            return False
    
    def _create_default_config(self) -> None:
        """Create default configuration file."""
        # 设置默认下载路径为项目根目录的downloads文件夹
        project_root = Path(__file__).parent.parent.parent  # 从app.py向上3级到项目根目录
        default_download_path = project_root / "downloads"
        
        default_config = {
            "general": {
                "theme": "dark",
                "language": "zh_CN",
                "auto_check_updates": True,
                "window_size": {
                    "width": 1400,
                    "height": 900
                }
            },
            "download": {
                "download_path": str(default_download_path),
                "concurrent_downloads": 3,
                "auto_retry": True,
                "max_retries": 3
            },
            "cache": {
                "cache_size_mb": 500
            },
            "jmcomic": {
                "username": "",
                "password": "",
                "auto_login": False,
                "api_endpoint": 2,
                "proxy": {
                    "enabled": False,
                    "address": "",
                    "port": 1080
                }
            },
            "ehentai": {
                "enabled": False,
                "auto_login": False,
                "cookies": "",
                "use_exhentai": False,
                "proxy": {
                    "enabled": False,
                    "address": "",
                    "port": 1080
                }
            },
            "picacg": {
                "email": "",
                "password": "",
                "auto_login": False,
                "endpoint": "https://picaapi.picacomic.com",
                "image_server": "storage.diwodiwo.xyz",
                "api_endpoints": [
                    "https://picaapi.picacomic.com",
                    "https://bika-api.jpacg.cc",
                    "https://188.114.98.153",
                    "https://bika2-api.jpacg.cc",
                    "https://104.21.91.145"
                ],
                "image_servers": [
                    "storage.diwodiwo.xyz",
                    "storage-b.picacomic.com",
                    "s3.picacomic.com",
                    "s2.picacomic.com",
                    "storage1.picacomic.com"
                ],
                "image_quality": "original"
            }
        }
        
        # Set config and save
        self.config_manager.config = default_config
        self.config_manager.save_config()
        
        Logger.info("Created default configuration file")
    
    def _initialize_adapters(self) -> None:
        """Initialize all source adapters."""
        # Get source configurations
        jmcomic_config = self.config_manager.get_source_config('jmcomic')
        ehentai_config = self.config_manager.get_source_config('ehentai')
        picacg_config = self.config_manager.get_source_config('picacg')
        
        # Create adapters
        self.jmcomic_adapter = JMComicAdapter(jmcomic_config)
        self.ehentai_adapter = EHentaiAdapter(ehentai_config)
        self.picacg_adapter = PicACGAdapter(picacg_config)
        
        # Start worker threads
        self.jmcomic_adapter.start_worker_thread()
        self.ehentai_adapter.start_worker_thread()
        self.picacg_adapter.start_worker_thread()
        
        # Initialize adapters
        try:
            self.jmcomic_adapter.initialize()
            Logger.info("JMComic adapter initialized")
        except Exception as e:
            Logger.error(f"Failed to initialize JMComic adapter: {e}")
        
        try:
            self.ehentai_adapter.initialize()
            Logger.info("E-Hentai adapter initialized (hidden)")
        except Exception as e:
            Logger.error(f"Failed to initialize E-Hentai adapter: {e}")
        
        try:
            self.picacg_adapter.initialize()
            Logger.info("PicACG adapter initialized")
        except Exception as e:
            Logger.error(f"Failed to initialize PicACG adapter: {e}")
        
        # Register download functions
        self.download_manager.register_download_function('jmcomic', self.jmcomic_adapter.download_chapter)
        self.download_manager.register_download_function('picacg', self.picacg_adapter.download_chapter)
        # Note: EHentai download function is disabled
        
        Logger.info("Source adapters initialized and download functions registered")
        
        # Auto-login if enabled
        if jmcomic_config.get('auto_login') and jmcomic_config.get('username'):
            Logger.info("Auto-login enabled for JMComic")
            # Auto-login will be implemented when adapter login is fully integrated
        
        # 确保PicACG适配器配置包含完整设置
        Logger.info("Configuring PicACG adapter with user settings")
        
        # 更新适配器配置以包含所有用户设置
        picacg_image_server = picacg_config.get('image_server', 'storage.diwodiwo.xyz')
        self.picacg_adapter.config.update({
            'auto_login': picacg_config.get('auto_login', False),
            'email': picacg_config.get('email', ''),
            'password': picacg_config.get('password', ''),
            'endpoint': picacg_config.get('endpoint', 'https://picaapi.picacomic.com'),
            'image_server': picacg_image_server,
            'image_quality': picacg_config.get('image_quality', 'original'),
            'credentials': {
                'email': picacg_config.get('email', ''),
                'password': picacg_config.get('password', '')
            }
        })
        
        # 确保图片服务器配置正确设置到适配器
        self.picacg_adapter.set_image_server(picacg_image_server)
        
        # 如果有自动登录设置，记录日志
        if picacg_config.get('auto_login') and picacg_config.get('email'):
            Logger.info(f"Auto-login enabled for PicACG: {picacg_config.get('email')}")
        
        # 记录图片服务器设置
        Logger.info(f"PicACG image server: {picacg_image_server}")
        self.picacg_adapter.auto_login()
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Application exit code
        """
        if not self.main_window:
            Logger.error("Main window not initialized")
            return 1
        
        # Show main window
        self.main_window.show()
        
        Logger.info("Application running")
        
        # Start Qt event loop
        return self.qt_app.exec()
    
    def _on_application_closing(self) -> None:
        """Handle application closing event."""
        Logger.info("Application closing...")
        
        # Stop download manager
        if self.download_manager:
            # Cancel all active downloads
            # This will be implemented when download manager is fully integrated
            pass
        
        # Stop adapters
        if self.jmcomic_adapter:
            self.jmcomic_adapter.stop_worker_thread()
        if self.ehentai_adapter:
            self.ehentai_adapter.stop_worker_thread()
        if self.picacg_adapter:
            self.picacg_adapter.stop_worker_thread()
        
        # Close database
        if self.database:
            self.database.close()
        
        # Cleanup old logs
        Logger.cleanup_old_logs(days_to_keep=7)
        
        Logger.info("Application closed")
    
    def get_main_window(self) -> Optional[MainWindow]:
        """
        Get main window instance.
        
        Returns:
            MainWindow instance or None if not initialized
        """
        return self.main_window
    
    def get_config_manager(self) -> Optional[ConfigManager]:
        """
        Get config manager instance.
        
        Returns:
            ConfigManager instance or None if not initialized
        """
        return self.config_manager
    
    def get_database(self) -> Optional[Database]:
        """
        Get database instance.
        
        Returns:
            Database instance or None if not initialized
        """
        return self.database
    
    def get_download_manager(self) -> Optional[DownloadManager]:
        """
        Get download manager instance.
        
        Returns:
            DownloadManager instance or None if not initialized
        """
        return self.download_manager
    
    def get_adapter(self, source: str):
        """
        Get adapter for a specific source.
        
        Args:
            source: Source name ('jmcomic', 'ehentai', 'picacg')
            
        Returns:
            Adapter instance or None if not found
        """
        if source == 'jmcomic':
            return self.jmcomic_adapter
        elif source == 'ehentai':
            return self.ehentai_adapter
        elif source == 'picacg':
            return self.picacg_adapter
        return None


# Global application instance
_app_instance = None


def App():
    """Get global application instance."""
    return _app_instance


def main():
    """Main entry point for the application."""
    global _app_instance
    
    # Create and initialize application
    _app_instance = Application()
    
    if not _app_instance.initialize():
        Logger.error("Failed to initialize application")
        return 1
    
    # Run application
    exit_code = _app_instance.run()
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
