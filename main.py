import sys
import os
import tempfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QFileDialog, QTextEdit,
                            QProgressBar, QLabel, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QColor, QPen, QFont
from PIL import Image, ImageOps, ImageEnhance
import pdf2image
import img2pdf

class ImageProcessor:
    """Handles intelligent duotone image processing with 100% layout preservation."""
    NAVY_BLUE = "#000080"
    MAGENTA = "#D1006E"
    WHITE = "#FFFFFF"
    
    @staticmethod
    def get_theme_colors(theme: str):
        if theme == "magenta":
            return ImageProcessor.MAGENTA, ImageProcessor.WHITE
        return ImageProcessor.NAVY_BLUE, ImageProcessor.WHITE

    @staticmethod
    def apply_duotone(img: Image.Image, theme: str) -> Image.Image:
        """Applies duotone mapping to a PIL Image object."""
        dark_color, light_color = ImageProcessor.get_theme_colors(theme)
        gray_img = img.convert("L")
        duotone_img = ImageOps.colorize(gray_img, black=dark_color, white=light_color)
        enhancer = ImageEnhance.Contrast(duotone_img)
        return enhancer.enhance(1.15)

    @staticmethod
    def process_image(image_path: str, output_path: str, theme: str = "blue") -> bool:
        try:
            img = Image.open(image_path).convert("RGB")
            duotone_img = ImageProcessor.apply_duotone(img, theme)
            duotone_img.save(output_path, optimize=True)
            return True
        except Exception as e:
            print(f"Image processing error: {e}")
            return False

class DocumentProcessor:
    """Routes and processes different document formats without destructive OCR."""
    @staticmethod
    def process_file(input_path: str, output_dir: str, log_callback, theme: str = "blue") -> bool:
        path = Path(input_path)
        ext = path.suffix.lower()
        theme_suffix = "bluewhite" if theme == "blue" else "magentawhite"
        output_name = path.stem + f"_{theme_suffix}" + ext

        if ext in ['.png', '.jpg', '.jpeg', '.tiff', '.tif']:
            out_path = os.path.join(output_dir, output_name)
            return ImageProcessor.process_image(input_path, out_path, theme)

        if ext == '.docx':
            try:
                from docx2pdf import convert
                temp_pdf = os.path.join(tempfile.gettempdir(), path.stem + "_temp.pdf")
                log_callback("Converting DOCX to PDF for layout preservation...")
                convert(input_path, temp_pdf)
                input_path = temp_pdf
                ext = '.pdf'
                output_name = path.stem + f"_{theme_suffix}.pdf"
            except Exception as e:
                log_callback(f"DOCX conversion failed (Is MS Word installed?): {e}")
                return False

        if ext == '.pdf':
            try:
                log_callback("Rendering PDF pages to high-resolution images (300 DPI)...")
                images = pdf2image.convert_from_path(input_path, dpi=300)
                temp_img_dir = tempfile.mkdtemp()
                processed_imgs = []

                for i, img in enumerate(images):
                    log_callback(f"Processing page {i+1}/{len(images)}...")
                    duotone_img = ImageProcessor.apply_duotone(img, theme)
                    out_img_path = os.path.join(temp_img_dir, f"processed_{i}.png")
                    duotone_img.save(out_img_path, "PNG", optimize=True)
                    processed_imgs.append(out_img_path)

                log_callback(f"Recompiling into {theme.title()} & White PDF...")
                final_pdf_path = os.path.join(output_dir, output_name)
                with open(final_pdf_path, "wb") as f:
                    f.write(img2pdf.convert(processed_imgs))
                
                shutil.rmtree(temp_img_dir)
                if path.stem + "_temp.pdf" == os.path.basename(input_path):
                    os.remove(input_path)
                return True
            except Exception as e:
                log_callback(f"PDF processing error: {e}")
                return False
        
        log_callback(f"Unsupported file format: {ext}")
        return False

class WorkerThread(QThread):
    """Background thread to keep GUI responsive during heavy processing."""
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    
    def __init__(self, file_paths, output_dir, theme="blue"):
        super().__init__()
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.theme = theme

    def run(self):
        total = len(self.file_paths)
        success_count = 0
        
        for i, file_path in enumerate(self.file_paths):
            self.log.emit(f"Starting: {Path(file_path).name}")
            
            def nested_log(msg):
                self.log.emit(f"  -> {msg}")
                
            if DocumentProcessor.process_file(file_path, self.output_dir, nested_log, self.theme):
                success_count += 1
                self.log.emit(f"✅ Success: {Path(file_path).name}")
            else:
                self.log.emit(f"❌ Failed: {Path(file_path).name}")
                
            progress_pct = int(((i + 1) / total) * 100)
            self.progress.emit(progress_pct)
        
        self.finished.emit(success_count == total)

