#!/usr/bin/env python3
"""
ClipNamer Pro - Professional Video Clip Organizer with Preview
"""

import sys
import os
import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import subprocess
from dataclasses import dataclass, asdict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog, QMessageBox,
    QCheckBox, QListWidget, QListWidgetItem, QComboBox, QFrame,
    QGroupBox, QGridLayout, QScrollArea, QLineEdit, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QTextEdit, QTabWidget, QDoubleSpinBox, QFormLayout, QDialog,
    QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QSlider,
    QSizePolicy, QAbstractItemView, QMenu, QAction, QToolBar,
    QStatusBar, QStyle
)
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, QTimer, QSize, QRect, pyqtSlot, QByteArray, QUrl
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette, QBrush, QLinearGradient, QPixmap, QImage, QPainter, QPen
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

# Constants
APP_NAME = "ClipNamer Pro"
VERSION = "2.0.0"
SUPPORTED_FORMATS = {".mp4", ".mov", ".mkv", ".mxf", ".avi", ".wmv", ".flv", ".webm", ".mts", ".m2ts"}
SETTINGS_FILE = Path.home() / ".clipnamer_pro_settings.json"
PRESETS_FILE = Path.home() / ".clipnamer_pro_presets.json"
THUMBNAIL_CACHE = Path.home() / ".clipnamer_thumbnails"

# Create thumbnail cache directory
THUMBNAIL_CACHE.mkdir(exist_ok=True, parents=True)

@dataclass
class ClipInfo:
    """Information about a video clip."""
    original_path: Path
    filename: str
    extension: str
    size: int
    created_date: datetime
    modified_date: datetime
    camera_model: str = ""
    camera_serial: str = ""
    resolution: str = ""
    frame_rate: float = 0.0
    duration: float = 0.0
    scene: str = ""
    take: int = 0
    shot_type: str = ""
    description: str = ""
    notes: str = ""
    custom_fields: Dict[str, str] = None
    thumbnail_path: Optional[Path] = None
    
    def __post_init__(self):
        if self.custom_fields is None:
            self.custom_fields = {}
    
    @property
    def folder(self) -> Path:
        return self.original_path.parent
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['original_path'] = str(self.original_path)
        data['created_date'] = self.created_date.isoformat()
        data['modified_date'] = self.modified_date.isoformat()
        data['thumbnail_path'] = str(self.thumbnail_path) if self.thumbnail_path else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ClipInfo':
        """Create from dictionary."""
        data = data.copy()
        data['original_path'] = Path(data['original_path'])
        data['created_date'] = datetime.fromisoformat(data['created_date'])
        data['modified_date'] = datetime.fromisoformat(data['modified_date'])
        if data.get('thumbnail_path'):
            data['thumbnail_path'] = Path(data['thumbnail_path'])
        else:
            data['thumbnail_path'] = None
        return cls(**data)
    
    def get_thumbnail(self, force_regenerate=False) -> Optional[Path]:
        """Get or generate thumbnail for this clip."""
        if self.thumbnail_path and self.thumbnail_path.exists() and not force_regenerate:
            return self.thumbnail_path
        
        # Generate thumbnail filename based on file hash
        import hashlib
        file_hash = hashlib.md5(str(self.original_path).encode()).hexdigest()[:16]
        thumbnail_name = f"{file_hash}_{self.original_path.stem}_thumb.jpg"
        thumbnail_path = THUMBNAIL_CACHE / thumbnail_name
        
        try:
            # Use ffmpeg to extract thumbnail at 10% of duration
            thumbnail_time = 1  # Default to 1 second
            
            if self.duration > 0:
                thumbnail_time = min(self.duration * 0.1, 10)  # Cap at 10 seconds
            
            cmd = [
                "ffmpeg", "-y", "-ss", str(thumbnail_time),
                "-i", str(self.original_path),
                "-vframes", "1",
                "-q:v", "2",  # Quality: 2-31 (lower is better)
                "-vf", "scale=320:-1",  # Scale to 320 width
                str(thumbnail_path)
            ]
            
            # Run ffmpeg
            result = subprocess.run(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                timeout=10
            )
            
            if result.returncode == 0 and thumbnail_path.exists():
                self.thumbnail_path = thumbnail_path
                return thumbnail_path
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # Create a placeholder thumbnail
            self.create_placeholder_thumbnail(thumbnail_path)
        
        return None
    
    def create_placeholder_thumbnail(self, thumbnail_path: Path):
        """Create a placeholder thumbnail when ffmpeg fails."""
        try:
            pixmap = QPixmap(320, 180)
            pixmap.fill(QColor("#2c3e50"))
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw video icon
            painter.setPen(QColor("#ecf0f1"))
            painter.setFont(QFont("Arial", 48, QFont.Bold))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, "🎬")
            
            # Draw filename
            painter.setFont(QFont("Arial", 10))
            text_rect = QRect(10, 140, 300, 30)
            painter.drawText(text_rect, Qt.AlignCenter, self.filename[:30])
            
            painter.end()
            
            pixmap.save(str(thumbnail_path), "JPEG")
            self.thumbnail_path = thumbnail_path
            
        except Exception:
            pass

@dataclass
class NamingTemplate:
    """Naming template for clips."""
    name: str
    template: str
    description: str = ""
    
    AVAILABLE_FIELDS = {
        "Scene": "Scene number or name",
        "Take": "Take number (padded to 3 digits)",
        "ShotType": "Type of shot (WS, MS, CU, etc.)",
        "Camera": "Camera model abbreviation",
        "CameraSerial": "Last 4 digits of camera serial",
        "Date": "Recording date (YYYYMMDD)",
        "Time": "Recording time (HHMMSS)",
        "Project": "Project name",
        "Resolution": "Video resolution",
        "FPS": "Frame rate",
        "Duration": "Clip duration in seconds",
        "OriginalName": "Original filename",
        "Counter": "Sequential counter",
        "Description": "Custom description",
        "Notes": "Custom notes"
    }

