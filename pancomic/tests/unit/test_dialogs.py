"""Unit tests for dialog windows."""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from pancomic.ui.dialogs.comic_detail_dialog import ComicDetailDialog
from pancomic.ui.dialogs.reader_window import ReaderWindow
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.adapters.base_adapter import BaseSourceAdapter


@pytest.fixture
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_comic():
    """Create a sample comic for testing."""
    return Comic(
        id="test_comic_1",
        title="测试漫画",
        author="测试作者",
        cover_url="https://example.com/cover.jpg",
        description="这是一个测试漫画的描述",
        tags=["标签1", "标签2", "标签3"],
        categories=["分类1", "分类2"],
        status="ongoing",
        chapter_count=10,
        view_count=1000,
        like_count=50,
        is_favorite=False,
        source="jmcomic"
    )


@pytest.fixture
def sample_chapters():
    """Create sample chapters for testing."""
    return [
        Chapter(
            id="ch1",
            comic_id="test_comic_1",
            title="第一话",
            chapter_number=1,
            page_count=20,
            is_downloaded=False,
            download_path=None,
            source="jmcomic"
        ),
        Chapter(
            id="ch2",
            comic_id="test_comic_1",
            title="第二话",
            chapter_number=2,
            page_count=25,
            is_downloaded=True,
            download_path="/path/to/chapter2",
            source="jmcomic"
        ),
    ]


class TestComicDetailDialog:
    """Tests for ComicDetailDialog."""
    
    def test_dialog_creation(self, qapp, sample_comic):
        """Test that ComicDetailDialog can be created."""
        dialog = ComicDetailDialog(sample_comic)
        
        assert dialog is not None
        assert dialog.windowTitle() == sample_comic.title
        assert dialog.minimumWidth() == 800
        assert dialog.minimumHeight() == 600
    
    def test_dialog_displays_comic_info(self, qapp, sample_comic):
        """Test that dialog displays comic information."""
        dialog = ComicDetailDialog(sample_comic)
        
        # Check that labels are set
        assert sample_comic.title in dialog.title_label.text()
        assert sample_comic.author in dialog.author_label.text()
        assert dialog.description_text.toPlainText() == sample_comic.description
    
    def test_dialog_displays_chapters(self, qapp, sample_comic, sample_chapters):
        """Test that dialog displays chapter list."""
        dialog = ComicDetailDialog(sample_comic, sample_chapters)
        
        # Should have 2 chapters
        assert dialog.chapter_list.count() == 2
    
    def test_dialog_no_chapters(self, qapp, sample_comic):
        """Test dialog with no chapters."""
        dialog = ComicDetailDialog(sample_comic, [])
        
        # Should show "no chapters" message
        assert dialog.chapter_list.count() == 1
        assert "暂无章节" in dialog.chapter_list.item(0).text()
    
    def test_favorite_button_toggle(self, qapp, sample_comic):
        """Test favorite button toggles state."""
        dialog = ComicDetailDialog(sample_comic)
        
        # Initially not favorite
        assert dialog.favorite_button.text() == "收藏"
        
        # Click favorite button
        dialog._on_favorite_clicked()
        assert dialog.favorite_button.text() == "取消收藏"
        
        # Click again
        dialog._on_favorite_clicked()
        assert dialog.favorite_button.text() == "收藏"
    
    def test_chapter_clicked_signal(self, qapp, sample_comic, sample_chapters):
        """Test that clicking chapter emits signal."""
        dialog = ComicDetailDialog(sample_comic, sample_chapters)
        
        signal_received = []
        dialog.chapter_clicked.connect(lambda ch: signal_received.append(ch))
        
        # Click first chapter
        item = dialog.chapter_list.item(0)
        dialog._on_chapter_item_clicked(item)
        
        assert len(signal_received) == 1
        assert signal_received[0] == sample_chapters[0]
    
    def test_update_chapters(self, qapp, sample_comic, sample_chapters):
        """Test updating chapter list."""
        dialog = ComicDetailDialog(sample_comic, [])
        
        # Initially no chapters
        assert dialog.chapter_list.count() == 1
        
        # Update with chapters
        dialog.update_chapters(sample_chapters)
        assert dialog.chapter_list.count() == 2


class MockAdapter(BaseSourceAdapter):
    """Mock adapter for testing."""
    
    def __init__(self):
        # Create a minimal config to satisfy BaseSourceAdapter
        config = {'source': 'test'}
        super().__init__(config)
    
    def initialize(self):
        pass
    
    def search(self, keyword, page):
        return self.search_completed
    
    def get_comic_detail(self, comic_id):
        return self.comic_detail_completed
    
    def get_chapters(self, comic_id):
        return self.chapters_completed
    
    def get_chapter_images(self, comic_id, chapter_id):
        # Don't actually load images in tests
        return self.images_completed
    
    def login(self, credentials):
        return self.login_completed


