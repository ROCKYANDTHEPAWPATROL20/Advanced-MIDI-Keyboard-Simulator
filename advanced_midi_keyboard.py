import sys
import time
import mido
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QProgressBar, QSlider, QGridLayout,
                             QGroupBox, QMainWindow, QFormLayout, QTextEdit, QListWidget,
                             QComboBox, QSpinBox, QListWidgetItem)
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
QTextEdit, QListWidget {
    background-color: #252525;
    border: 1px solid #555;
    border-radius: 4px;
}
"""
# --- ENHANCED PIANO WIDGET CLASS (Visualizer) ---
class PianoWidget(QWidget):
    """A custom widget to visualize a piano keyboard with velocity."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        # Active notes now a dict: {note: velocity}
        self.active_notes = {}
        self._key_rects = {}

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(self.rect(), QColor("#1c1c1c"))

        white_key_color = QColor(Qt.white)
        black_key_color = QColor(Qt.black)
        
        min_note = min(NOTE_MAP.keys())
        max_note = max(NOTE_MAP.keys())

        white_keys_all = [k for k in range(min_note, max_note + 1) if k % 12 in [0, 2, 4, 5, 7, 9, 11]]
        white_keys = [k for k in white_keys_all if k in NOTE_MAP]
        black_keys = [k for k in range(min_note, max_note + 1) if k % 12 in [1, 3, 6, 8, 10] and k in NOTE_MAP]

        if not white_keys:
            return

        white_key_width = self.width() / len(white_keys)
        black_key_width = white_key_width * 0.6
        black_key_height = self.height() * 0.6

        # Draw white keys
        for i, note in enumerate(white_keys):
            rect = QRectF(i * white_key_width, 0, white_key_width, self.height())
            self._key_rects[note] = rect
            painter.setPen(Qt.black)
            
            # --- Velocity Visualization ---
            if note in self.active_notes:
                velocity = self.active_notes[note]
                # Hue: 212 (blue), Saturation: varies with velocity, Value: constant
                color = QColor.fromHsvF(212/360.0, min(1.0, 0.4 + velocity / 127.0), 1.0)
                painter.setBrush(color)
            else:
                painter.setBrush(white_key_color)
            painter.drawRect(rect)

        # Draw black keys
        white_key_index_map = {note: i for i, note in enumerate(white_keys)}
        prev_white_key_index = -1
        for note in range(min_note, max_note + 1):
            if note in white_keys:
                prev_white_key_index = white_key_index_map.get(note, prev_white_key_index)
            
            if note in black_keys:
                if prev_white_key_index != -1:
                    x_pos = prev_white_key_index * white_key_width + (white_key_width - black_key_width / 2)
                    rect = QRectF(x_pos, 0, black_key_width, black_key_height)
                    self._key_rects[note] = rect
                    painter.setPen(Qt.black)

                    # --- Velocity Visualization ---
                    if note in self.active_notes:
                        velocity = self.active_notes[note]
                        color = QColor.fromHsvF(212/360.0, min(1.0, 0.4 + velocity / 127.0), 1.0)
                        painter.setBrush(color)
                    else:
                        painter.setBrush(black_key_color)
                    painter.drawRect(rect)

    def set_active_notes(self, notes_dict):
        self.active_notes = notes_dict
        self.update()

# --- MIDI LOADING THREAD ---
class MidiLoadingThread(QThread):
    loading_complete = pyqtSignal(object, dict)
    def __init__(self, midi_path):
        super().__init__()
        self.midi_path = midi_path
    def run(self):
        try:
            mid = mido.MidiFile(self.midi_path, clip=True)
            messages = list(mid)
            note_count = sum(1 for msg in messages if msg.type == 'note_on' and msg.velocity > 0)
            info = {"path": self.midi_path, "filename": self.midi_path.split('/')[-1],
                    "track_count": len(mid.tracks), "note_count": note_count, "total_messages": len(messages)}
            self.loading_complete.emit(mid, info)
        except Exception as e:
            self.loading_complete.emit(None, {"error": str(e)})