class MetadataExtractor(QObject):
    """Extracts metadata from video files using ffprobe."""
    
    metadata_extracted = pyqtSignal(object, dict)
    finished = pyqtSignal()
    error = pyqtSignal(object, str)
    
    def __init__(self, files: List[Path]):
        super().__init__()
        self.files = files
        self.running = True
    
    def run(self):
        """Extract metadata from all files."""
        for file_path in self.files:
            if not self.running:
                break
            
            try:
                metadata = self.extract_metadata(file_path)
                self.metadata_extracted.emit(file_path, metadata)
            except Exception as e:
                self.error.emit(file_path, str(e))
        
        self.finished.emit()
    
    def extract_metadata(self, file_path: Path) -> Dict:
        """Extract metadata using ffprobe."""
        metadata = {
            "camera_model": "",
            "camera_serial": "",
            "resolution": "",
            "frame_rate": 0.0,
            "duration": 0.0,
            "creation_time": ""
        }
        
        try:
            # Get basic stream info
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration",
                "-show_entries", "format_tags=creation_time,model,make,serial",
                "-of", "json",
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Extract video info
                if "streams" in data and len(data["streams"]) > 0:
                    stream = data["streams"][0]
                    width = stream.get("width", 0)
                    height = stream.get("height", 0)
                    if width and height:
                        metadata["resolution"] = f"{width}x{height}"
                    
                    # Frame rate
                    r_frame_rate = stream.get("r_frame_rate", "0/1")
                    if "/" in r_frame_rate:
                        num, den = map(int, r_frame_rate.split("/"))
                        if den > 0:
                            metadata["frame_rate"] = round(num / den, 2)
                    
                    # Duration
                    duration = stream.get("duration", "0")
                    if duration:
                        metadata["duration"] = float(duration)
                
                # Extract format tags
                if "format" in data and "tags" in data["format"]:
                    tags = data["format"]["tags"]
                    metadata["camera_model"] = tags.get("model", tags.get("Make", ""))
                    metadata["camera_serial"] = tags.get("serial", "")
                    metadata["creation_time"] = tags.get("creation_time", "")
            
            # Get file stats
            stat = file_path.stat()
            metadata["file_size"] = stat.st_size
            metadata["created"] = datetime.fromtimestamp(stat.st_ctime)
            metadata["modified"] = datetime.fromtimestamp(stat.st_mtime)
            
        except subprocess.TimeoutExpired:
            metadata["error"] = "Timeout"
        except json.JSONDecodeError:
            metadata["error"] = "Invalid format"
        except Exception as e:
            metadata["error"] = str(e)
        
        return metadata

class ThumbnailGenerator(QObject):
    """Generates thumbnails for video clips in background."""
    
    thumbnail_generated = pyqtSignal(Path, Path)
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()
    
    def __init__(self, clips: List[ClipInfo]):
        super().__init__()
        self.clips = clips
        self.running = True
    
    def run(self):
        """Generate thumbnails for all clips."""
        total = len(self.clips)
        
        for i, clip in enumerate(self.clips):
            if not self.running:
                break
            
            thumbnail_path = clip.get_thumbnail()
            if thumbnail_path:
                self.thumbnail_generated.emit(clip.original_path, thumbnail_path)
            
            self.progress.emit(i + 1, total)
        
        self.finished.emit()

