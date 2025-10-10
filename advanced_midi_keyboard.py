import sys
import time
import mido
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QProgressBar, QSlider, QGridLayout,
                             QGroupBox, QMainWindow, QFormLayout, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen
from pynput.keyboard import Controller, Key

# --- CORRECTED MIDI NOTE TO KEYBOARD MAPPING ---
# This map is based *precisely* on the provided image, including all shifted characters.
# The keys are mapped sequentially across the keyboard from left to right.
NOTE_MAP = {
    # The first white key visible is C3 (note 48) in standard MIDI numbering, 
    # but the image starts earlier. We map based on the image's sequence.

    # Starting from the left of the image (first white key '3' is E2, note 40)
    # The image is highly non-standard in its note representation. Mapping is strictly sequential.
    
    # Octave 2/3 Transition (Approximate MIDI notes based on C4=60)
    36: '2', # White Key '2' (C#2 is 37, D2 is 38) -> Let's map based on the image sequence
    37: '!', # Black Key '!'
    38: '_', # White Key '_'
    39: '@', # Black Key '@'
    40: '3', # White Key '3'
    41: '4', # White Key '4'
    42: '$', # Black Key '$'
    43: '5', # White Key '5'
    44: '%', # Black Key '%'
    45: '6', # White Key '6'
    46: '^', # Black Key '^'
    47: '7', # White Key '7'

    # Octave 3/4 Transition
    48: '8', # White Key '8'
    49: '*', # Black Key '*'
    50: '9', # White Key '9'
    51: '(', # Black Key '('
    52: '0', # White Key '0'
    53: 'q', # White Key 'q'
    54: 'Q', # Black Key 'Q'
    55: 'w', # White Key 'w'
    56: 'W', # Black Key 'W'
    57: 'e', # White Key 'e'
    58: 'E', # Black Key 'E'
    59: 'r', # White Key 'r'

    # Octave 4 (Middle C Octave)
    60: 't',  # White Key 't'
    61: 'T',  # Black Key 'T'
    62: 'y',  # White Key 'y'
    63: 'Y',  # Black Key 'Y'
    64: 'u',  # White Key 'u'
    65: 'i',  # White Key 'i'
    66: 'I',  # Black Key 'I'
    67: 'o',  # White Key 'o'
    68: 'O',  # Black Key 'O'
    69: 'p',  # White Key 'p'
    70: 'P',  # Black Key 'P'
    71: 'a',  # White Key 'a'

    # Octave 5
    72: 's',  # White Key 's'
    73: 'S',  # Black Key 'S'
    74: 'd',  # White Key 'd'
    75: 'D',  # Black Key 'D'
    76: 'f',  # White Key 'f'
    77: 'g',  # White Key 'g'
    78: 'G',  # Black Key 'G'
    79: 'h',  # White Key 'h'
    80: 'H',  # Black Key 'H'
    81: 'j',  # White Key 'j'
    82: 'J',  # Black Key 'J'
    83: 'k',  # White Key 'k'

    # Octave 6
    84: 'l',  # White Key 'l'
    85: 'L',  # Black Key 'L'
    86: 'z',  # White Key 'z'
    87: 'Z',  # Black Key 'Z'
    88: 'x',  # White Key 'x'
    89: 'c',  # White Key 'c'
    90: 'C',  # Black Key 'C'
    91: 'v',  # White Key 'v'
    92: 'V',  # Black Key 'V'
    93: 'b',  # White Key 'b'
    94: 'B',  # Black Key 'B'
    95: 'n',  # White Key 'n'

    # Octave 7 (Final keys visible in the image)
    96: 'm',  # White Key 'm'
    97: '_',  # Black Key '_' (second-to-last set)
    98: 'u',  # White Key 'u' (second-to-last set)
    99: '_',  # Black Key '_' (second-to-last set)
    100: 'o', # White Key 'o' (second-to-last set)
    101: '_', # White Key '_' (second-to-last set)
    102: 's', # Black Key 's' (final set)
    103: 'f', # White Key 'f' (final set)
    104: 'h', # White Key 'h' (final set)
    105: 'j', # White Key 'j' (final set)
    106: '_', # White Key '_' (final set)
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
# --- PIANO WIDGET CLASS (Visualizer) ---
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
        
        # Define the range of MIDI notes to display (matching the NOTE_MAP)
        min_note = min(NOTE_MAP.keys())
        max_note = max(NOTE_MAP.keys())

        # Determine which notes are white keys (0, 2, 4, 5, 7, 9, 11 semitones from C)
        white_keys_all = [k for k in range(min_note, max_note + 1) if k % 12 in [0, 2, 4, 5, 7, 9, 11]]
        # Filter down to the actual keys used in the mapping to size the widget correctly
        white_keys = [k for k in white_keys_all if k in NOTE_MAP]
        black_keys = [k for k in range(min_note, max_note + 1) if k % 12 in [1, 3, 6, 8, 10] and k in NOTE_MAP]

        if not white_keys: # Handle case with no keys mapped
            return

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
        white_key_index_map = {note: i for i, note in enumerate(white_keys)}
        
        # Iterate over all notes in the range to position black keys
        # We need to find the previous *mapped* white key for correct positioning
        prev_white_key_index = -1
        for note in range(min_note, max_note + 1):
            if note in white_keys:
                prev_white_key_index = white_key_index_map.get(note, prev_white_key_index)
            
            if note in black_keys:
                if prev_white_key_index != -1:
                    # Position based on the previous white key
                    x_pos = prev_white_key_index * white_key_width + (white_key_width - black_key_width / 2)
                    rect = QRectF(x_pos, 0, black_key_width, black_key_height)
                    self._key_rects[note] = rect
                    painter.setPen(Qt.black)
                    painter.setBrush(pressed_color if note in self.active_notes else black_key_color)
                    painter.drawRect(rect)

    def set_active_notes(self, notes):
        self.active_notes = notes
        self.update()

# --- MIDI LOADING THREAD ---
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

# --- MIDI PLAYER THREAD (FIXED) ---
class MidiPlayerThread(QThread):
    """Thread for handling MIDI playback with real-time controls."""
    progress_update = pyqtSignal(int)
    note_event = pyqtSignal(set)
    finished = pyqtSignal()
    status_update = pyqtSignal(str)

    # Map of shifted characters to their base keys on a standard QWERTY keyboard
    SHIFT_MAP = {
        '!': '1', '@': '2', '$': '4', '%': '5', '^': '6', '*': '8', '(': '9', '_': '-',
        'Q': 'q', 'W': 'w', 'E': 'e', 'T': 't', 'Y': 'y', 'I': 'i', 'O': 'o', 'P': 'p',
        'S': 's', 'D': 'd', 'G': 'g', 'H': 'h', 'J': 'j', 'L': 'l', 'Z': 'z',
        'C': 'c', 'V': 'v', 'B': 'b'
    }

    def __init__(self, mid_obj):
        super().__init__()
        self.mid = mid_obj
        self.keyboard = Controller()
        self.is_running = True
        self.speed_multiplier = 1.0
        
        # State tracking for keyboard presses
        self.active_midi_notes = set()
        self.pressed_keys = {}  # Maps MIDI note -> base character pressed
        self.shifted_notes_active = set() # Set of active notes that require shift

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
                char_to_press = NOTE_MAP.get(msg.note)
                
                # Avoid re-triggering a key that's already down for another note
                if not char_to_press or msg.note in self.pressed_keys:
                    continue

                # Determine if shift is needed and find the base key
                if char_to_press in self.SHIFT_MAP:
                    # This is the first shifted key, so press Shift down
                    if not self.shifted_notes_active:
                        self.keyboard.press(Key.shift)
                    self.shifted_notes_active.add(msg.note)
                    base_key = self.SHIFT_MAP[char_to_press]
                else:
                    base_key = char_to_press
                
                self.keyboard.press(base_key)
                self.pressed_keys[msg.note] = base_key # Record what we pressed

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in self.active_midi_notes:
                    self.active_midi_notes.remove(msg.note)
                
                # Check if we have a record of this note being pressed
                if msg.note in self.pressed_keys:
                    base_key_to_release = self.pressed_keys.pop(msg.note)
                    self.keyboard.release(base_key_to_release)

                    # If this was a shifted note, update the shift state
                    if msg.note in self.shifted_notes_active:
                        self.shifted_notes_active.remove(msg.note)
                        # If it was the *last* shifted note, release Shift
                        if not self.shifted_notes_active:
                            self.keyboard.release(Key.shift)
            
            self.note_event.emit(self.active_midi_notes)
            msg_count += 1
            self.progress_update.emit(msg_count)
        
        self.release_all_keys()
        self.finished.emit()

    def stop(self):
        self.is_running = False

    def release_all_keys(self):
        # Ensure all currently pressed keys are released upon stopping/finishing
        for base_key in self.pressed_keys.values():
            try:
                self.keyboard.release(base_key)
            except Exception as e:
                print(f"Could not release key {base_key}: {e}")
        
        # If shift key was held, release it
        if self.shifted_notes_active:
             try:
                self.keyboard.release(Key.shift)
             except Exception as e:
                print(f"Could not release shift key: {e}")

        self.pressed_keys.clear()
        self.shifted_notes_active.clear()
        self.active_midi_notes.clear()
        self.note_event.emit(self.active_midi_notes)

# --- MAIN APPLICATION WINDOW ---
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
            self.status_label.setText("Loading file, please wait...")
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
            # Clean up any existing thread before starting a new one
            if self.player_thread and self.player_thread.isRunning():
                self.player_thread.stop()
                self.player_thread.wait()

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
            # Wait for the thread to finish execution
            self.player_thread.wait() 
            self.on_playback_finished(is_stopped=True) # Manually call cleanup and UI reset

    def on_playback_finished(self, is_stopped=False):
        if not is_stopped:
             self.status_label.setText("Playback finished.")
        else:
             self.status_label.setText("Playback stopped by user.")
        
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.load_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.piano_widget.set_active_notes(set()) # Clear visualizer

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