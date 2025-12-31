"""
下载管理页面 - 已禁用
显示和管理动漫视频下载队列

注意：动漫下载功能已被移除，此文件已禁用。
如需重新启用，请移除此注释并恢复相关功能。
"""

# 动漫下载功能已移除 - 此文件已禁用
# 如需重新启用，请移除此注释

"""
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QMessageBox, QMenu, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QCursor

from pancomic.infrastructure.download_queue_manager import DownloadQueueManager, DownloadStatus, DownloadTask


class DownloadManagerPage(QWidget):
    """下载管理页面"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # 初始化下载队列管理器
        self.download_manager = DownloadQueueManager()
        
        # 连接信号
        self.download_manager.queue_updated.connect(self._refresh_table)
        self.download_manager.task_progress.connect(self._update_task_progress)
        
        self._setup_ui()
        self._refresh_table()
        
        # 定时刷新
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_table)
        self._refresh_timer.start(5000)  # 每5秒刷新一次
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("下载管理")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 下载队列表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "动漫名称", "剧集", "状态", "进度", "创建时间", "输出路径", "操作"
        ])
        
        # 设置表格样式
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                gridline-color: #3a3a3a;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3a3a;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #ffffff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # 设置表格属性
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(3, 120)
        
        # 右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #3a3a3a; border-radius: 8px; padding: 10px;")
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # 统计信息
        self.stats_label = QLabel("队列: 0 | 下载中: 0 | 已完成: 0 | 失败: 0")
        self.stats_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        layout.addWidget(self.stats_label)
        
        layout.addStretch()
        
        # 操作按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_table)
        refresh_btn.setStyleSheet(self._get_button_style("#0078d4"))
        layout.addWidget(refresh_btn)
        
        clear_completed_btn = QPushButton("清理已完成")
        clear_completed_btn.clicked.connect(self._clear_completed)
        clear_completed_btn.setStyleSheet(self._get_button_style("#ff8c00"))
        layout.addWidget(clear_completed_btn)
        
        pause_all_btn = QPushButton("暂停全部")
        pause_all_btn.clicked.connect(self._pause_all)
        pause_all_btn.setStyleSheet(self._get_button_style("#dc3545"))
        layout.addWidget(pause_all_btn)
        
        return toolbar
    
    def _get_button_style(self, color: str) -> str:
        """获取按钮样式"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """
    
    def _refresh_table(self):
        """刷新表格"""
        tasks = self.download_manager.get_queue_tasks()
        
        self.table.setRowCount(len(tasks))
        
        for row, task in enumerate(tasks):
            # 动漫名称
            anime_name = task.anime.get('name', '未知')
            self.table.setItem(row, 0, QTableWidgetItem(anime_name))
            
            # 剧集信息
            episode_info = f"第{task.episode.get('ep', '?')}集 - {task.episode.get('name', '未知')}"
            self.table.setItem(row, 1, QTableWidgetItem(episode_info))
            
            # 状态
            status_text = self._get_status_text(task.status)
            status_item = QTableWidgetItem(status_text)
            status_item.setData(Qt.ItemDataRole.UserRole, task.task_id)
            self.table.setItem(row, 2, status_item)
            
            # 进度条
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(task.progress)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #3a3a3a;
                    border-radius: 3px;
                    text-align: center;
                    color: #ffffff;
                    background-color: #2d2d2d;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                    border-radius: 2px;
                }
            """)
            self.table.setCellWidget(row, 3, progress_bar)
            
            # 创建时间
            created_time = task.created_time[:19] if task.created_time else ""
            self.table.setItem(row, 4, QTableWidgetItem(created_time))
            
            # 输出路径
            output_path = task.output_path or "等待中..."
            self.table.setItem(row, 5, QTableWidgetItem(output_path))
            
            # 操作按钮
            action_widget = self._create_action_widget(task)
            self.table.setCellWidget(row, 6, action_widget)
        
        # 更新统计信息
        self._update_stats(tasks)
    
    def _get_status_text(self, status: str) -> str:
        """获取状态文本"""
        status_map = {
            DownloadStatus.PENDING.value: "等待中",
            DownloadStatus.DOWNLOADING.value: "下载中",
            DownloadStatus.COMPLETED.value: "已完成",
            DownloadStatus.FAILED.value: "失败",
            DownloadStatus.PAUSED.value: "暂停"
        }
        return status_map.get(status, status)
    
    def _create_action_widget(self, task: DownloadTask) -> QWidget:
        """创建操作按钮组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(3)
        
        if task.status == DownloadStatus.PENDING.value:
            # 等待中：可以取消
            cancel_btn = QPushButton("取消")
            cancel_btn.setFixedSize(50, 24)
            cancel_btn.clicked.connect(lambda: self._cancel_task(task.task_id))
            cancel_btn.setStyleSheet(self._get_small_button_style("#dc3545"))
            layout.addWidget(cancel_btn)
            
        elif task.status == DownloadStatus.DOWNLOADING.value:
            # 下载中：可以暂停
            pause_btn = QPushButton("暂停")
            pause_btn.setFixedSize(50, 24)
            pause_btn.clicked.connect(lambda: self._pause_task(task.task_id))
            pause_btn.setStyleSheet(self._get_small_button_style("#ff8c00"))
            layout.addWidget(pause_btn)
            
        elif task.status == DownloadStatus.COMPLETED.value:
            # 已完成：可以打开文件夹
            open_btn = QPushButton("打开")
            open_btn.setFixedSize(50, 24)
            open_btn.clicked.connect(lambda: self._open_file_location(task.output_path))
            open_btn.setStyleSheet(self._get_small_button_style("#107c10"))
            layout.addWidget(open_btn)
            
        elif task.status == DownloadStatus.FAILED.value:
            # 失败：可以重试
            retry_btn = QPushButton("重试")
            retry_btn.setFixedSize(50, 24)
            retry_btn.clicked.connect(lambda: self._retry_task(task.task_id))
            retry_btn.setStyleSheet(self._get_small_button_style("#0078d4"))
            layout.addWidget(retry_btn)
        
        # 删除按钮（所有状态都有）
        delete_btn = QPushButton("删除")
        delete_btn.setFixedSize(50, 24)
        delete_btn.clicked.connect(lambda: self._delete_task(task.task_id))
        delete_btn.setStyleSheet(self._get_small_button_style("#6c757d"))
        layout.addWidget(delete_btn)
        
        return widget
    
    def _get_small_button_style(self, color: str) -> str:
        """获取小按钮样式"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: #ffffff;
                border: none;
                border-radius: 3px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """
    
    def _update_stats(self, tasks: List[DownloadTask]):
        """更新统计信息"""
        total = len(tasks)
        downloading = len([t for t in tasks if t.status == DownloadStatus.DOWNLOADING.value])
        completed = len([t for t in tasks if t.status == DownloadStatus.COMPLETED.value])
        failed = len([t for t in tasks if t.status == DownloadStatus.FAILED.value])
        
        self.stats_label.setText(f"队列: {total} | 下载中: {downloading} | 已完成: {completed} | 失败: {failed}")
    
    def _update_task_progress(self, task_id: str, progress: int):
        """更新任务进度"""
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            if status_item and status_item.data(Qt.ItemDataRole.UserRole) == task_id:
                progress_bar = self.table.cellWidget(row, 3)
                if isinstance(progress_bar, QProgressBar):
                    progress_bar.setValue(progress)
                break
    
    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self.table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        status_item = self.table.item(row, 2)
        if not status_item:
            return
        
        task_id = status_item.data(Qt.ItemDataRole.UserRole)
        task = self.download_manager.get_task(task_id)
        if not task:
            return
        
        menu = QMenu(self)
        
        # 根据状态添加菜单项
        if task.status == DownloadStatus.PENDING.value:
            cancel_action = QAction("取消任务", self)
            cancel_action.triggered.connect(lambda: self._cancel_task(task_id))
            menu.addAction(cancel_action)
            
        elif task.status == DownloadStatus.DOWNLOADING.value:
            pause_action = QAction("暂停任务", self)
            pause_action.triggered.connect(lambda: self._pause_task(task_id))
            menu.addAction(pause_action)
            
        elif task.status == DownloadStatus.COMPLETED.value:
            open_action = QAction("打开文件位置", self)
            open_action.triggered.connect(lambda: self._open_file_location(task.output_path))
            menu.addAction(open_action)
            
        elif task.status == DownloadStatus.FAILED.value:
            retry_action = QAction("重试任务", self)
            retry_action.triggered.connect(lambda: self._retry_task(task_id))
            menu.addAction(retry_action)
        
        menu.addSeparator()
        
        delete_action = QAction("删除任务", self)
        delete_action.triggered.connect(lambda: self._delete_task(task_id))
        menu.addAction(delete_action)
        
        menu.exec(self.table.mapToGlobal(position))
    
    def _cancel_task(self, task_id: str):
        """取消任务"""
        if self.download_manager.remove_task(task_id):
            QMessageBox.information(self, "操作成功", "任务已取消")
        else:
            QMessageBox.warning(self, "操作失败", "无法取消任务")
    
    def _pause_task(self, task_id: str):
        """暂停任务"""
        # TODO: 实现暂停逻辑
        QMessageBox.information(self, "功能开发中", "暂停功能正在开发中")
    
    def _retry_task(self, task_id: str):
        """重试任务"""
        # TODO: 实现重试逻辑
        QMessageBox.information(self, "功能开发中", "重试功能正在开发中")
    
    def _delete_task(self, task_id: str):
        """删除任务"""
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            "确定要删除这个任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.download_manager.remove_task(task_id):
                QMessageBox.information(self, "操作成功", "任务已删除")
            else:
                QMessageBox.warning(self, "操作失败", "无法删除任务")
    
    def _open_file_location(self, file_path: str):
        """打开文件位置"""
        if not file_path:
            QMessageBox.warning(self, "操作失败", "文件路径为空")
            return
        
        import os
        import subprocess
        
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', '/select,', file_path])
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['open', '-R', file_path])
        except Exception as e:
            QMessageBox.warning(self, "操作失败", f"无法打开文件位置: {e}")
    
    def _clear_completed(self):
        """清理已完成的任务"""
        reply = QMessageBox.question(
            self, 
            "确认清理", 
            "确定要清理所有已完成的任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.download_manager.clear_completed_tasks()
            QMessageBox.information(self, "操作成功", "已完成的任务已清理")
    
    def _pause_all(self):
        """暂停所有任务"""
        # TODO: 实现暂停所有任务的逻辑
        QMessageBox.information(self, "功能开发中", "暂停全部功能正在开发中")
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.stop()
        
        if hasattr(self, 'download_manager'):
            self.download_manager.cleanup()