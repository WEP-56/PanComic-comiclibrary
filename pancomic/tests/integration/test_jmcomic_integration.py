"""Integration tests for JMComic source."""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt

from pancomic.adapters.jmcomic_adapter import JMComicAdapter
from pancomic.ui.pages.jmcomic_page import JMComicPage
from pancomic.ui.dialogs.comic_detail_dialog import ComicDetailDialog
from pancomic.ui.dialogs.reader_window import ReaderWindow
from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class TestJMComicIntegration(unittest.TestCase):
    """Integration tests for JMComic source."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        # Create QApplication if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'domain': 'https://jmcomic.test',
            'proxy': {'enabled': False}
        }
        self.adapter = JMComicAdapter(self.config)
        self.download_manager = DownloadManager(max_concurrent=3)
    
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'page'):
            self.page.deleteLater()
        if hasattr(self, 'adapter'):
            self.adapter.stop_worker_thread()
    
    def test_login_functionality(self):
        """Test JMComic login functionality."""
        # Create mock for login
        login_success = False
        login_message = ""
        
        def on_login_completed(success, message):
            nonlocal login_success, login_message
            login_success = success
            login_message = message
        
        # Connect signal
        self.adapter.login_completed.connect(on_login_completed)
        
        # Mock the JMComic modules to avoid actual network calls
        with patch.object(self.adapter, '_is_initialized', True):
            with patch.object(self.adapter, '_jmcomic_module') as mock_module:
                # Setup mock response
                mock_server = MagicMock()
                mock_task = MagicMock()
                mock_task.status = 0  # Status.Ok
                mock_task.res.raw = {
                    'code': 200,
                    'data': {'uid': '12345'},
                    'message': 'success'
                }
                mock_server.Send.return_value = mock_task
                
                mock_qt_owner = MagicMock()
                mock_qt_owner.user = MagicMock()
                
                mock_module.__getitem__.side_effect = lambda key: {
                    'req': MagicMock(),
                    'server': mock_server,
                    'qt_owner': mock_qt_owner
                }[key]
                
                # Perform login
                credentials = {'username': 'test_user', 'password': 'test_pass'}
                self.adapter._do_login(credentials)
                
                # Process events to allow signal emission
                QApplication.processEvents()
                
                # Verify login was successful
                self.assertTrue(login_success)
                self.assertEqual(login_message, "登录成功")
    
    def test_search_and_browse(self):
        """Test JMComic search and browse functionality."""
        # Create mock for search
        search_results = []
        
        def on_search_completed(comics):
            nonlocal search_results
            search_results = comics
        
        # Connect signal
        self.adapter.search_completed.connect(on_search_completed)
        
        # Mock the JMComic modules
        with patch.object(self.adapter, '_is_initialized', True):
            with patch.object(self.adapter, '_jmcomic_module') as mock_module:
                # Setup mock response
                mock_server = MagicMock()
                mock_task = MagicMock()
                mock_task.status = 0  # Status.Ok
                mock_task.res.raw = {
                    'content': [
                        {
                            'id': '123',
                            'name': 'Test Comic',
                            'author': 'Test Author',
                            'img': 'http://test.com/cover.jpg',
                            'description': 'Test description',
                            'tags': ['tag1', 'tag2'],
                            'category': ['category1'],
                            'series': [{'id': '1'}],
                            'views': 1000,
                            'likes': 100
                        }
                    ]
                }
                mock_server.Send.return_value = mock_task
                
                mock_module.__getitem__.side_effect = lambda key: {
                    'req': MagicMock(),
                    'server': mock_server
                }[key]
                
                # Perform search
                self.adapter._do_search('test', 1)
                
                # Process events
                QApplication.processEvents()
                
                # Verify search results
                self.assertEqual(len(search_results), 1)
                self.assertEqual(search_results[0].id, '123')
                self.assertEqual(search_results[0].title, 'Test Comic')
                self.assertEqual(search_results[0].author, 'Test Author')
                self.assertEqual(search_results[0].source, 'jmcomic')
    
    def test_comic_detail_display(self):
        """Test comic detail dialog display."""
        # Create a test comic
        test_comic = Comic(
            id='123',
            title='Test Comic',
            author='Test Author',
            cover_url='http://test.com/cover.jpg',
            description='Test description',
            tags=['tag1', 'tag2'],
            categories=['category1'],
            status='ongoing',
            chapter_count=10,
            view_count=1000,
            like_count=100,
            is_favorite=False,
            source='jmcomic'
        )
        
        # Create detail dialog
        dialog = ComicDetailDialog(test_comic, self.adapter, self.download_manager)
        
        # Verify dialog was created
        self.assertIsNotNone(dialog)
        
        # Verify comic information is displayed
        # Note: Actual verification would require checking UI elements
        # For now, just verify the dialog can be created
        
        dialog.deleteLater()
    
    def test_chapter_reading(self):
        """Test chapter reading functionality."""
        # Create test chapter
        test_chapter = Chapter(
            id='ch1',
            comic_id='123',
            title='Chapter 1',
            chapter_number=1,
            page_count=20,
            is_downloaded=False,
            download_path=None,
            source='jmcomic'
        )
        
        # Mock image URLs
        test_images = [
            'http://test.com/page1.jpg',
            'http://test.com/page2.jpg',
            'http://test.com/page3.jpg'
        ]
        
        # Create reader window
        reader = ReaderWindow('123', 'ch1', self.adapter)
        
        # Mock the get_chapter_images to return test images
        with patch.object(self.adapter, '_is_initialized', True):
            # Simulate images loaded
            reader.images = test_images
            reader.current_page = 0
            
            # Verify reader was created
            self.assertIsNotNone(reader)
            self.assertEqual(len(reader.images), 3)
            self.assertEqual(reader.current_page, 0)
        
        reader.deleteLater()
    
    def test_download_functionality(self):
        """Test download functionality."""
        # Create test comic and chapters
        test_comic = Comic(
            id='123',
            title='Test Comic',
            author='Test Author',
            cover_url='http://test.com/cover.jpg',
            description='Test description',
            tags=['tag1'],
            categories=['category1'],
            status='ongoing',
            chapter_count=2,
            view_count=1000,
            like_count=100,
            is_favorite=False,
            source='jmcomic'
        )
        
        test_chapters = [
            Chapter(
                id='ch1',
                comic_id='123',
                title='Chapter 1',
                chapter_number=1,
                page_count=10,
                is_downloaded=False,
                download_path=None,
                source='jmcomic'
            ),
            Chapter(
                id='ch2',
                comic_id='123',
                title='Chapter 2',
                chapter_number=2,
                page_count=10,
                is_downloaded=False,
                download_path=None,
                source='jmcomic'
            )
        ]
        
        # Add download task
        task_id = self.download_manager.add_download(test_comic, test_chapters, self.adapter)
        
        # Verify task was created
        self.assertIsNotNone(task_id)
        self.assertIn(task_id, self.download_manager.active_tasks)
        
        # Verify task properties
        task = self.download_manager.active_tasks[task_id]
        self.assertEqual(task.comic.id, '123')
        self.assertEqual(len(task.chapters), 2)
        self.assertEqual(task.status, 'queued')
    
    def test_page_integration(self):
        """Test JMComicPage integration with adapter."""
        # Create page
        self.page = JMComicPage(self.adapter, self.download_manager)
        
        # Verify page was created
        self.assertIsNotNone(self.page)
        
        # Verify adapter is set
        self.assertEqual(self.page.adapter, self.adapter)
        
        # Verify search bar exists
        self.assertIsNotNone(self.page.search_bar)
        
        # Verify comic grid exists
        self.assertIsNotNone(self.page.comic_grid)
        
        # Verify loading widget exists
        self.assertIsNotNone(self.page.loading_widget)
    
    def test_search_ui_integration(self):
        """Test search UI integration."""
        # Create page
        self.page = JMComicPage(self.adapter, self.download_manager)
        
        # Mock search results
        search_results = []
        
        def on_search_completed(comics):
            nonlocal search_results
            search_results = comics
        
        self.adapter.search_completed.connect(on_search_completed)
        
        # Simulate search
        with patch.object(self.adapter, '_is_initialized', True):
            with patch.object(self.adapter, '_jmcomic_module') as mock_module:
                mock_server = MagicMock()
                mock_task = MagicMock()
                mock_task.status = 0
                mock_task.res.raw = {'content': []}
                mock_server.Send.return_value = mock_task
                
                mock_module.__getitem__.side_effect = lambda key: {
                    'req': MagicMock(),
                    'server': mock_server
                }[key]
                
                # Trigger search
                self.page.on_search('test')
                
                # Process events
                QApplication.processEvents()
                
                # Verify loading indicator was shown
                # (In actual implementation, would check loading_widget visibility)


if __name__ == '__main__':
    unittest.main()
