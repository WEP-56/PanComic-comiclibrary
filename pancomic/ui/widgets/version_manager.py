"""
PanComic 版本管理组件
集成到设置页面的版本检测和更新功能
"""

import json
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QTextEdit, QProgressBar, 
    QMessageBox, QGroupBox, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont


class GitHubRelease:
    """GitHub Release 数据模型"""
    
    def __init__(self, data: dict):
        self.tag_name = data.get('tag_name', '')
        self.name = data.get('name', '')
        self.body = data.get('body', '')
        self.published_at = data.get('published_at', '')
        self.prerelease = data.get('prerelease', False)
        self.draft = data.get('draft', False)
        self.assets = data.get('assets', [])
        self.zipball_url = data.get('zipball_url', '')
        self.tarball_url = data.get('tarball_url', '')
        
    @property
    def version(self) -> str:
        """获取版本号"""
        return self.tag_name.lstrip('v')
    
    @property
    def published_date(self) -> str:
        """获取发布日期"""
        try:
            dt = datetime.fromisoformat(self.published_at.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return self.published_at
    
    @property
    def is_stable(self) -> bool:
        """是否为稳定版本"""
        return not self.prerelease and not self.draft
    
    @property
    def download_url(self) -> str:
        """获取下载链接"""
        # 优先使用 assets 中的文件
        for asset in self.assets:
            if asset.get('name', '').endswith(('.zip', '.exe', '.msi')):
                return asset.get('browser_download_url', '')
        
        # 如果没有 assets，使用源码 zip
        return self.zipball_url


class VersionFetcher(QThread):
    """版本获取线程"""
    
    versions_fetched = Signal(list)  # List[GitHubRelease]
    fetch_failed = Signal(str)  # error_message
    
    def __init__(self, repo_owner: str, repo_name: str):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name = repo_name
    
    def run(self):
        """获取版本列表"""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases"
            
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'PanComic-VersionManager'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            releases_data = response.json()
            releases = [GitHubRelease(data) for data in releases_data]
            
            self.versions_fetched.emit(releases)
            
        except Exception as e:
            self.fetch_failed.emit(str(e))


class VersionDownloader(QThread):
    """版本下载线程"""
    
    download_progress = Signal(int, int)  # current, total
    download_completed = Signal(str)  # file_path
    download_failed = Signal(str)  # error_message
    
    def __init__(self, release: GitHubRelease, download_dir: str):
        super().__init__()
        self.release = release
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self):
        """下载版本"""
        try:
            url = self.release.download_url
            if not url:
                self.download_failed.emit("没有可用的下载链接")
                return
            
            # 确定文件名
            filename = f"PanComic-{self.release.version}.zip"
            file_path = self.download_dir / filename
            
            # 下载文件
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.download_progress.emit(downloaded, total_size)
            
            self.download_completed.emit(str(file_path))
            
        except Exception as e:
            self.download_failed.emit(str(e))


