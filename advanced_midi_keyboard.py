import sys
import time
import mido
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QProgressBar, QSlider, QGridLayout,
                             QGroupBox, QMainWindow, QFormLayout, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen
from pynput.keyboard import Controller

# --- CORRECTED MIDI NOTE TO KEYBOARD MAPPING ---
# This map is based on the provided image, mapping MIDI notes to specific keyboard characters.
# It covers multiple octaves sequentially across the keyboard.
NOTE_MAP = {
    # Octave 2 (starting from C2)
    36: '1',
    37: '!',
    38: '2',
    39: '@',
    40: '3',
    41: '4',
    42: '$',
    43: '5',
    44: '%',
    45: '6',
    46: '^',
    47: '7',
    # Octave 3
    48: '8',
    49: '*',
    50: '9',
    51: '(',
    52: '0',
    53: 'q',
    54: 'Q',
    55: 'w',
    56: 'W',
    57: 'e',
    58: 'E',
    59: 'r',
    # Octave 4 (Middle C octave)
    60: 't',  # C4 (Middle C)
    61: 'T',
    62: 'y',
    63: 'Y',
    64: 'u',
    65: 'i',
    66: 'I',
    67: 'o',
    68: 'O',
    69: 'p',
    70: 'P',
    71: 'a',
    # Octave 5
    72: 's',
    73: 'S',
    74: 'd',
    75: 'D',
    76: 'f',
    77: 'g',
    78: 'G',
    79: 'h',
    80: 'H',
    81: 'j',
    82: 'J',
    83: 'k',
    # Octave 6
    84: 'l',
    85: 'L',
    86: 'z',
    87: 'Z',
    88: 'x',
    89: 'c',
    90: 'C',
    91: 'v',
    92: 'V',
    93: 'b',
    94: 'B',
    95: 'n',
    # Octave 7
    96: 'm',
}


# --- STYLING ---
DARK_STYLESHEET = """
QWidget {
    font-size: 11px;
    color: #e0e0e0;
    background-color: #2d2d2d;
}
QMainWindow {
    background-color: #2d2d2d;
}
QGroupBox {
    font-weight: bold;
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 6px;
    margin-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
}
QPushButton {
    background-color: #555;
    border: 1px solid #666;
    padding: 6px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #6a6a6a;
}
QPushButton:pressed {
    background-color: #4a4a4a;
}
QPushButton:disabled {
    background-color: #444;
    color: #888;
}
QProgressBar {
    border: 1px solid #555;
    border-radius: 4px;
    text-align: center;
    background-color: #444;
}
QProgressBar::chunk {
    background-color: #0078d7;
    border-radius: 3px;
}
QSlider::groove:horizontal {
    border: 1px solid #555;
    height: 4px;
    background: #444;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0078d7;
    border: 1px solid #0078d7;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}
QLabel#statusLabel {
    color: #a0a0a0;
    font-style: italic;
}
"""