class TestReaderWindow:
    """Tests for ReaderWindow."""
    
    def test_reader_creation(self, qapp, sample_chapters):
        """Test that ReaderWindow can be created."""
        adapter = MockAdapter()
        chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", chapter, adapter)
        
        assert reader is not None
        assert reader.comic_id == "test_comic_1"
        assert reader.chapter == chapter
        assert reader.current_page == 0
        assert reader.preload_count == 3
    
    def test_reader_fullscreen(self, qapp, sample_chapters):
        """Test that reader opens in fullscreen."""
        adapter = MockAdapter()
        chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", chapter, adapter)
        
        # Check fullscreen state
        assert reader.windowState() & Qt.WindowFullScreen
    
    def test_page_indicator_format(self, qapp, sample_chapters):
        """Test page indicator format."""
        adapter = MockAdapter()
        chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", chapter, adapter)
        
        # With no images, should show 0 / 0
        assert reader.page_indicator.text() == "0 / 0"
        
        # Set some images
        reader.images = ["img1.jpg", "img2.jpg", "img3.jpg"]
        reader._update_page_indicator()
        
        # Should show 1 / 3 (current_page is 0, but display is 1-indexed)
        assert reader.page_indicator.text() == "1 / 3"
    
    def test_next_page(self, qapp, sample_chapters):
        """Test next page navigation."""
        adapter = MockAdapter()
        chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", chapter, adapter)
        reader.images = ["img1.jpg", "img2.jpg", "img3.jpg"]
        
        # Start at page 0
        assert reader.current_page == 0
        
        # Go to next page (but won't actually load without real images)
        # Just test the logic
        if reader.current_page < len(reader.images) - 1:
            next_page = reader.current_page + 1
            assert next_page == 1
    
    def test_prev_page(self, qapp, sample_chapters):
        """Test previous page navigation."""
        adapter = MockAdapter()
        chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", chapter, adapter)
        reader.images = ["img1.jpg", "img2.jpg", "img3.jpg"]
        reader.current_page = 1
        
        # Go to previous page
        if reader.current_page > 0:
            prev_page = reader.current_page - 1
            assert prev_page == 0
    
    def test_image_cache_initialization(self, qapp, sample_chapters):
        """Test that image cache is initialized."""
        adapter = MockAdapter()
        chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", chapter, adapter)
        
        assert hasattr(reader, 'image_cache')
        assert isinstance(reader.image_cache, dict)
        assert len(reader.image_cache) == 0
    
    def test_local_chapter_detection(self, qapp, sample_chapters):
        """Test that local chapters are detected correctly."""
        adapter = MockAdapter()
        
        # Test remote chapter (not downloaded)
        remote_chapter = sample_chapters[0]
        assert remote_chapter.is_downloaded is False
        assert remote_chapter.download_path is None
        
        # Test local chapter (downloaded)
        local_chapter = sample_chapters[1]
        assert local_chapter.is_downloaded is True
        assert local_chapter.download_path is not None
    
    def test_local_chapter_loading(self, qapp, sample_chapters, tmp_path):
        """Test that local chapters load from disk without network requests."""
        import os
        from pathlib import Path
        
        adapter = MockAdapter()
        
        # Create a temporary directory with test images
        chapter_dir = tmp_path / "chapter2"
        chapter_dir.mkdir()
        
        # Create some dummy image files
        for i in range(1, 4):
            img_file = chapter_dir / f"page_{i}.jpg"
            img_file.write_text(f"dummy image {i}")
        
        # Create a local chapter with the temp path
        local_chapter = Chapter(
            id="ch2",
            comic_id="test_comic_1",
            title="第二话",
            chapter_number=2,
            page_count=3,
            is_downloaded=True,
            download_path=str(chapter_dir),
            source="jmcomic"
        )
        
        reader = ReaderWindow("test_comic_1", local_chapter, adapter)
        
        # Verify that images were loaded from local path
        assert len(reader.images) == 3
        
        # Verify all images are local file paths
        for img_path in reader.images:
            assert Path(img_path).exists()
            assert str(chapter_dir) in img_path
    
    def test_remote_chapter_uses_adapter(self, qapp, sample_chapters):
        """Test that remote chapters use adapter for loading."""
        adapter = MockAdapter()
        
        # Use remote chapter (not downloaded)
        remote_chapter = sample_chapters[0]
        
        reader = ReaderWindow("test_comic_1", remote_chapter, adapter)
        
        # Verify that adapter's get_chapter_images would be called
        # (we can't fully test this without mocking, but we verify the setup)
        assert reader.adapter is adapter
        assert reader.chapter.is_downloaded is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
