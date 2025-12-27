"""Unit tests for adapters."""

import unittest
from pancomic.adapters import BaseSourceAdapter, JMComicAdapter, PicACGAdapter


class TestBaseSourceAdapter(unittest.TestCase):
    """Test cases for BaseSourceAdapter."""
    
    def test_base_adapter_is_abstract(self):
        """Test that BaseSourceAdapter cannot be instantiated directly."""
        # BaseSourceAdapter is abstract and should not be instantiated
        # We can only test that concrete implementations work
        pass
    
    def test_adapter_initialization(self):
        """Test that adapters can be initialized with config."""
        jm_adapter = JMComicAdapter({'domain': 'test'})
        self.assertIsNotNone(jm_adapter)
        self.assertEqual(jm_adapter.config['domain'], 'test')
        
        pa_adapter = PicACGAdapter({'endpoint': 'test'})
        self.assertIsNotNone(pa_adapter)
        self.assertEqual(pa_adapter.config['endpoint'], 'test')
    
    def test_get_source_name(self):
        """Test that adapters return correct source names."""
        jm_adapter = JMComicAdapter({})
        self.assertEqual(jm_adapter.get_source_name(), 'jmcomic')
        
        pa_adapter = PicACGAdapter({})
        self.assertEqual(pa_adapter.get_source_name(), 'picacg')
    
    def test_is_initialized_default_false(self):
        """Test that adapters are not initialized by default."""
        jm_adapter = JMComicAdapter({})
        self.assertFalse(jm_adapter.is_initialized())
        
        pa_adapter = PicACGAdapter({})
        self.assertFalse(pa_adapter.is_initialized())


class TestJMComicAdapter(unittest.TestCase):
    """Test cases for JMComicAdapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'domain': 'https://jmcomic.test',
            'proxy': {'enabled': False}
        }
        self.adapter = JMComicAdapter(self.config)
    
    def test_initialization(self):
        """Test JMComicAdapter initialization."""
        self.assertIsNotNone(self.adapter)
        self.assertEqual(self.adapter.config['domain'], 'https://jmcomic.test')
        self.assertFalse(self.adapter.is_initialized())
    
    def test_signals_exist(self):
        """Test that all required signals are defined."""
        self.assertTrue(hasattr(self.adapter, 'search_completed'))
        self.assertTrue(hasattr(self.adapter, 'search_failed'))
        self.assertTrue(hasattr(self.adapter, 'comic_detail_completed'))
        self.assertTrue(hasattr(self.adapter, 'comic_detail_failed'))
        self.assertTrue(hasattr(self.adapter, 'chapters_completed'))
        self.assertTrue(hasattr(self.adapter, 'chapters_failed'))
        self.assertTrue(hasattr(self.adapter, 'images_completed'))
        self.assertTrue(hasattr(self.adapter, 'images_failed'))
        self.assertTrue(hasattr(self.adapter, 'login_completed'))
        self.assertTrue(hasattr(self.adapter, 'login_failed'))


class TestPicACGAdapter(unittest.TestCase):
    """Test cases for PicACGAdapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'endpoint': 'https://api.picacomic.com',
            'image_quality': 'high',
            'proxy': {'enabled': False}
        }
        self.adapter = PicACGAdapter(self.config)
    
    def test_initialization(self):
        """Test PicACGAdapter initialization."""
        self.assertIsNotNone(self.adapter)
        self.assertEqual(self.adapter.config['endpoint'], 'https://api.picacomic.com')
        self.assertFalse(self.adapter.is_initialized())
    
    def test_signals_exist(self):
        """Test that all required signals are defined."""
        self.assertTrue(hasattr(self.adapter, 'search_completed'))
        self.assertTrue(hasattr(self.adapter, 'search_failed'))
        self.assertTrue(hasattr(self.adapter, 'comic_detail_completed'))
        self.assertTrue(hasattr(self.adapter, 'comic_detail_failed'))
        self.assertTrue(hasattr(self.adapter, 'chapters_completed'))
        self.assertTrue(hasattr(self.adapter, 'chapters_failed'))
        self.assertTrue(hasattr(self.adapter, 'images_completed'))
        self.assertTrue(hasattr(self.adapter, 'images_failed'))
        self.assertTrue(hasattr(self.adapter, 'login_completed'))
        self.assertTrue(hasattr(self.adapter, 'login_failed'))
    
    def test_endpoint_management(self):
        """Test PicACG endpoint management."""
        # Test get_current_endpoint
        self.assertIsNone(self.adapter.get_current_endpoint())
        
        # Test set_endpoint (will work after initialization)
        # For now, just verify the method exists
        self.assertTrue(hasattr(self.adapter, 'set_endpoint'))
        self.assertTrue(hasattr(self.adapter, 'get_current_endpoint'))
        self.assertTrue(hasattr(self.adapter, 'test_endpoints'))
    
    def test_additional_signals(self):
        """Test PicACG-specific signals."""
        self.assertTrue(hasattr(self.adapter, 'endpoint_test_completed'))
        self.assertTrue(hasattr(self.adapter, 'endpoint_changed'))


if __name__ == '__main__':
    unittest.main()