# --- MIDI PLAYER THREAD ---
class MidiPlayerThread(QThread):
    progress_update = pyqtSignal(int)
    note_event = pyqtSignal(dict) # Emits dict {note: velocity}
    log_message = pyqtSignal(str) # Emits message string for log
    finished = pyqtSignal()
    status_update = pyqtSignal(str)

    SHIFT_MAP = {'!': '1', '@': '2', '$': '4', '%': '5', '^': '6', '*': '8', '(': '9', '_': '-', 'Q': 'q', 'W': 'w',
                 'E': 'e', 'T': 't', 'Y': 'y', 'I': 'i', 'O': 'o', 'P': 'p', 'S': 's', 'D': 'd', 'G': 'g', 'H': 'h',
                 'J': 'j', 'L': 'l', 'Z': 'z', 'C': 'c', 'V': 'v', 'B': 'b'}

    def __init__(self, mid_obj):
        super().__init__()
        self.mid = mid_obj
        self.keyboard = Controller()
        self.is_running = True
        self.is_paused = False
        self.speed_multiplier = 1.0
        self.transpose = 0 # Transposition value in semitones
        self.active_midi_notes = {} # {note: velocity}
        self.pressed_keys = {}
        self.shifted_notes_active = set()

    def run(self):
        msg_count = 0
        messages = list(self.mid)
        self.status_update.emit("Playback will start in 3 seconds... Switch to your target window.")
        time.sleep(3)
        self.status_update.emit("Playing...")

        for msg in messages:
            while self.is_paused:
                if not self.is_running: break
                time.sleep(0.1)
            if not self.is_running: break
            
            time.sleep(msg.time / self.speed_multiplier)
            self.log_message.emit(str(msg))

            if msg.is_meta: continue
            
            # This is a safe check for note attribute
            if not hasattr(msg, 'note'): continue

            # --- REAL-TIME TRANSFORMATION ---
            transposed_note = msg.note + self.transpose
            if not (0 <= transposed_note <= 127): continue # Skip notes outside valid MIDI range

            if msg.type == 'note_on' and msg.velocity > 0:
                self.active_midi_notes[transposed_note] = msg.velocity
                char_to_press = NOTE_MAP.get(transposed_note)
                if not char_to_press or transposed_note in self.pressed_keys: continue

                if char_to_press in self.SHIFT_MAP:
                    if not self.shifted_notes_active: self.keyboard.press(Key.shift)
                    self.shifted_notes_active.add(transposed_note)
                    base_key = self.SHIFT_MAP[char_to_press]
                else:
                    base_key = char_to_press
                
                self.keyboard.press(base_key)
                self.pressed_keys[transposed_note] = base_key

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if transposed_note in self.active_midi_notes:
                    del self.active_midi_notes[transposed_note]
                
                if transposed_note in self.pressed_keys:
                    base_key_to_release = self.pressed_keys.pop(transposed_note)
                    self.keyboard.release(base_key_to_release)
                    if transposed_note in self.shifted_notes_active:
                        self.shifted_notes_active.remove(transposed_note)
                        if not self.shifted_notes_active: self.keyboard.release(Key.shift)
            
            self.note_event.emit(self.active_midi_notes.copy())
            msg_count += 1
            self.progress_update.emit(msg_count)
        
        self.release_all_keys()
        self.finished.emit()

    def stop(self): self.is_running = False
    def pause(self): self.is_paused = True; self.status_update.emit("Playback paused.")
    def resume(self): self.is_paused = False; self.status_update.emit("Resuming playback...")
    def release_all_keys(self):
        for base_key in self.pressed_keys.values():
            try: self.keyboard.release(base_key)
            except Exception: pass
        if self.shifted_notes_active:
            try: self.keyboard.release(Key.shift)
            except Exception: pass
        self.pressed_keys.clear()
        self.shifted_notes_active.clear()
        self.active_midi_notes.clear()
        self.note_event.emit(self.active_midi_notes.copy())

# --- MIDI INPUT THREAD ---
class MidiInputThread(QThread):
    note_event = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    
    def __init__(self, port_name):
        super().__init__()
        self.port_name = port_name
        self.is_running = True
        self.active_notes = {}

    def run(self):
        try:
            with mido.open_input(self.port_name) as port:
                self.log_message.emit(f"Listening on MIDI input: {self.port_name}")
                for msg in port:
                    if not self.is_running:
                        break
                    
                    self.log_message.emit(str(msg))

                    if msg.type == 'note_on' and msg.velocity > 0:
                        self.active_notes[msg.note] = msg.velocity
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        if msg.note in self.active_notes:
                            del self.active_notes[msg.note]
                    
                    self.note_event.emit(self.active_notes.copy())

        except Exception as e:
            self.log_message.emit(f"Error with MIDI input: {e}")
        
        # Clear notes on exit
        self.active_notes.clear()
        self.note_event.emit(self.active_notes.copy())
        self.log_message.emit(f"Stopped listening on {self.port_name}")

    def stop(self):
        self.is_running = False