class VersionManagerWidget(QWidget):
    """版本管理组件 - 集成到设置页面"""
    
    def __init__(self, repo_owner: str = "WEP-56", repo_name: str = "PanComic-comiclibrary", parent=None):
        super().__init__(parent)
        
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.releases: List[GitHubRelease] = []
        self.current_version = self._get_current_version()
        
        self._setup_ui()
        
        # 线程
        self.fetcher_thread = None
        self.downloader_thread = None
    
    def _get_current_version(self) -> str:
        """获取当前版本号"""
        try:
            # 尝试从配置文件或版本文件读取
            version_file = Path("version.txt")
            if version_file.exists():
                return version_file.read_text().strip()
            
            # 当前版本 (根据实际情况)
            return "0.3.0"
        except:
            return "0.2.0"
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # 当前版本信息
        current_version_group = QGroupBox("当前版本")
        current_version_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        current_layout = QHBoxLayout(current_version_group)
        
        self.current_version_label = QLabel(f"当前版本: v{self.current_version}")
        self.current_version_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #48bb78;")
        
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.setFixedSize(100, 35)
        self.check_update_btn.clicked.connect(self._fetch_versions)
        self.check_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #4299e1;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3182ce; }
            QPushButton:pressed { background-color: #2c5282; }
        """)
        
        current_layout.addWidget(self.current_version_label)
        current_layout.addStretch()
        current_layout.addWidget(self.check_update_btn)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：版本列表
        left_panel = self._create_version_list_panel()
        splitter.addWidget(left_panel)
        
        # 右侧：版本详情
        right_panel = self._create_version_details_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 400])
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4a5568;
                border-radius: 3px;
                background-color: #2d3748;
            }
            QProgressBar::chunk {
                background-color: #48bb78;
                border-radius: 2px;
            }
        """)
        
        # 状态标签
        self.status_label = QLabel("点击'检查更新'获取版本列表")
        self.status_label.setStyleSheet("color: #888888;")
        
        # 添加到主布局
        layout.addWidget(current_version_group)
        layout.addWidget(splitter)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
    
    def _create_version_list_panel(self) -> QWidget:
        """创建版本列表面板"""
        panel = QGroupBox("可用版本")
        panel.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        layout = QVBoxLayout(panel)
        
        # 过滤选项
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("显示:"))
        
        self.version_filter = QComboBox()
        self.version_filter.addItems(["所有版本", "仅稳定版", "仅预览版"])
        self.version_filter.currentTextChanged.connect(self._filter_versions)
        self.version_filter.setStyleSheet("""
            QComboBox {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 4px;
                padding: 5px;
                color: white;
                min-width: 100px;
            }
        """)
        
        filter_layout.addWidget(self.version_filter)
        filter_layout.addStretch()
        
        # 版本列表
        self.version_list = QListWidget()
        self.version_list.itemClicked.connect(self._on_version_selected)
        self.version_list.setStyleSheet("""
            QListWidget {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 5px;
                color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #4299e1;
            }
            QListWidget::item:hover {
                background-color: #3a4553;
            }
        """)
        
        layout.addLayout(filter_layout)
        layout.addWidget(self.version_list)
        
        return panel
    
    def _create_version_details_panel(self) -> QWidget:
        """创建版本详情面板"""
        panel = QGroupBox("版本详情")
        panel.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        layout = QVBoxLayout(panel)
        
        # 版本信息
        self.version_info_label = QLabel("选择一个版本查看详情")
        self.version_info_label.setAlignment(Qt.AlignCenter)
        self.version_info_label.setStyleSheet("color: #888888; font-style: italic;")
        
        # 更新日志
        changelog_label = QLabel("更新日志:")
        changelog_label.setStyleSheet("color: white; font-weight: bold;")
        
        self.changelog_text = QTextEdit()
        self.changelog_text.setMaximumHeight(200)
        self.changelog_text.setPlaceholderText("版本更新日志将在这里显示...")
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 8px;
                color: white;
            }
        """)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("下载此版本")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected_version)
        
        self.open_folder_btn = QPushButton("打开下载文件夹")
        self.open_folder_btn.clicked.connect(self._open_download_folder)
        
        # 按钮样式
        button_style = """
            QPushButton {
                background-color: #4299e1;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3182ce; }
            QPushButton:pressed { background-color: #2c5282; }
            QPushButton:disabled {
                background-color: #4a5568;
                color: #a0aec0;
            }
        """
        
        self.download_btn.setStyleSheet(button_style)
        self.open_folder_btn.setStyleSheet(button_style)
        
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.open_folder_btn)
        
        layout.addWidget(self.version_info_label)
        layout.addWidget(changelog_label)
        layout.addWidget(self.changelog_text)
        layout.addLayout(button_layout)
        
        return panel
    
    def _fetch_versions(self):
        """获取版本列表"""
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            return
        
        self.status_label.setText("正在获取版本列表...")
        self.status_label.setStyleSheet("color: #4299e1;")
        self.check_update_btn.setEnabled(False)
        
        self.fetcher_thread = VersionFetcher(self.repo_owner, self.repo_name)
        self.fetcher_thread.versions_fetched.connect(self._on_versions_fetched)
        self.fetcher_thread.fetch_failed.connect(self._on_fetch_failed)
        self.fetcher_thread.start()
    
    def _on_versions_fetched(self, releases: List[GitHubRelease]):
        """处理版本获取完成"""
        self.releases = releases
        self._update_version_list()
        
        self.status_label.setText(f"获取到 {len(releases)} 个版本")
        self.status_label.setStyleSheet("color: #48bb78;")
        self.check_update_btn.setEnabled(True)
        
        # 检查是否有新版本
        if releases and self._compare_versions(releases[0].version, self.current_version) > 0:
            self.status_label.setText(f"发现新版本: v{releases[0].version}")
            self.status_label.setStyleSheet("color: #48bb78; font-weight: bold;")
        else:
            self.status_label.setText("当前已是最新版本")
            self.status_label.setStyleSheet("color: #888888;")
    
    def _on_fetch_failed(self, error: str):
        """处理版本获取失败"""
        self.status_label.setText(f"获取失败: {error}")
        self.status_label.setStyleSheet("color: #f56565;")
        self.check_update_btn.setEnabled(True)
        
        QMessageBox.warning(self, "获取失败", f"无法获取版本列表:\n{error}")
    
    def _update_version_list(self):
        """更新版本列表显示"""
        self.version_list.clear()
        
        # 根据过滤器筛选版本
        filter_text = self.version_filter.currentText()
        filtered_releases = []
        
        for release in self.releases:
            if filter_text == "所有版本":
                filtered_releases.append(release)
            elif filter_text == "仅稳定版" and release.is_stable:
                filtered_releases.append(release)
            elif filter_text == "仅预览版" and not release.is_stable:
                filtered_releases.append(release)
        
        # 添加到列表
        for release in filtered_releases:
            item = QListWidgetItem()
            
            # 版本标签
            version_text = f"v{release.version}"
            if not release.is_stable:
                version_text += " (预览版)"
            if release.version == self.current_version:
                version_text += " (当前)"
            
            # 发布日期
            date_text = release.published_date
            
            item.setText(f"{version_text}\n{date_text}")
            item.setData(Qt.UserRole, release)
            
            self.version_list.addItem(item)
    
    def _filter_versions(self):
        """过滤版本列表"""
        if self.releases:
            self._update_version_list()
    
    def _on_version_selected(self, item: QListWidgetItem):
        """处理版本选择"""
        release = item.data(Qt.UserRole)
        if not release:
            return
        
        # 更新版本信息
        info_text = f"版本: v{release.version}\n"
        info_text += f"发布时间: {release.published_date}\n"
        info_text += f"类型: {'稳定版' if release.is_stable else '预览版'}"
        
        self.version_info_label.setText(info_text)
        self.version_info_label.setAlignment(Qt.AlignLeft)
        self.version_info_label.setStyleSheet("color: white;")
        
        # 更新更新日志
        self.changelog_text.setPlainText(release.body or "暂无更新日志")
        
        # 启用下载按钮
        self.download_btn.setEnabled(True)
        
        # 保存选中的版本
        self.selected_release = release
    
    def _download_selected_version(self):
        """下载选中的版本"""
        if not hasattr(self, 'selected_release'):
            return
        
        if self.downloader_thread and self.downloader_thread.isRunning():
            return
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"正在下载 v{self.selected_release.version}...")
        self.status_label.setStyleSheet("color: #4299e1;")
        
        # 开始下载
        download_dir = Path.cwd() / "downloads" / "versions"
        self.downloader_thread = VersionDownloader(self.selected_release, str(download_dir))
        self.downloader_thread.download_progress.connect(self._on_download_progress)
        self.downloader_thread.download_completed.connect(self._on_download_completed)
        self.downloader_thread.download_failed.connect(self._on_download_failed)
        self.downloader_thread.start()
    
    def _on_download_progress(self, current: int, total: int):
        """更新下载进度"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            
            # 转换为可读的大小
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.status_label.setText(f"下载中... {current_mb:.1f}MB / {total_mb:.1f}MB")
    
    def _on_download_completed(self, file_path: str):
        """下载完成"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"下载完成: {Path(file_path).name}")
        self.status_label.setStyleSheet("color: #48bb78;")
        
        QMessageBox.information(self, "下载完成", f"版本已下载到:\n{file_path}\n\n请手动解压并替换程序文件。")
    
    def _on_download_failed(self, error: str):
        """下载失败"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"下载失败: {error}")
        self.status_label.setStyleSheet("color: #f56565;")
        
        QMessageBox.warning(self, "下载失败", f"下载失败:\n{error}")
    
    def _open_download_folder(self):
        """打开下载文件夹"""
        download_dir = Path.cwd() / "downloads" / "versions"
        download_dir.mkdir(parents=True, exist_ok=True)
        
        import subprocess
        import sys
        
        if sys.platform == "win32":
            subprocess.run(["explorer", str(download_dir)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(download_dir)])
        else:
            subprocess.run(["xdg-open", str(download_dir)])
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """比较版本号，支持预发行版本"""
        def version_tuple(v):
            # 处理 v 前缀
            v = v.lstrip('v')
            
            # 分割版本号
            parts = v.split('.')
            
            # 确保至少有3个部分 (major.minor.patch)
            while len(parts) < 3:
                parts.append('0')
            
            # 转换为整数
            try:
                return tuple(int(part) for part in parts[:3])
            except ValueError:
                # 如果包含非数字字符，使用字符串比较
                return tuple(parts[:3])
        
        try:
            v1 = version_tuple(version1)
            v2 = version_tuple(version2)
            
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
            else:
                return 0
        except:
            # 回退到字符串比较
            if version1 > version2:
                return 1
            elif version1 < version2:
                return -1
            else:
                return 0