class PianoWidget(QWidget):
    """A custom widget to visualize a piano keyboard."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.active_notes = set()
        self._key_rects = {}

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor("#1c1c1c"))

        white_key_color = QColor(Qt.white)
        black_key_color = QColor(Qt.black)
        pressed_color = QColor("#0078d7")
        
        white_keys = [k for k in range(36, 111) if k % 12 not in [1, 3, 6, 8, 10]]
        black_keys = [k for k in range(36, 111) if k % 12 in [1, 3, 6, 8, 10]]

        white_key_width = self.width() / len(white_keys)
        black_key_width = white_key_width * 0.6
        black_key_height = self.height() * 0.6

        # Draw white keys first
        for i, note in enumerate(white_keys):
            rect = QRectF(i * white_key_width, 0, white_key_width, self.height())
            self._key_rects[note] = rect
            painter.setPen(Qt.black)
            painter.setBrush(pressed_color if note in self.active_notes else white_key_color)
            painter.drawRect(rect)

        # Draw black keys
        white_key_index = -1
        for note in range(36, 111):
            if note in white_keys:
                white_key_index += 1
            
            if note in black_keys:
                # Find the previous white key's index
                prev_white_key_index = white_key_index
                rect = QRectF(prev_white_key_index * white_key_width + (white_key_width - black_key_width / 2), 0, black_key_width, black_key_height)
                self._key_rects[note] = rect
                painter.setPen(Qt.black)
                painter.setBrush(pressed_color if note in self.active_notes else black_key_color)
                painter.drawRect(rect)

    def set_active_notes(self, notes):
        self.active_notes = notes
        self.update()


class MidiLoadingThread(QThread):
    """Thread to load a MIDI file and extract its info without freezing the GUI."""
    loading_complete = pyqtSignal(object, dict)

    def __init__(self, midi_path):
        super().__init__()
        self.midi_path = midi_path

    def run(self):
        try:
            mid = mido.MidiFile(self.midi_path, clip=True)
            messages = list(mid)
            note_count = sum(1 for msg in messages if msg.type == 'note_on' and msg.velocity > 0)
            info = {
                "path": self.midi_path,
                "filename": self.midi_path.split('/')[-1],
                "track_count": len(mid.tracks),
                "note_count": note_count,
                "total_messages": len(messages)
            }
            self.loading_complete.emit(mid, info)
        except Exception as e:
            self.loading_complete.emit(None, {"error": str(e)})


class MidiPlayerThread(QThread):
    """Thread for handling MIDI playback with real-time controls."""
    progress_update = pyqtSignal(int)
    note_event = pyqtSignal(set)
    finished = pyqtSignal()
    status_update = pyqtSignal(str)

    def __init__(self, mid_obj):
        super().__init__()
        self.mid = mid_obj
        self.keyboard = Controller()
        self.is_running = True
        self.pressed_keys = set()
        self.active_midi_notes = set()
        self.speed_multiplier = 1.0

    def run(self):
        msg_count = 0
        messages = list(self.mid)
        
        self.status_update.emit("Playback will start in 3 seconds... Switch to your target window.")
        time.sleep(3)
        self.status_update.emit("Playing...")

        for msg in messages:
            if not self.is_running:
                break
            
            time.sleep(msg.time / self.speed_multiplier)

            if msg.is_meta:
                continue

            if msg.type == 'note_on' and msg.velocity > 0:
                self.active_midi_notes.add(msg.note)
                key = NOTE_MAP.get(msg.note)
                if key:
                    if key not in self.pressed_keys:
                        self.keyboard.press(key)
                        self.pressed_keys.add(key)
                else:
                    self.status_update.emit(f"Skipped note: {msg.note} (out of range)")
            
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in self.active_midi_notes:
                    self.active_midi_notes.remove(msg.note)
                key = NOTE_MAP.get(msg.note)
                if key and key in self.pressed_keys:
                    self.keyboard.release(key)
                    self.pressed_keys.remove(key)
            
            self.note_event.emit(self.active_midi_notes)
            msg_count += 1
            self.progress_update.emit(msg_count)
        
        self.release_all_keys()
        self.finished.emit()

    def stop(self):
        self.is_running = False

    def release_all_keys(self):
        for key in list(self.pressed_keys):
            self.keyboard.release(key)
        self.pressed_keys.clear()
        self.active_midi_notes.clear()
        self.note_event.emit(self.active_midi_notes)


class MidiKeyboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.loaded_midi_object = None
        self.midi_info = {}
        self.player_thread = None
        self.loading_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Advanced MIDI Keyboard Simulator')
        self.setGeometry(100, 100, 550, 450)
        self.setStyleSheet(DARK_STYLESHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- File Info Group ---
        info_group = QGroupBox("MIDI File Information")
        info_layout = QFormLayout()
        self.filename_label = QLabel("N/A")
        self.track_count_label = QLabel("N/A")
        self.note_count_label = QLabel("N/A")
        info_layout.addRow("Filename:", self.filename_label)
        info_layout.addRow("Track Count:", self.track_count_label)
        info_layout.addRow("Note Events:", self.note_count_label)
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # --- Playback Controls Group ---
        controls_group = QGroupBox("Playback Controls")
        controls_layout = QGridLayout()
        
        self.load_button = QPushButton("Load MIDI File")
        self.load_button.clicked.connect(self.select_midi_file)
        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.play_midi)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_midi)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.stop_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)

        # Speed Slider
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200) # 0.5x to 2.0x
        self.speed_slider.setValue(100)
        self.speed_slider.setEnabled(False)
        self.speed_slider.valueChanged.connect(self.speed_changed)
        self.speed_label = QLabel(f"Speed: {self.speed_slider.value() / 100:.2f}x")

        controls_layout.addLayout(button_layout, 0, 0, 1, 2)
        controls_layout.addWidget(self.progress_bar, 1, 0, 1, 2)
        controls_layout.addWidget(self.speed_label, 2, 0)
        controls_layout.addWidget(self.speed_slider, 2, 1)
        
        controls_group.setLayout(controls_layout)
        main_layout.addWidget(controls_group)
        
        # --- Piano Visualizer ---
        piano_group = QGroupBox("Visualizer")
        piano_layout = QVBoxLayout()
        self.piano_widget = PianoWidget()
        piano_layout.addWidget(self.piano_widget)
        piano_group.setLayout(piano_layout)
        main_layout.addWidget(piano_group)

        main_layout.addStretch()

        # --- Status Bar ---
        self.status_label = QLabel("Welcome! Please load a MIDI file.")
        self.status_label.setObjectName("statusLabel")
        self.statusBar().addPermanentWidget(self.status_label, 1)

        self.show()

    def select_midi_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open MIDI File", "", "MIDI Files (*.mid *.midi)")
        if file_name:
            self.reset_ui_for_loading()
            self.status_label.setText("Loading large file, please wait...")
            self.loading_thread = MidiLoadingThread(file_name)
            self.loading_thread.loading_complete.connect(self.on_loading_finished)
            self.loading_thread.start()

    def on_loading_finished(self, mid_obj, info):
        if mid_obj:
            self.loaded_midi_object = mid_obj
            self.midi_info = info
            self.filename_label.setText(info["filename"])
            self.track_count_label.setText(str(info["track_count"]))
            self.note_count_label.setText(f"{info['note_count']:,}")
            self.progress_bar.setMaximum(info["total_messages"])
            self.play_button.setEnabled(True)
            self.speed_slider.setEnabled(True)
            self.status_label.setText(f"Successfully loaded '{info['filename']}'. Ready to play.")
        else:
            self.status_label.setText(f"Error loading file: {info.get('error', 'Unknown error')}")
        
        self.load_button.setEnabled(True)

    def play_midi(self):
        if self.loaded_midi_object:
            self.player_thread = MidiPlayerThread(self.loaded_midi_object)
            self.player_thread.progress_update.connect(self.progress_bar.setValue)
            self.player_thread.note_event.connect(self.piano_widget.set_active_notes)
            self.player_thread.finished.connect(self.on_playback_finished)
            self.player_thread.status_update.connect(self.status_label.setText)
            self.player_thread.speed_multiplier = self.speed_slider.value() / 100.0
            self.player_thread.start()

            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.load_button.setEnabled(False)

    def stop_midi(self):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.status_label.setText("Playback stopped by user.")
            self.stop_button.setEnabled(False)

    def on_playback_finished(self):
        self.status_label.setText("Playback finished.")
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.load_button.setEnabled(True)
        self.progress_bar.setValue(0)

    def speed_changed(self, value):
        speed = value / 100.0
        self.speed_label.setText(f"Speed: {speed:.2f}x")
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.speed_multiplier = speed
    
    def reset_ui_for_loading(self):
        self.play_button.setEnabled(False)
        self.load_button.setEnabled(False)
        self.speed_slider.setEnabled(False)
        self.filename_label.setText("Loading...")
        self.track_count_label.setText("...")
        self.note_count_label.setText("...")
        self.progress_bar.setValue(0)
        self.piano_widget.set_active_notes(set())

    def closeEvent(self, event):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MidiKeyboardApp()
    sys.exit(app.exec_())