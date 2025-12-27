"""Unit tests for infrastructure components."""

import unittest
import tempfile
import shutil
from pathlib import Path
import json
from datetime import datetime

from pancomic.core.config_manager import ConfigManager
from pancomic.core.logger import Logger
from pancomic.infrastructure.database import Database
from pancomic.infrastructure.image_cache import ImageCache
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"
        
        # Create a test config file
        test_config = {
            "general": {
                "theme": "dark",
                "language": "zh_CN",
                "auto_check_updates": True,
                "window_size": {"width": 1400, "height": 900}
            },
            "download": {
                "download_path": "",
                "concurrent_downloads": 3,
                "auto_retry": True,
                "max_retries": 3
            },
            "cache": {
                "cache_size_mb": 500,
                "cache_directory": "",
                "enable_cache": True
            },
            "jmcomic": {
                "enabled": True,
                "auto_login": False,
                "proxy": {"enabled": False, "address": "", "port": 0},
                "image_quality": "high"
            },
            "picacg": {
                "enabled": True,
                "auto_login": False,
                "api_endpoint": "https://picaapi.picacomic.com",
                "available_endpoints": ["https://picaapi.picacomic.com"],
                "proxy": {"enabled": False, "address": "", "port": 0},
                "image_quality": "original"
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_load_config(self):
        """Test loading configuration."""
        manager = ConfigManager(str(self.config_path))
        config = manager.load_config()
        
        self.assertIsNotNone(config)
        self.assertEqual(config['general']['theme'], 'dark')
        self.assertEqual(config['download']['concurrent_downloads'], 3)
    
    def test_save_config(self):
        """Test saving configuration."""
        manager = ConfigManager(str(self.config_path))
        manager.load_config()
        
        manager.config['general']['theme'] = 'light'
        manager.save_config()
        
        # Reload and verify
        manager2 = ConfigManager(str(self.config_path))
        config = manager2.load_config()
        self.assertEqual(config['general']['theme'], 'light')
    
    def test_get_source_config(self):
        """Test getting source-specific configuration."""
        manager = ConfigManager(str(self.config_path))
        manager.load_config()
        
        jmcomic_config = manager.get_source_config('jmcomic')
        self.assertTrue(jmcomic_config['enabled'])
        self.assertEqual(jmcomic_config['image_quality'], 'high')
    
    def test_update_source_config(self):
        """Test updating source configuration."""
        manager = ConfigManager(str(self.config_path))
        manager.load_config()
        
        manager.update_source_config('jmcomic', {'auto_login': True})
        self.assertTrue(manager.config['jmcomic']['auto_login'])


class TestLogger(unittest.TestCase):
    """Test Logger functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        # Reset logger for each test
        Logger._initialized = False
        Logger._logger = None
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close all logger handlers to release file locks
        if Logger._logger:
            for handler in Logger._logger.handlers[:]:
                handler.close()
                Logger._logger.removeHandler(handler)
        
        # Reset logger state
        Logger._initialized = False
        Logger._logger = None
        
        # Now we can safely remove the directory
        try:
            shutil.rmtree(self.temp_dir)
        except PermissionError:
            # On Windows, sometimes files are still locked
            import time
            time.sleep(0.1)
            shutil.rmtree(self.temp_dir)
    
    def test_logger_setup(self):
        """Test logger initialization."""
        Logger.setup(self.temp_dir, level='INFO')
        
        # Verify log directory was created
        self.assertTrue(Path(self.temp_dir).exists())
    
    def test_logger_messages(self):
        """Test logging messages."""
        Logger.setup(self.temp_dir, level='DEBUG')
        
        # These should not raise exceptions
        Logger.debug("Debug message")
        Logger.info("Info message")
        Logger.warning("Warning message")
        Logger.error("Error message")


class TestDatabase(unittest.TestCase):
    """Test Database functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(str(self.db_path))
        self.db.initialize_schema()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_get_comic(self):
        """Test saving and retrieving a comic."""
        comic = Comic(
            id="test123",
            title="Test Comic",
            author="Test Author",
            cover_url="http://example.com/cover.jpg",
            description="Test description",
            tags=["tag1", "tag2"],
            categories=["category1"],
            status="ongoing",
            chapter_count=10,
            view_count=100,
            like_count=50,
            is_favorite=False,
            source="jmcomic",
            created_at=datetime.now()
        )
        
        self.db.save_comic(comic)
        
        retrieved = self.db.get_comic("test123", "jmcomic")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Test Comic")
        self.assertEqual(retrieved.author, "Test Author")
    
    def test_save_and_get_chapter(self):
        """Test saving and retrieving a chapter."""
        # First save a comic
        comic = Comic(
            id="comic123",
            title="Test Comic",
            author="Test Author",
            cover_url="http://example.com/cover.jpg",
            description="Test description",
            tags=[],
            categories=[],
            status="ongoing",
            chapter_count=1,
            view_count=0,
            like_count=0,
            is_favorite=False,
            source="jmcomic"
        )
        self.db.save_comic(comic)
        
        # Now save a chapter
        chapter = Chapter(
            id="chapter1",
            comic_id="comic123",
            title="Chapter 1",
            chapter_number=1,
            page_count=20,
            is_downloaded=False,
            download_path=None,
            source="jmcomic"
        )
        self.db.save_chapter(chapter)
        
        chapters = self.db.get_chapters("comic123", "jmcomic")
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].title, "Chapter 1")


class TestImageCache(unittest.TestCase):
    """Test ImageCache functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        # Reset singleton for testing
        ImageCache._instance = None
        self.cache = ImageCache(self.temp_dir, max_size_mb=10)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.cache.clear()
        shutil.rmtree(self.temp_dir)
        ImageCache._instance = None
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        self.assertEqual(self.cache.max_size_mb, 10)
        self.assertTrue(self.cache.cache_dir.exists())
    
    def test_singleton_pattern(self):
        """Test that ImageCache follows singleton pattern."""
        cache1 = ImageCache.instance()
        cache2 = ImageCache.instance()
        self.assertIs(cache1, cache2)
    
    def test_url_to_filename(self):
        """Test URL to filename conversion."""
        url = "http://example.com/image.jpg"
        filename = self.cache._url_to_filename(url)
        
        self.assertTrue(filename.endswith('.cache'))
        self.assertEqual(len(filename), 70)  # SHA256 hash (64 chars) + '.cache' (6 chars)


if __name__ == '__main__':
    unittest.main()