class DropZoneWidget(QFrame):
    """Custom widget that accepts drag-and-drop events."""
    files_dropped = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        self.setStyleSheet("""
            QFrame {
                border: 3px dashed #444;
                border-radius: 20px;
                background-color: #1a1a1a;
            }
            QFrame:hover {
                background-color: #252525;
                border-color: #666;
            }
        """)
        
        layout = QVBoxLayout(self)
        label = QLabel("UPLOAD FILES")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            color: #fff; 
            font-size: 28px; 
            font-weight: bold;
            font-family: 'Courier New', monospace;
        """)
        layout.addWidget(label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        if filename.lower().endswith(('.pdf', '.docx', '.png', '.jpg', '.jpeg', '.tiff', '.tif')):
                            files.append(os.path.join(root, filename))
        
        if files:
            self.files_dropped.emit(files)

class ThemeCircle(QWidget):
    """Custom circular button for theme selection."""
    clicked = pyqtSignal(str)
    
    def __init__(self, color, theme_name):
        super().__init__()
        self.color = color
        self.theme_name = theme_name
        self.selected = False
        self.setFixedSize(60, 60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw main circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(5, 5, 50, 50)
        
        # Draw white selection ring if selected
        if self.selected:
            pen = QPen(QColor("#FFFFFF"), 4)
            painter.setPen(pen)
            painter.drawEllipse(3, 3, 54, 54)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.theme_name)
        self.selected = True
        self.update()
    
    def deselect(self):
        self.selected = False
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Colour Converter")
        self.resize(800, 700)
        self.setStyleSheet("background-color: #000; color: #fff;")
        self.selected_files = []
        self.output_dir = os.path.expanduser("~/Desktop/Converted_Theme")
        self.current_theme = "blue"
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header
        header = QLabel("Colour Converter")
        header.setStyleSheet("""
            font-size: 32px; 
            font-weight: bold; 
            color: #fff;
            font-family: 'Courier New', monospace;
        """)
        main_layout.addWidget(header)

        # Drop Zone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.files_dropped.connect(self.add_files)
        main_layout.addWidget(self.drop_zone, stretch=2)

        # Control buttons and theme circles
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)
        
        # Upload button (circular)
        self.btn_select = QPushButton("⬆")
        self.btn_select.setFixedSize(50, 50)
        self.btn_select.clicked.connect(self.select_files)
        self.btn_select.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        control_layout.addWidget(self.btn_select)
        
        # Change Location button
        self.btn_export_dir = QPushButton("⟲ Change Location")
        self.btn_export_dir.clicked.connect(self.select_export_dir)
        self.btn_export_dir.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #000;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        control_layout.addWidget(self.btn_export_dir)
        
        control_layout.addSpacing(20)
        
        # Theme circles
        self.blue_circle = ThemeCircle("#0047AB", "blue")
        self.blue_circle.clicked.connect(self.select_theme)
        self.magenta_circle = ThemeCircle("#FF1493", "magenta")
        self.magenta_circle.clicked.connect(self.select_theme)
        
        # Select blue by default
        self.blue_circle.selected = True
        self.blue_circle.update()
        
        control_layout.addWidget(self.blue_circle)
        control_layout.addWidget(self.magenta_circle)
        
        control_layout.addStretch()
        
        # Run button
        self.btn_convert = QPushButton("⭐ Run")
        self.btn_convert.setFixedSize(120, 50)
        self.btn_convert.clicked.connect(self.start_conversion)
        self.btn_convert.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #000;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton:disabled {
                background-color: #222;
                color: #555;
            }
        """)
        self.btn_convert.setEnabled(False)
        control_layout.addWidget(self.btn_convert)
        
        main_layout.addLayout(control_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #333;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                           stop:0 #0047AB, stop:1 #FF1493);
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Log output (terminal style)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            background-color: #1a1a1a; 
            border: none; 
            border-radius: 10px;
            font-family: 'Courier New', monospace; 
            font-size: 12px;
            color: #0f0;
            padding: 10px;
        """)
        main_layout.addWidget(self.log_output, stretch=3)
        
        # File count label
        self.file_count_label = QLabel("No files selected.")
        self.file_count_label.setStyleSheet("color: #666; font-size: 11px;")
        main_layout.addWidget(self.file_count_label)

    def select_theme(self, theme):
        self.current_theme = theme
        if theme == "blue":
            self.blue_circle.selected = True
            self.blue_circle.update()
            self.magenta_circle.deselect()
        else:
            self.magenta_circle.selected = True
            self.magenta_circle.update()
            self.blue_circle.deselect()
        self.log(f"🎨 Theme selected: {theme.title()} & White")

    def add_files(self, files):
        self.selected_files = list(set(self.selected_files + files))
        self.update_file_label()

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", 
            "Supported Files (*.pdf *.docx *.png *.jpg *.jpeg *.tiff *.tif);;All Files (*)"
        )
        if files:
            self.add_files(files)

    def select_export_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Export Folder", self.output_dir)
        if directory:
            self.output_dir = directory
            self.log_output.append(f"📁 Export folder: {self.output_dir}")

    def update_file_label(self):
        count = len(self.selected_files)
        if count > 0:
            self.file_count_label.setText(f"{count} file(s) ready for conversion.")
            self.btn_convert.setEnabled(True)
        else:
            self.file_count_label.setText("No files selected.")
            self.btn_convert.setEnabled(False)

    def log(self, message):
        self.log_output.append(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def start_conversion(self):
        if not self.selected_files:
            return
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.btn_convert.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        
        self.log(f"🚀 Starting {self.current_theme.title()} & White conversion...")
        self.log(f"📁 Output: {self.output_dir}")

        self.worker = WorkerThread(self.selected_files, self.output_dir, self.current_theme)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log)
        self.worker.finished.connect(self.conversion_finished)
        self.worker.start()

    def conversion_finished(self, success):
        self.btn_convert.setEnabled(True)
        if success:
            self.log("🎉 All files processed successfully!")
        else:
            self.log("⚠️ Processing completed with some errors.")
        
        os.system(f'open "{self.output_dir}"')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
