"""Tests for download functionality integration."""

import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.models.download_task import DownloadTask
from pancomic.infrastructure.download_manager import DownloadManager


class TestDownloadIntegration(unittest.TestCase):
    """Test download functionality integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock download manager
        self.download_manager = DownloadManager(max_concurrent=2)
        
        # Create test comic
        self.comic = Comic(
            id="test_comic_1",
            title="Test Comic",
            author="Test Author",
            cover_url="http://example.com/cover.jpg",
            description="Test description",
            tags=["tag1", "tag2"],
            categories=["category1"],
            status="ongoing",
            chapter_count=5,
            view_count=1000,
            like_count=100,
            is_favorite=False,
            source="jmcomic"
        )
        
        # Create test chapters
        self.chapters = [
            Chapter(
                id=f"chapter_{i}",
                comic_id="test_comic_1",
                title=f"Chapter {i}",
                chapter_number=i,
                page_count=20,
                is_downloaded=False,
                download_path=None,
                source="jmcomic"
            )
            for i in range(1, 6)
        ]
    
    def test_add_download_creates_task(self):
        """Test that adding a download creates a task."""
        # Add download
        task_id = self.download_manager.add_download(
            self.comic,
            self.chapters,
            "/tmp/downloads"
        )
        
        # Verify task was created
        self.assertIsNotNone(task_id)
        self.assertIsInstance(task_id, str)
        
        # Verify task is in queued tasks
        queued_tasks = self.download_manager.get_queued_tasks()
        self.assertEqual(len(queued_tasks), 1)
        self.assertEqual(queued_tasks[0].task_id, task_id)
        self.assertEqual(queued_tasks[0].comic.id, self.comic.id)
        self.assertEqual(len(queued_tasks[0].chapters), 5)
    
    def test_download_task_has_correct_initial_state(self):
        """Test that download task has correct initial state."""
        # Add download
        task_id = self.download_manager.add_download(
            self.comic,
            self.chapters,
            "/tmp/downloads"
        )
        
        # Get task
        queued_tasks = self.download_manager.get_queued_tasks()
        task = queued_tasks[0]
        
        # Verify initial state
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.progress, 0)
        self.assertEqual(task.current_chapter, 0)
        self.assertEqual(task.total_chapters, 5)
        self.assertIsNone(task.error_message)
        self.assertIsNone(task.completed_at)
    
    def test_cancel_download_removes_task(self):
        """Test that canceling a download removes the task."""
        # Add download
        task_id = self.download_manager.add_download(
            self.comic,
            self.chapters,
            "/tmp/downloads"
        )
        
        # Verify task exists
        queued_tasks = self.download_manager.get_queued_tasks()
        self.assertEqual(len(queued_tasks), 1)
        
        # Cancel download
        self.download_manager.cancel_download(task_id)
        
        # Verify task was removed
        queued_tasks = self.download_manager.get_queued_tasks()
        self.assertEqual(len(queued_tasks), 0)
    
    def test_multiple_downloads_are_queued(self):
        """Test that multiple downloads are properly queued."""
        # Add multiple downloads
        task_ids = []
        for i in range(3):
            comic = Comic(
                id=f"comic_{i}",
                title=f"Comic {i}",
                author="Author",
                cover_url="http://example.com/cover.jpg",
                description="Description",
                tags=[],
                categories=[],
                status="ongoing",
                chapter_count=5,
                view_count=100,
                like_count=10,
                is_favorite=False,
                source="jmcomic"
            )
            
            task_id = self.download_manager.add_download(
                comic,
                self.chapters,
                "/tmp/downloads"
            )
            task_ids.append(task_id)
        
        # Verify all tasks are queued or active
        queued_tasks = self.download_manager.get_queued_tasks()
        active_tasks = self.download_manager.get_active_tasks()
        total_tasks = len(queued_tasks) + len(active_tasks)
        
        self.assertEqual(total_tasks, 3)
        
        # Verify all task IDs are present
        all_task_ids = [t.task_id for t in queued_tasks] + [t.task_id for t in active_tasks]
        for task_id in task_ids:
            self.assertIn(task_id, all_task_ids)


class TestDownloadTaskModel(unittest.TestCase):
    """Test DownloadTask model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.comic = Comic(
            id="test_comic",
            title="Test Comic",
            author="Test Author",
            cover_url="http://example.com/cover.jpg",
            description="Test description",
            tags=[],
            categories=[],
            status="ongoing",
            chapter_count=5,
            view_count=100,
            like_count=10,
            is_favorite=False,
            source="jmcomic"
        )
        
        self.chapters = [
            Chapter(
                id=f"chapter_{i}",
                comic_id="test_comic",
                title=f"Chapter {i}",
                chapter_number=i,
                page_count=20,
                is_downloaded=False,
                download_path=None,
                source="jmcomic"
            )
            for i in range(1, 6)
        ]
    
    def test_calculate_progress(self):
        """Test progress calculation."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=0,
            current_chapter=0,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        # Test 0% progress
        self.assertEqual(task.calculate_progress(), 0)
        
        # Test 40% progress (2 of 5 chapters)
        task.current_chapter = 2
        self.assertEqual(task.calculate_progress(), 40)
        
        # Test 100% progress
        task.current_chapter = 5
        self.assertEqual(task.calculate_progress(), 100)
    
    def test_update_progress(self):
        """Test updating progress."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=0,
            current_chapter=0,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        # Update progress
        task.update_progress(3)
        
        self.assertEqual(task.current_chapter, 3)
        self.assertEqual(task.progress, 60)
    
    def test_mark_completed(self):
        """Test marking task as completed."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=50,
            current_chapter=2,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        # Mark as completed
        task.mark_completed()
        
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.current_chapter, 5)
        self.assertIsNotNone(task.completed_at)
        self.assertIsNone(task.error_message)
    
    def test_mark_failed(self):
        """Test marking task as failed."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=50,
            current_chapter=2,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        # Mark as failed
        error_msg = "Network error"
        task.mark_failed(error_msg)
        
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.error_message, error_msg)
    
    def test_pause_and_resume(self):
        """Test pausing and resuming task."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=50,
            current_chapter=2,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        # Pause
        task.pause()
        self.assertEqual(task.status, "paused")
        
        # Resume
        task.resume()
        self.assertEqual(task.status, "downloading")
    
    def test_is_active(self):
        """Test is_active method."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=0,
            current_chapter=0,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        self.assertTrue(task.is_active())
        
        task.status = "paused"
        self.assertFalse(task.is_active())
    
    def test_is_finished(self):
        """Test is_finished method."""
        task = DownloadTask(
            task_id="task_1",
            comic=self.comic,
            chapters=self.chapters,
            status="downloading",
            progress=0,
            current_chapter=0,
            total_chapters=5,
            error_message=None,
            created_at=datetime.now()
        )
        
        self.assertFalse(task.is_finished())
        
        task.status = "completed"
        self.assertTrue(task.is_finished())
        
        task.status = "failed"
        self.assertTrue(task.is_finished())


if __name__ == '__main__':
    unittest.main()