class VideoPreviewWidget(QWidget):
    """Widget for video preview with controls."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_clip: Optional[ClipInfo] = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Video player
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.video_widget)
        
        # Media player
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setVolume(50)
        
        # Controls
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        
        # Play/pause button
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_btn)
        
        # Stop button
        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.setFixedSize(32, 32)
        self.stop_btn.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.stop_btn)
        
        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.position_slider)
        
        # Time label
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(100)
        controls_layout.addWidget(self.time_label)
        
        # Volume
        controls_layout.addWidget(QLabel("🔊"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.valueChanged.connect(self.set_volume)
        controls_layout.addWidget(self.volume_slider)
        
        layout.addWidget(controls_widget)
        
        # Info display
        self.info_label = QLabel("No video loaded")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.info_label)
        
        # Connect signals
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.stateChanged.connect(self.state_changed)
    
    def load_clip(self, clip: ClipInfo):
        """Load a clip for preview."""
        self.current_clip = clip
        self.media_player.stop()
        
        video_url = QUrl.fromLocalFile(str(clip.original_path))
        self.media_player.setMedia(QMediaContent(video_url))
        
        # Update info
        info_text = f"{clip.filename}"
        if clip.duration > 0:
            mins = int(clip.duration // 60)
            secs = int(clip.duration % 60)
            info_text += f" | {mins}:{secs:02d}"
        if clip.resolution:
            info_text += f" | {clip.resolution}"
        if clip.frame_rate > 0:
            info_text += f" | {clip.frame_rate}fps"
        
        self.info_label.setText(info_text)
        self.position_slider.setValue(0)
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
    
    def toggle_playback(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
    
    def stop_playback(self):
        self.media_player.stop()
    
    def set_position(self, position):
        self.media_player.setPosition(position)
    
    def set_volume(self, volume):
        self.media_player.setVolume(volume)
    
    def position_changed(self, position):
        self.position_slider.setValue(position)
        duration = self.media_player.duration()
        if duration > 0:
            current_time = self.format_time(position)
            total_time = self.format_time(duration)
            self.time_label.setText(f"{current_time} / {total_time}")
    
    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
    
    def state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
    
    def format_time(self, milliseconds):
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def stop(self):
        self.media_player.stop()
        self.current_clip = None
        self.info_label.setText("No video loaded")
        self.time_label.setText("00:00 / 00:00")
        self.position_slider.setValue(0)

class ClipListWidget(QListWidget):
    """Custom list widget for clips with thumbnails."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(120, 80))
        self.setResizeMode(QListWidget.Adjust)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setSpacing(10)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
            QListWidget::item {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                padding: 5px;
            }
            QListWidget::item:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QListWidget::item:selected {
                background-color: #4361ee;
                color: white;
                border-color: #3a56d4;
            }
        """)
    
    def add_clip_item(self, clip: ClipInfo, index: int):
        """Add a clip with thumbnail to the list."""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, index)
        
        # Set text
        display_text = clip.filename
        if clip.scene:
            display_text = f"{clip.scene}_{clip.take:03d}" if clip.take > 0 else clip.scene
        item.setText(display_text)
        
        # Set tooltip
        tooltip = f"File: {clip.filename}"
        if clip.scene:
            tooltip += f"\nScene: {clip.scene}"
        if clip.take > 0:
            tooltip += f"\nTake: {clip.take}"
        if clip.shot_type:
            tooltip += f"\nShot: {clip.shot_type}"
        if clip.duration > 0:
            mins = int(clip.duration // 60)
            secs = int(clip.duration % 60)
            tooltip += f"\nDuration: {mins}:{secs:02d}"
        item.setToolTip(tooltip)
        
        # Load thumbnail
        thumbnail = clip.get_thumbnail()
        if thumbnail and thumbnail.exists():
            pixmap = QPixmap(str(thumbnail))
            if not pixmap.isNull():
                if pixmap.width() > 120 or pixmap.height() > 80:
                    pixmap = pixmap.scaled(120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(pixmap))
            else:
                self.set_placeholder_icon(item, clip)
        else:
            self.set_placeholder_icon(item, clip)
        
        self.addItem(item)
    
    def set_placeholder_icon(self, item: QListWidgetItem, clip: ClipInfo):
        """Create a placeholder icon."""
        pixmap = QPixmap(120, 80)
        pixmap.fill(QColor("#e9ecef"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.setPen(QColor("#495057"))
        ext = clip.extension.upper().replace(".", "")
        painter.drawText(pixmap.rect(), Qt.AlignCenter, ext)
        
        if clip.extension.lower() in ['.mp4', '.mov', '.mkv', '.avi']:
            painter.setPen(QPen(QColor("#4361ee"), 2))
            painter.drawRect(5, 5, 110, 70)
        
        painter.end()
        item.setIcon(QIcon(pixmap))

class ClipTableModel:
    """Model for managing clip data."""
    
    def __init__(self):
        self.clips: List[ClipInfo] = []
        self.custom_fields = set()
        self.templates: List[NamingTemplate] = self.load_default_templates()
    
    def load_default_templates(self) -> List[NamingTemplate]:
        """Load default naming templates."""
        return [
            NamingTemplate(
                "Film Standard",
                "{Scene}_{Take:03d}_{ShotType}_{Camera}",
                "Standard film naming: Scene_Take_ShotType_Camera"
            ),
            NamingTemplate(
                "YouTube Project",
                "{Project}_{Scene}_{Take:03d}_{Description}",
                "For YouTube/content creation projects"
            ),
            NamingTemplate(
                "Camera Roll",
                "{Date}_{Time}_{CameraSerial}_{Counter:04d}",
                "Organize by date and camera"
            ),
            NamingTemplate(
                "Scene-Based",
                "Scene_{Scene}_Take_{Take:03d}_{ShotType}",
                "Emphasize scene and take numbers"
            ),
            NamingTemplate(
                "Simple Counter",
                "{Project}_{Counter:04d}_{Description}",
                "Simple sequential numbering"
            )
        ]
    
    def add_clip(self, clip: ClipInfo):
        self.clips.append(clip)
    
    def remove_clip(self, index: int):
        if 0 <= index < len(self.clips):
            del self.clips[index]
    
    def get_clip(self, index: int) -> Optional[ClipInfo]:
        if 0 <= index < len(self.clips):
            return self.clips[index]
        return None
    
    def clear(self):
        self.clips.clear()
    
    def generate_new_name(self, clip: ClipInfo, template_str: str, 
                         project_name: str = "", counter: int = 1) -> str:
        """Generate new filename using template."""
        try:
            rec_date = clip.created_date
            
            values = {
                "Scene": clip.scene or "SCENE",
                "Take": clip.take or 1,
                "ShotType": clip.shot_type or "SHOT",
                "Camera": clip.camera_model or "CAM",
                "CameraSerial": (clip.camera_serial[-4:] if clip.camera_serial else "0000"),
                "Date": rec_date.strftime("%Y%m%d"),
                "Time": rec_date.strftime("%H%M%S"),
                "Project": project_name or "PROJECT",
                "Resolution": clip.resolution or "1920x1080",
                "FPS": clip.frame_rate or 30.0,
                "Duration": int(clip.duration) if clip.duration else 0,
                "OriginalName": clip.filename,
                "Counter": counter,
                "Description": clip.description or "",
                "Notes": clip.notes or ""
            }
            
            values.update(clip.custom_fields)
            new_name = template_str.format(**values)
            new_name = re.sub(r'[<>:"/\\|?*]', '_', new_name)
            new_name = re.sub(r'\s+', ' ', new_name).strip()
            
            return new_name
            
        except KeyError as e:
            return f"TemplateError_{clip.filename}"
        except Exception as e:
            return f"Error_{clip.filename}"
    
    def validate_template(self, template_str: str) -> Tuple[bool, str]:
        try:
            test_values = {field: "TEST" for field in NamingTemplate.AVAILABLE_FIELDS.keys()}
            test_values.update({"Take": 1, "Counter": 1, "FPS": 30.0, "Duration": 10})
            template_str.format(**test_values)
            return True, "Template is valid"
        except KeyError as e:
            return False, f"Unknown field: {e}"
        except ValueError as e:
            return False, f"Format error: {e}"
        except Exception as e:
            return False, f"Error: {str(e)}"

class SettingsManager:
    """Manages application settings."""
    
    def __init__(self):
        self.settings_file = SETTINGS_FILE
        self.presets_file = PRESETS_FILE
        self.default_settings = {
            "last_folder": str(Path.home()),
            "default_template": "Film Standard",
            "project_name": "MyProject",
            "auto_extract_metadata": True,
            "preview_before_rename": True,
            "create_backup": True,
            "window_geometry": None,
            "window_state": None,
            "custom_fields": [],
            "shot_types": ["WS", "MS", "CU", "ECU", "2S", "OTS", "DOLLY", "CRANE", "STATIC"]
        }
    
    def load(self) -> Dict:
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    settings = self.default_settings.copy()
                    settings.update(loaded)
                    return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return self.default_settings.copy()
    
    def save(self, settings: Dict):
        try:
            self.settings_file.parent.mkdir(exist_ok=True, parents=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def load_presets(self) -> List[NamingTemplate]:
        try:
            if self.presets_file.exists():
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [NamingTemplate(**item) for item in data]
        except Exception as e:
            print(f"Error loading presets: {e}")
        
        return []
    
    def save_presets(self, presets: List[NamingTemplate]):
        try:
            self.presets_file.parent.mkdir(exist_ok=True, parents=True)
            data = [asdict(preset) for preset in presets]
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving presets: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load()
        self.model = ClipTableModel()
        self.init_ui()
        self.metadata_thread = None
        self.metadata_worker = None
        self.thumbnail_thread = None
        self.thumbnail_worker = None
        
    def init_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.setMinimumSize(1200, 800)
        self.setAcceptDrops(True)
        
        self.set_application_icon()
        
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        self.create_library_tab()
        self.create_edit_tab()
        self.create_template_tab()
        self.create_batch_tab()
        
        self.create_toolbar()
        
        self.statusBar().showMessage("Ready")
        
        self.apply_saved_geometry()
    
    def set_application_icon(self):
        icon_paths = [
            "clipnamer.icns",
            "clipnamer.ico",
            "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericFolderIcon.icns"
        ]
        
        for path in icon_paths:
            if os.path.exists(path):
                self.setWindowIcon(QIcon(path))
                return
        
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#4361ee"))
        self.setWindowIcon(QIcon(pixmap))
    
    def create_library_tab(self):
        library_tab = QWidget()
        main_layout = QVBoxLayout(library_tab)
        
        header = QLabel("📁 Video Library")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #4361ee; padding: 10px;")
        main_layout.addWidget(header)
        
        splitter = QSplitter(Qt.Horizontal)
        
        browser_panel = QWidget()
        browser_layout = QVBoxLayout(browser_panel)
        
        file_ops_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("📄 Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        file_ops_layout.addWidget(self.add_files_btn)
        
        self.add_folder_btn = QPushButton("📁 Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        file_ops_layout.addWidget(self.add_folder_btn)
        
        self.clear_btn = QPushButton("🗑️ Clear All")
        self.clear_btn.clicked.connect(self.clear_files)
        file_ops_layout.addWidget(self.clear_btn)
        
        browser_layout.addLayout(file_ops_layout)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Search:"))
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by filename, scene, description...")
        self.search_edit.textChanged.connect(self.filter_clips)
        search_layout.addWidget(self.search_edit)
        
        browser_layout.addLayout(search_layout)
        
        self.clip_list_widget = ClipListWidget()
        self.clip_list_widget.itemClicked.connect(self.on_clip_selected_library)
        self.clip_list_widget.itemDoubleClicked.connect(self.on_clip_double_clicked)
        browser_layout.addWidget(self.clip_list_widget)
        
        quick_actions = QHBoxLayout()
        
        self.generate_thumbs_btn = QPushButton("🖼️ Generate Thumbnails")
        self.generate_thumbs_btn.clicked.connect(self.generate_all_thumbnails)
        quick_actions.addWidget(self.generate_thumbs_btn)
        
        self.refresh_thumbs_btn = QPushButton("🔄 Refresh All")
        self.refresh_thumbs_btn.clicked.connect(self.refresh_all_thumbnails)
        quick_actions.addWidget(self.refresh_thumbs_btn)
        
        browser_layout.addLayout(quick_actions)
        
        splitter.addWidget(browser_panel)
        
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        
        self.video_preview = VideoPreviewWidget()
        preview_layout.addWidget(self.video_preview, 3)
        
        info_group = QGroupBox("Clip Information")
        info_layout = QFormLayout()
        
        self.preview_scene_label = QLabel("-")
        info_layout.addRow("Scene:", self.preview_scene_label)
        
        self.preview_take_label = QLabel("-")
        info_layout.addRow("Take:", self.preview_take_label)
        
        self.preview_shot_label = QLabel("-")
        info_layout.addRow("Shot Type:", self.preview_shot_label)
        
        self.preview_desc_label = QLabel("-")
        info_layout.addRow("Description:", self.preview_desc_label)
        
        self.preview_camera_label = QLabel("-")
        info_layout.addRow("Camera:", self.preview_camera_label)
        
        self.preview_res_label = QLabel("-")
        info_layout.addRow("Resolution:", self.preview_res_label)
        
        self.quick_edit_btn = QPushButton("✏️ Quick Edit")
        self.quick_edit_btn.clicked.connect(self.quick_edit_clip)
        info_layout.addRow(self.quick_edit_btn)
        
        info_group.setLayout(info_layout)
        preview_layout.addWidget(info_group, 1)
        
        splitter.addWidget(preview_panel)
        
        splitter.setSizes([400, 800])
        
        main_layout.addWidget(splitter)
        
        self.tab_widget.addTab(library_tab, "Library")
        
        self.metadata_checkbox = QCheckBox("Extract metadata automatically")
        self.metadata_checkbox.setChecked(self.settings.get("auto_extract_metadata", True))
        browser_layout.addWidget(self.metadata_checkbox)
    
    def create_edit_tab(self):
        edit_tab = QWidget()
        layout = QVBoxLayout(edit_tab)
        
        header = QLabel("✏️ Edit Clip Details")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #4361ee; padding: 10px;")
        layout.addWidget(header)
        
        splitter = QSplitter(Qt.Horizontal)
        
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        
        self.edit_clip_table = QTableWidget()
        self.edit_clip_table.setColumnCount(6)
        self.edit_clip_table.setHorizontalHeaderLabels(["Thumb", "Filename", "Scene", "Take", "Shot", "Duration"])
        self.edit_clip_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.edit_clip_table.setColumnWidth(0, 60)
        self.edit_clip_table.setColumnWidth(2, 80)
        self.edit_clip_table.setColumnWidth(3, 60)
        self.edit_clip_table.setColumnWidth(4, 80)
        self.edit_clip_table.setColumnWidth(5, 80)
        self.edit_clip_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.edit_clip_table.itemSelectionChanged.connect(self.on_edit_clip_selected)
        
        list_layout.addWidget(self.edit_clip_table)
        
        splitter.addWidget(list_widget)
        
        editor_widget = QWidget()
        editor_layout = QFormLayout(editor_widget)
        editor_layout.setSpacing(10)
        
        editor_layout.addRow(QLabel("<b>Basic Information</b>"))
        
        self.scene_edit = QLineEdit()
        self.scene_edit.setPlaceholderText("e.g., 001A, INT, EXT")
        editor_layout.addRow("Scene:", self.scene_edit)
        
        self.take_spin = QSpinBox()
        self.take_spin.setRange(1, 999)
        self.take_spin.setValue(1)
        editor_layout.addRow("Take:", self.take_spin)
        
        self.shot_combo = QComboBox()
        self.shot_combo.addItems(self.settings.get("shot_types", ["WS", "MS", "CU", "ECU"]))
        self.shot_combo.setEditable(True)
        editor_layout.addRow("Shot Type:", self.shot_combo)
        
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Brief description of the clip")
        editor_layout.addRow("Description:", self.desc_edit)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlaceholderText("Additional notes...")
        editor_layout.addRow("Notes:", self.notes_edit)
        
        editor_layout.addRow(QLabel("<b>Metadata</b>"))
        
        self.metadata_display = QTextEdit()
        self.metadata_display.setMaximumHeight(150)
        self.metadata_display.setReadOnly(True)
        editor_layout.addRow("File Info:", self.metadata_display)
        
        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self.save_clip_changes)
        self.save_btn.setEnabled(False)
        editor_layout.addRow(self.save_btn)
        
        splitter.addWidget(editor_widget)
        
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        
        self.tab_widget.addTab(edit_tab, "Edit")
    
    def create_template_tab(self):
        template_tab = QWidget()
        layout = QVBoxLayout(template_tab)
        
        header = QLabel("🎯 Naming Template")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #4361ee; padding: 10px;")
        layout.addWidget(header)
        
        project_layout = QHBoxLayout()
        project_layout.addWidget(QLabel("Project Name:"))
        
        self.project_edit = QLineEdit()
        self.project_edit.setText(self.settings.get("project_name", "MyProject"))
        self.project_edit.textChanged.connect(self.update_preview)
        project_layout.addWidget(self.project_edit)
        
        layout.addLayout(project_layout)
        
        template_group = QGroupBox("Select Template")
        template_layout = QVBoxLayout()
        
        self.template_combo = QComboBox()
        self.populate_template_combo()
        self.template_combo.currentIndexChanged.connect(self.update_preview)
        template_layout.addWidget(self.template_combo)
        
        edit_template_btn = QPushButton("✏️ Edit Templates...")
        edit_template_btn.clicked.connect(self.edit_templates)
        template_layout.addWidget(edit_template_btn)
        
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)
        
        custom_group = QGroupBox("Custom Template")
        custom_layout = QVBoxLayout()
        
        self.custom_template_edit = QLineEdit()
        self.custom_template_edit.setText("{Scene}_{Take:03d}_{ShotType}")
        self.custom_template_edit.textChanged.connect(self.update_preview)
        custom_layout.addWidget(self.custom_template_edit)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_list = QListWidget()
        preview_layout.addWidget(self.preview_list)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        options_group = QGroupBox("Options")
        options_layout = QGridLayout()
        
        self.preview_checkbox = QCheckBox("Preview before renaming")
        self.preview_checkbox.setChecked(self.settings.get("preview_before_rename", True))
        options_layout.addWidget(self.preview_checkbox, 0, 0)
        
        self.backup_checkbox = QCheckBox("Create backup before renaming")
        self.backup_checkbox.setChecked(self.settings.get("create_backup", True))
        options_layout.addWidget(self.backup_checkbox, 0, 1)
        
        self.sequential_checkbox = QCheckBox("Use sequential numbering")
        self.sequential_checkbox.setChecked(True)
        options_layout.addWidget(self.sequential_checkbox, 1, 0)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        self.tab_widget.addTab(template_tab, "Template")
    
    def create_batch_tab(self):
        batch_tab = QWidget()
        layout = QVBoxLayout(batch_tab)
        
        header = QLabel("🚀 Batch Rename")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #4361ee; padding: 10px;")
        layout.addWidget(header)
        
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()
        
        self.summary_label = QLabel("No clips loaded")
        summary_layout.addWidget(self.summary_label)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        table_group = QGroupBox("Rename Preview")
        table_layout = QVBoxLayout()
        
        self.rename_table = QTableWidget()
        self.rename_table.setColumnCount(3)
        self.rename_table.setHorizontalHeaderLabels(["Current", "→", "New Name"])
        self.rename_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.rename_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.rename_table.setColumnWidth(1, 30)
        
        table_layout.addWidget(self.rename_table)
        
        update_btn = QPushButton("🔄 Update Preview")
        update_btn.clicked.connect(self.update_rename_preview)
        table_layout.addWidget(update_btn)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        action_layout = QHBoxLayout()
        
        self.export_log_btn = QPushButton("📋 Export Rename Log")
        self.export_log_btn.clicked.connect(self.export_rename_log)
        self.export_log_btn.setEnabled(False)
        action_layout.addWidget(self.export_log_btn)
        
        self.rename_btn = QPushButton("✅ Execute Rename")
        self.rename_btn.clicked.connect(self.execute_rename)
        self.rename_btn.setMinimumHeight(50)
        self.rename_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        action_layout.addWidget(self.rename_btn)
        
        layout.addLayout(action_layout)
        
        self.tab_widget.addTab(batch_tab, "Rename")
    
    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        add_files_action = QAction("📄 Add Files", self)
        add_files_action.triggered.connect(self.add_files)
        toolbar.addAction(add_files_action)
        
        toolbar.addSeparator()
        
        thumbs_action = QAction("🖼️ Generate Thumbs", self)
        thumbs_action.triggered.connect(self.generate_all_thumbnails)
        toolbar.addAction(thumbs_action)
        
        play_action = QAction("▶ Play Selected", self)
        play_action.triggered.connect(self.play_selected_clip)
        toolbar.addAction(play_action)
        
        toolbar.addSeparator()
        
        rename_action = QAction("🚀 Go to Rename", self)
        rename_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(3))
        toolbar.addAction(rename_action)
    
    def apply_saved_geometry(self):
        if self.settings.get("window_geometry"):
            try:
                self.restoreGeometry(
                    QByteArray.fromHex(
                        self.settings["window_geometry"].encode()
                    )
                )
            except:
                pass
        
        if self.settings.get("window_state"):
            try:
                self.restoreState(
                    QByteArray.fromHex(
                        self.settings["window_state"].encode()
                    )
                )
            except:
                pass
    
    def populate_template_combo(self):
        self.template_combo.clear()
        for template in self.model.templates:
            self.template_combo.addItem(template.name, template.template)
        
        self.template_combo.addItem("Custom...", "")
        
        default = self.settings.get("default_template", "Film Standard")
        index = self.template_combo.findText(default)
        if index >= 0:
            self.template_combo.setCurrentIndex(index)
    
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files",
            self.settings.get("last_folder", str(Path.home())),
            "Video Files (*.mp4 *.mov *.mkv *.mxf *.avi *.wmv *.flv *.webm *.mts *.m2ts)"
        )
        
        if files:
            self.settings["last_folder"] = str(Path(files[0]).parent)
            self.process_files(files)
    
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder",
            self.settings.get("last_folder", str(Path.home()))
        )
        
        if folder:
            self.settings["last_folder"] = folder
            self.settings_manager.save(self.settings)
            
            files = []
            for ext in SUPPORTED_FORMATS:
                files.extend(Path(folder).glob(f"*{ext}"))
                files.extend(Path(folder).glob(f"*{ext.upper()}"))
            
            self.process_files([str(f) for f in files])
    
    def process_files(self, file_paths: List[str]):
        added_count = 0
        
        for file_path in file_paths:
            path = Path(file_path)
            
            if any(clip.original_path == path for clip in self.model.clips):
                continue
            
            if path.suffix.lower() not in SUPPORTED_FORMATS:
                continue
            
            try:
                stat = path.stat()
                clip = ClipInfo(
                    original_path=path,
                    filename=path.name,
                    extension=path.suffix.lower(),
                    size=stat.st_size,
                    created_date=datetime.fromtimestamp(stat.st_ctime),
                    modified_date=datetime.fromtimestamp(stat.st_mtime)
                )
                
                self.model.add_clip(clip)
                added_count += 1
                
                self.clip_list_widget.add_clip_item(clip, len(self.model.clips) - 1)
                
                row = self.edit_clip_table.rowCount()
                self.edit_clip_table.insertRow(row)
                
                # Add thumbnail to edit table
                thumbnail_item = QTableWidgetItem()
                thumbnail = clip.get_thumbnail()
                if thumbnail and thumbnail.exists():
                    pixmap = QPixmap(str(thumbnail))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(50, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        thumbnail_item.setIcon(QIcon(pixmap))
                self.edit_clip_table.setItem(row, 0, thumbnail_item)
                
                # Add other columns
                self.edit_clip_table.setItem(row, 1, QTableWidgetItem(clip.filename))
                self.edit_clip_table.setItem(row, 2, QTableWidgetItem(clip.scene))
                self.edit_clip_table.setItem(row, 3, QTableWidgetItem(str(clip.take) if clip.take > 0 else ""))
                self.edit_clip_table.setItem(row, 4, QTableWidgetItem(clip.shot_type))
                
                duration_text = ""
                if clip.duration > 0:
                    mins = int(clip.duration // 60)
                    secs = int(clip.duration % 60)
                    duration_text = f"{mins}:{secs:02d}"
                self.edit_clip_table.setItem(row, 5, QTableWidgetItem(duration_text))
                
            except Exception as e:
                self.statusBar().showMessage(f"Error adding {path.name}: {str(e)}", 3000)
        
        if added_count > 0:
            self.statusBar().showMessage(f"Added {added_count} files", 3000)
            
            if self.metadata_checkbox.isChecked() and added_count <= 50:
                self.extract_metadata()
            
            self.update_summary()
    
    def extract_metadata(self):
        if not self.model.clips:
            return
        
        self.statusBar().showMessage("Extracting metadata...", 3000)
        
        self.metadata_thread = QThread()
        self.metadata_worker = MetadataExtractor([clip.original_path for clip in self.model.clips])
        self.metadata_worker.moveToThread(self.metadata_thread)
        
        self.metadata_thread.started.connect(self.metadata_worker.run)
        self.metadata_worker.metadata_extracted.connect(self.on_metadata_extracted)
        self.metadata_worker.finished.connect(self.metadata_thread.quit)
        self.metadata_worker.finished.connect(self.metadata_worker.deleteLater)
        self.metadata_thread.finished.connect(self.metadata_thread.deleteLater)
        
        self.metadata_thread.start()
    
    def on_metadata_extracted(self, file_path: Path, metadata: Dict):
        for i, clip in enumerate(self.model.clips):
            if clip.original_path == file_path:
                clip.camera_model = metadata.get("camera_model", "")
                clip.camera_serial = metadata.get("camera_serial", "")
                clip.resolution = metadata.get("resolution", "")
                clip.frame_rate = metadata.get("frame_rate", 0.0)
                clip.duration = metadata.get("duration", 0.0)
                
                # Update edit table
                if clip.duration > 0:
                    mins = int(clip.duration // 60)
                    secs = int(clip.duration % 60)
                    duration_text = f"{mins}:{secs:02d}"
                    self.edit_clip_table.setItem(i, 5, QTableWidgetItem(duration_text))
                
                break
    
    def clear_files(self):
        if self.model.clips:
            reply = QMessageBox.question(
                self, "Clear All",
                "Are you sure you want to remove all clips?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.model.clear()
                self.clip_list_widget.clear()
                self.edit_clip_table.setRowCount(0)
                self.preview_list.clear()
                self.rename_table.setRowCount(0)
                self.summary_label.setText("No clips loaded")
                self.video_preview.stop()
                self.statusBar().showMessage("Cleared all clips", 3000)
    
    def on_clip_selected_library(self, item):
        index = item.data(Qt.UserRole)
        clip = self.model.get_clip(index)
        
        if clip:
            self.video_preview.load_clip(clip)
            
            self.preview_scene_label.setText(clip.scene if clip.scene else "-")
            self.preview_take_label.setText(str(clip.take) if clip.take > 0 else "-")
            self.preview_shot_label.setText(clip.shot_type if clip.shot_type else "-")
            self.preview_desc_label.setText(clip.description if clip.description else "-")
            self.preview_camera_label.setText(clip.camera_model if clip.camera_model else "-")
            self.preview_res_label.setText(clip.resolution if clip.resolution else "-")
            
            self.quick_edit_btn.setEnabled(True)
    
    def on_clip_double_clicked(self, item):
        index = item.data(Qt.UserRole)
        clip = self.model.get_clip(index)
        
        if clip and self.video_preview.current_clip == clip:
            self.video_preview.toggle_playback()
    
    def play_selected_clip(self):
        items = self.clip_list_widget.selectedItems()
        if items:
            self.on_clip_selected_library(items[0])
            self.video_preview.media_player.play()
    
    def generate_all_thumbnails(self):
        if not self.model.clips:
            QMessageBox.information(self, "No Clips", "Please add clips first.")
            return
        
        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailGenerator(self.model.clips)
        self.thumbnail_worker.moveToThread(self.thumbnail_thread)
        
        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_worker.thumbnail_generated.connect(self.on_thumbnail_generated)
        self.thumbnail_worker.progress.connect(self.on_thumbnail_progress)
        self.thumbnail_worker.finished.connect(self.thumbnail_thread.quit)
        self.thumbnail_worker.finished.connect(self.thumbnail_worker.deleteLater)
        self.thumbnail_thread.finished.connect(self.thumbnail_thread.deleteLater)
        self.thumbnail_thread.finished.connect(self.on_thumbnails_finished)
        
        self.generate_thumbs_btn.setEnabled(False)
        self.generate_thumbs_btn.setText("⏳ Generating...")
        
        self.thumbnail_thread.start()
    
    def on_thumbnail_generated(self, clip_path: Path, thumbnail_path: Path):
        for i, clip in enumerate(self.model.clips):
            if clip.original_path == clip_path:
                clip.thumbnail_path = thumbnail_path
                
                # Update library view
                for j in range(self.clip_list_widget.count()):
                    item = self.clip_list_widget.item(j)
                    if item.data(Qt.UserRole) == i:
                        pixmap = QPixmap(str(thumbnail_path))
                        if not pixmap.isNull():
                            if pixmap.width() > 120 or pixmap.height() > 80:
                                pixmap = pixmap.scaled(120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            item.setIcon(QIcon(pixmap))
                        break
                
                # Update edit table
                if i < self.edit_clip_table.rowCount():
                    pixmap = QPixmap(str(thumbnail_path))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(50, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.edit_clip_table.item(i, 0).setIcon(QIcon(pixmap))
                
                break
    
    def on_thumbnail_progress(self, current: int, total: int):
        self.statusBar().showMessage(f"Generating thumbnails: {current}/{total}", 1000)
    
    def on_thumbnails_finished(self):
        self.generate_thumbs_btn.setEnabled(True)
        self.generate_thumbs_btn.setText("🖼️ Generate Thumbnails")
        self.statusBar().showMessage(f"Generated thumbnails for {len(self.model.clips)} clips", 3000)
    
    def refresh_all_thumbnails(self):
        if not self.model.clips:
            return
        
        for clip in self.model.clips:
            clip.thumbnail_path = None
        
        self.clip_list_widget.clear()
        for i, clip in enumerate(self.model.clips):
            self.clip_list_widget.add_clip_item(clip, i)
        
        self.generate_all_thumbnails()
    
    def filter_clips(self, search_text: str):
        search_text = search_text.lower()
        
        for i in range(self.clip_list_widget.count()):
            item = self.clip_list_widget.item(i)
            clip = self.model.get_clip(item.data(Qt.UserRole))
            
            if not clip:
                item.setHidden(True)
                continue
            
            matches = (
                search_text in clip.filename.lower() or
                search_text in (clip.scene or "").lower() or
                search_text in (clip.description or "").lower() or
                search_text in (clip.shot_type or "").lower() or
                search_text in (clip.camera_model or "").lower()
            )
            
            item.setHidden(not matches)
    
    def quick_edit_clip(self):
        items = self.clip_list_widget.selectedItems()
        if items:
            self.tab_widget.setCurrentIndex(1)
            index = items[0].data(Qt.UserRole)
            self.edit_clip_table.selectRow(index)
            self.edit_clip_table.scrollToItem(
                self.edit_clip_table.item(index, 0),
                QAbstractItemView.PositionAtTop
            )
    
    def on_edit_clip_selected(self):
        selected = self.edit_clip_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        clip = self.model.get_clip(row)
        
        if clip:
            self.scene_edit.setText(clip.scene)
            self.take_spin.setValue(clip.take if clip.take > 0 else 1)
            
            shot_index = self.shot_combo.findText(clip.shot_type)
            if shot_index >= 0:
                self.shot_combo.setCurrentIndex(shot_index)
            elif clip.shot_type:
                self.shot_combo.setCurrentText(clip.shot_type)
            
            self.desc_edit.setText(clip.description)
            self.notes_edit.setPlainText(clip.notes)
            
            lines = []
            lines.append(f"File: {clip.filename}")
            lines.append(f"Size: {clip.size // 1024 // 1024} MB")
            lines.append(f"Created: {clip.created_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if clip.resolution:
                lines.append(f"Resolution: {clip.resolution}")
            if clip.frame_rate > 0:
                lines.append(f"Frame Rate: {clip.frame_rate} fps")
            if clip.duration > 0:
                lines.append(f"Duration: {int(clip.duration // 60)}:{int(clip.duration % 60):02d}")
            if clip.camera_model:
                lines.append(f"Camera: {clip.camera_model}")
            if clip.camera_serial:
                lines.append(f"Serial: {clip.camera_serial}")
            
            self.metadata_display.setPlainText("\n".join(lines))
            
            self.save_btn.setEnabled(True)
    
    def save_clip_changes(self):
        selected = self.edit_clip_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        clip = self.model.get_clip(row)
        
        if clip:
            clip.scene = self.scene_edit.text()
            clip.take = self.take_spin.value()
            clip.shot_type = self.shot_combo.currentText()
            clip.description = self.desc_edit.text()
            clip.notes = self.notes_edit.toPlainText()
            
            # Update edit table
            self.edit_clip_table.setItem(row, 2, QTableWidgetItem(clip.scene))
            self.edit_clip_table.setItem(row, 3, QTableWidgetItem(str(clip.take) if clip.take > 0 else ""))
            self.edit_clip_table.setItem(row, 4, QTableWidgetItem(clip.shot_type))
            
            # Update library view
            for i in range(self.clip_list_widget.count()):
                item = self.clip_list_widget.item(i)
                if item.data(Qt.UserRole) == row:
                    display_text = clip.filename
                    if clip.scene:
                        display_text = f"{clip.scene}_{clip.take:03d}" if clip.take > 0 else clip.scene
                    item.setText(display_text)
                    
                    tooltip = f"File: {clip.filename}"
                    if clip.scene:
                        tooltip += f"\nScene: {clip.scene}"
                    if clip.take > 0:
                        tooltip += f"\nTake: {clip.take}"
                    if clip.shot_type:
                        tooltip += f"\nShot: {clip.shot_type}"
                    if clip.duration > 0:
                        mins = int(clip.duration // 60)
                        secs = int(clip.duration % 60)
                        tooltip += f"\nDuration: {mins}:{secs:02d}"
                    item.setToolTip(tooltip)
                    break
            
            self.statusBar().showMessage(f"Saved changes to {clip.filename}", 3000)
            self.update_preview()
    
    def edit_templates(self):
        # Simple template editor
        from PyQt5.QtWidgets import QInputDialog
        
        templates_text = "\n\n".join([f"{t.name}: {t.template}\n{t.description}" for t in self.model.templates])
        
        new_templates, ok = QInputDialog.getMultiLineText(
            self, "Edit Templates",
            "Enter templates (one per line, format: Name|Template|Description):",
            "\n".join([f"{t.name}|{t.template}|{t.description}" for t in self.model.templates])
        )
        
        if ok and new_templates:
            self.model.templates = []
            for line in new_templates.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split('|', 2)
                    if len(parts) >= 2:
                        name = parts[0]
                        template = parts[1]
                        description = parts[2] if len(parts) > 2 else ""
                        self.model.templates.append(NamingTemplate(name, template, description))
            
            self.populate_template_combo()
            self.update_preview()
            self.settings_manager.save_presets(self.model.templates)
    
    def update_preview(self):
        if not self.model.clips:
            self.preview_list.clear()
            return
        
        if self.template_combo.currentText() == "Custom...":
            template_str = self.custom_template_edit.text()
        else:
            template_str = self.template_combo.currentData()
        
        project_name = self.project_edit.text()
        
        self.preview_list.clear()
        
        for i, clip in enumerate(self.model.clips):
            new_name = self.model.generate_new_name(
                clip, 
                template_str,
                project_name,
                i + 1
            )
            
            new_name_full = f"{new_name}{clip.extension}"
            item = QListWidgetItem(f"{clip.filename} → {new_name_full}")
            self.preview_list.addItem(item)
    
    def update_summary(self):
        count = len(self.model.clips)
        
        scenes = defaultdict(int)
        for clip in self.model.clips:
            if clip.scene:
                scenes[clip.scene] += 1
        
        summary_text = f"Total Clips: {count}\n"
        if scenes:
            summary_text += "Scenes:\n"
            for scene, scene_count in sorted(scenes.items()):
                summary_text += f"  {scene}: {scene_count} clips\n"
        
        self.summary_label.setText(summary_text)
    
    def update_rename_preview(self):
        if not self.model.clips:
            self.rename_table.setRowCount(0)
            return
        
        if self.template_combo.currentText() == "Custom...":
            template_str = self.custom_template_edit.text()
        else:
            template_str = self.template_combo.currentData()
        
        is_valid, message = self.model.validate_template(template_str)
        if not is_valid:
            QMessageBox.warning(self, "Template Error", message)
            return
        
        project_name = self.project_edit.text()
        
        self.rename_table.setRowCount(len(self.model.clips))
        
        for i, clip in enumerate(self.model.clips):
            counter = i + 1 if self.sequential_checkbox.isChecked() else 1
            new_name = self.model.generate_new_name(
                clip,
                template_str,
                project_name,
                counter
            )
            
            new_name_full = f"{new_name}{clip.extension}"
            
            orig_item = QTableWidgetItem(clip.filename)
            self.rename_table.setItem(i, 0, orig_item)
            
            arrow_item = QTableWidgetItem("→")
            arrow_item.setTextAlignment(Qt.AlignCenter)
            self.rename_table.setItem(i, 1, arrow_item)
            
            new_item = QTableWidgetItem(new_name_full)
            self.rename_table.setItem(i, 2, new_item)
        
        self.export_log_btn.setEnabled(True)
        self.statusBar().showMessage(f"Preview updated for {len(self.model.clips)} clips", 3000)
    
    def export_rename_log(self):
        if not self.model.clips:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Rename Log",
            str(Path.home() / f"clipnamer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"),
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            data = []
            for clip in self.model.clips:
                template_str = self.template_combo.currentData() if self.template_combo.currentText() != "Custom..." else self.custom_template_edit.text()
                new_name = self.model.generate_new_name(clip, template_str, self.project_edit.text(), 1)
                
                data.append({
                    "original_path": str(clip.original_path),
                    "original_name": clip.filename,
                    "new_name": f"{new_name}{clip.extension}",
                    "scene": clip.scene,
                    "take": clip.take,
                    "shot_type": clip.shot_type,
                    "description": clip.description,
                    "camera": clip.camera_model,
                    "resolution": clip.resolution,
                    "frame_rate": clip.frame_rate,
                    "timestamp": datetime.now().isoformat()
                })
            
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                import csv
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
            
            self.statusBar().showMessage(f"Log exported to {file_path}", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting log: {str(e)}")
    
    def execute_rename(self):
        if not self.model.clips:
            QMessageBox.warning(self, "No Clips", "Please add clips first.")
            return
        
        rename_list = []
        for i, clip in enumerate(self.model.clips):
            template_str = self.template_combo.currentData() if self.template_combo.currentText() != "Custom..." else self.custom_template_edit.text()
            counter = i + 1 if self.sequential_checkbox.isChecked() else 1
            new_name = self.model.generate_new_name(
                clip,
                template_str,
                self.project_edit.text(),
                counter
            )
            
            new_name_full = f"{new_name}{clip.extension}"
            rename_list.append((clip.original_path, new_name_full))
        
        if self.preview_checkbox.isChecked():
            # Simple preview dialog
            preview_text = "\n".join([f"{old.name} → {new}" for old, new in rename_list[:20]])
            if len(rename_list) > 20:
                preview_text += f"\n... and {len(rename_list) - 20} more files"
            
            reply = QMessageBox.question(
                self, "Preview Rename",
                f"Preview of first 20 files:\n\n{preview_text}\n\nContinue with rename?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
        
        success_count = 0
        error_count = 0
        rename_log = []
        
        for old_path, new_name in rename_list:
            try:
                if self.backup_checkbox.isChecked():
                    backup_path = old_path.parent / f"backup_{old_path.name}"
                    shutil.copy2(old_path, backup_path)
                
                new_path = old_path.parent / new_name
                old_path.rename(new_path)
                
                rename_log.append({
                    "original": str(old_path),
                    "renamed": str(new_path),
                    "timestamp": datetime.now().isoformat(),
                    "success": True
                })
                
                success_count += 1
                
            except Exception as e:
                rename_log.append({
                    "original": str(old_path),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "success": False
                })
                error_count += 1
        
        try:
            log_file = Path.home() / f"clipnamer_rename_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(rename_log, f, indent=2, ensure_ascii=False)
        except:
            pass
        
        msg = f"Rename complete!\n\nSuccess: {success_count}\nErrors: {error_count}"
        if error_count == 0:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.warning(self, "Complete with Errors", msg)
        
        self.statusBar().showMessage(f"Renamed {success_count} files", 5000)
        
        if success_count > 0:
            self.model.clear()
            self.clip_list_widget.clear()
            self.edit_clip_table.setRowCount(0)
            self.preview_list.clear()
            self.rename_table.setRowCount(0)
            self.summary_label.setText("No clips loaded")
            self.video_preview.stop()
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = []
        folders = []
        
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                folders.append(path)
        
        for folder in folders:
            for ext in SUPPORTED_FORMATS:
                for file_path in Path(folder).glob(f"**/*{ext}"):
                    files.append(str(file_path))
                for file_path in Path(folder).glob(f"**/*{ext.upper()}"):
                    files.append(str(file_path))
        
        if files:
            self.process_files(files)
            event.acceptProposedAction()
    
    def closeEvent(self, event):
        self.settings.update({
            "last_folder": self.settings.get("last_folder", str(Path.home())),
            "default_template": self.template_combo.currentText(),
            "project_name": self.project_edit.text(),
            "auto_extract_metadata": self.metadata_checkbox.isChecked(),
            "preview_before_rename": self.preview_checkbox.isChecked(),
            "create_backup": self.backup_checkbox.isChecked(),
            "window_geometry": self.saveGeometry().toHex().data().decode(),
            "window_state": self.saveState().toHex().data().decode()
        })
        
        self.settings_manager.save(self.settings)
        
        if self.metadata_thread and self.metadata_thread.isRunning():
            self.metadata_worker.running = False
            self.metadata_thread.quit()
            self.metadata_thread.wait(1000)
        
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_worker.running = False
            self.thumbnail_thread.quit()
            self.thumbnail_thread.wait(1000)
        
        self.video_preview.media_player.stop()
        
        event.accept()

def check_dependencies():
    try:
        result = subprocess.run(["ffprobe", "-version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            return False, "ffprobe failed to run"
        return True, "OK"
    except FileNotFoundError:
        return False, "ffprobe not found in PATH"

def main():
    has_ffprobe, message = check_dependencies()
    if not has_ffprobe:
        print("Warning: FFmpeg/ffprobe not found.")
        print("ClipNamer will work, but metadata extraction and thumbnails will be limited.")
        print("Install FFmpeg for full functionality:")
        print("  macOS:    brew install ffmpeg")
        print("  Ubuntu:   sudo apt install ffmpeg")
        print("  Windows:  Download from https://ffmpeg.org/")
        print("\nPress Enter to continue...")
        try:
            input()
        except:
            pass
    
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    
    app.setStyle("Fusion")
    
    font = QFont("Arial", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()