# --- MAIN APPLICATION WINDOW ---
class MidiKeyboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.midi_files = {} # Store loaded mido objects: {path: mid_obj}
        self.player_thread = None
        self.loading_thread = None
        self.input_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Advanced MIDI Keyboard Simulator')
        self.setGeometry(100, 100, 950, 650)
        self.setStyleSheet(DARK_STYLESHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # --- LEFT PANEL (Controls) ---
        left_panel_layout = QVBoxLayout()
        
        # --- Playlist Group ---
        playlist_group = QGroupBox("Playlist")
        playlist_layout = QVBoxLayout()
        self.playlist_widget = QListWidget()
        self.playlist_widget.itemDoubleClicked.connect(self.play_midi)
        playlist_buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Files")
        self.add_button.clicked.connect(self.add_files_to_playlist)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected_from_playlist)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_playlist)
        playlist_buttons_layout.addWidget(self.add_button)
        playlist_buttons_layout.addWidget(self.remove_button)
        playlist_buttons_layout.addWidget(self.clear_button)
        playlist_layout.addWidget(self.playlist_widget)
        playlist_layout.addLayout(playlist_buttons_layout)
        playlist_group.setLayout(playlist_layout)
        left_panel_layout.addWidget(playlist_group)

        # --- Playback Controls Group ---
        controls_group = QGroupBox("Playback Controls")
        controls_layout = QGridLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_midi)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_midi)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200); self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.speed_changed)
        self.speed_label = QLabel(f"Speed: {self.speed_slider.value() / 100:.2f}x")
        controls_layout.addLayout(button_layout, 0, 0, 1, 2)
        controls_layout.addWidget(self.progress_bar, 1, 0, 1, 2)
        controls_layout.addWidget(self.speed_label, 2, 0)
        controls_layout.addWidget(self.speed_slider, 2, 1)
        controls_group.setLayout(controls_layout)
        left_panel_layout.addWidget(controls_group)

        # --- MIDI Transformation Group ---
        transform_group = QGroupBox("Real-time Transformation")
        transform_layout = QFormLayout()
        self.transpose_spinbox = QSpinBox()
        self.transpose_spinbox.setRange(-24, 24)
        self.transpose_spinbox.setValue(0)
        self.transpose_spinbox.valueChanged.connect(self.transpose_changed)
        transform_layout.addRow("Transpose (Semitones):", self.transpose_spinbox)
        transform_group.setLayout(transform_layout)
        left_panel_layout.addWidget(transform_group)

        # --- MIDI Input Group ---
        input_group = QGroupBox("MIDI Input")
        input_layout = QHBoxLayout()
        self.midi_input_combo = QComboBox()
        self.midi_input_combo.addItems(mido.get_input_names())
        self.connect_button = QPushButton("Connect")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_midi_input)
        input_layout.addWidget(self.midi_input_combo)
        input_layout.addWidget(self.connect_button)
        input_group.setLayout(input_layout)
        left_panel_layout.addWidget(input_group)
        
        left_panel_widget = QWidget()
        left_panel_widget.setLayout(left_panel_layout)

        # --- RIGHT PANEL (Visualization) ---
        right_panel_layout = QVBoxLayout()
        
        piano_group = QGroupBox("Visualizer")
        piano_layout = QVBoxLayout()
        self.piano_widget = PianoWidget()
        piano_layout.addWidget(self.piano_widget)
        piano_group.setLayout(piano_layout)
        right_panel_layout.addWidget(piano_group, 2) # Give more space to piano

        log_group = QGroupBox("Real-time MIDI Event Log")
        log_layout = QVBoxLayout()
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)
        log_group.setLayout(log_layout)
        right_panel_layout.addWidget(log_group, 1) # Give less space to log
        
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_panel_layout)

        main_layout.addWidget(left_panel_widget, 1)
        main_layout.addWidget(right_panel_widget, 2)
        
        self.status_label = QLabel("Welcome! Please add MIDI files to the playlist.")
        self.status_label.setObjectName("statusLabel")
        self.statusBar().addPermanentWidget(self.status_label, 1)

        self.update_button_states()
        self.show()

    def add_files_to_playlist(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add MIDI Files", "", "MIDI Files (*.mid *.midi)")
        for file_path in files:
            if file_path:
                # Avoid adding duplicates
                if not self.playlist_widget.findItems(file_path, Qt.MatchExactly):
                    item = QListWidgetItem(file_path)
                    self.playlist_widget.addItem(item)
        self.update_button_states()

    def remove_selected_from_playlist(self):
        for item in self.playlist_widget.selectedItems():
            row = self.playlist_widget.row(item)
            self.playlist_widget.takeItem(row)
            path = item.text()
            if path in self.midi_files:
                del self.midi_files[path]
        self.update_button_states()

    def clear_playlist(self):
        self.playlist_widget.clear()
        self.midi_files.clear()
        self.update_button_states()

    def play_midi(self):
        current_item = self.playlist_widget.currentItem()
        if not current_item:
            if self.playlist_widget.count() > 0:
                self.playlist_widget.setCurrentRow(0)
                current_item = self.playlist_widget.item(0)
            else:
                self.status_label.setText("Playlist is empty.")
                return

        file_path = current_item.text()
        
        if file_path in self.midi_files:
            self.start_playback(self.midi_files[file_path])
        else:
            self.status_label.setText(f"Loading {file_path.split('/')[-1]}...")
            self.loading_thread = MidiLoadingThread(file_path)
            self.loading_thread.loading_complete.connect(self.on_loading_finished_and_play)
            self.loading_thread.start()

    def on_loading_finished_and_play(self, mid_obj, info):
        if mid_obj:
            self.midi_files[info["path"]] = mid_obj
            self.start_playback(mid_obj)
            self.progress_bar.setMaximum(info["total_messages"])
        else:
            self.status_label.setText(f"Error loading file: {info.get('error', 'Unknown error')}")

    def start_playback(self, mid_obj):
        if self.input_thread: self.toggle_midi_input(False) # Disconnect input if playing
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop(); self.player_thread.wait()

        self.player_thread = MidiPlayerThread(mid_obj)
        self.player_thread.progress_update.connect(self.progress_bar.setValue)
        self.player_thread.note_event.connect(self.piano_widget.set_active_notes)
        self.player_thread.log_message.connect(self.append_to_log)
        self.player_thread.finished.connect(self.on_playback_finished)
        self.player_thread.status_update.connect(self.status_label.setText)
        self.player_thread.speed_multiplier = self.speed_slider.value() / 100.0
        self.player_thread.transpose = self.transpose_spinbox.value()
        self.player_thread.start()
        self.update_button_states()

    def toggle_pause(self):
        if self.player_thread and self.player_thread.isRunning():
            if self.player_thread.is_paused:
                self.player_thread.resume()
                self.pause_button.setText("Pause")
            else:
                self.player_thread.pause()
                self.pause_button.setText("Resume")

    def stop_midi(self):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()
            self.on_playback_finished(is_stopped=True)

    def on_playback_finished(self, is_stopped=False):
        if not is_stopped: self.status_label.setText("Playback finished.")
        else: self.status_label.setText("Playback stopped by user.")
        self.progress_bar.setValue(0)
        self.piano_widget.set_active_notes({})
        self.pause_button.setText("Pause")
        self.update_button_states()

    def speed_changed(self, value):
        speed = value / 100.0
        self.speed_label.setText(f"Speed: {speed:.2f}x")
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.speed_multiplier = speed

    def transpose_changed(self, value):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.transpose = value
            self.status_label.setText(f"Transposition set to {value} semitones.")

    def append_to_log(self, message):
        self.log_edit.append(message)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def toggle_midi_input(self, checked):
        if checked:
            if self.player_thread and self.player_thread.isRunning():
                self.stop_midi()
            port_name = self.midi_input_combo.currentText()
            if not port_name:
                self.status_label.setText("No MIDI input device selected.")
                self.connect_button.setChecked(False)
                return
            self.input_thread = MidiInputThread(port_name)
            self.input_thread.note_event.connect(self.piano_widget.set_active_notes)
            self.input_thread.log_message.connect(self.append_to_log)
            self.input_thread.start()
            self.connect_button.setText("Disconnect")
            self.midi_input_combo.setEnabled(False)
        else:
            if self.input_thread:
                self.input_thread.stop()
                self.input_thread.wait()
                self.input_thread = None
            self.connect_button.setText("Connect")
            self.connect_button.setChecked(False)
            self.midi_input_combo.setEnabled(True)
            self.piano_widget.set_active_notes({}) # Clear piano

    def update_button_states(self):
        is_playlist_non_empty = self.playlist_widget.count() > 0
        # --- FIX IS HERE ---
        is_playing = bool(self.player_thread and self.player_thread.isRunning())
        
        self.play_button.setEnabled(is_playlist_non_empty and not is_playing)
        self.pause_button.setEnabled(is_playing)
        self.stop_button.setEnabled(is_playing)
        self.playlist_widget.setEnabled(not is_playing)
        self.add_button.setEnabled(not is_playing)
        self.remove_button.setEnabled(not is_playing)
        self.clear_button.setEnabled(not is_playing)

    def closeEvent(self, event):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop(); self.player_thread.wait()
        if self.input_thread and self.input_thread.isRunning():
            self.input_thread.stop(); self.input_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MidiKeyboardApp()
    sys.exit(app.exec_())