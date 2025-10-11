import sys
import time
from typing import Dict, List, Tuple, Optional

import mido
from pynput.keyboard import Controller, Key
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QProgressBar, QSlider, QGridLayout,
                             QGroupBox, QMainWindow, QFormLayout, QTextEdit, QListWidget,
                             QComboBox, QSpinBox, QListWidgetItem)

# --- APPLICATION CONSTANTS ---

# Maps MIDI note numbers to the character that should be pressed.
NOTE_MAP: Dict[int, str] = {
    36: '2', 37: '!', 38: '_', 39: '@', 40: '3', 41: '4', 42: '$', 43: '5', 44: '%', 45: '6', 46: '^', 47: '7',
    48: '8', 49: '*', 50: '9', 51: '(', 52: '0', 53: 'q', 54: 'Q', 55: 'w', 56: 'W', 57: 'e', 58: 'E', 59: 'r',
    60: 't', 61: 'T', 62: 'y', 63: 'Y', 64: 'u', 65: 'i', 66: 'I', 67: 'o', 68: 'O', 69: 'p', 70: 'P', 71: 'a',
    72: 's', 73: 'S', 74: 'd', 75: 'D', 76: 'f', 77: 'g', 78: 'G', 79: 'h', 80: 'H', 81: 'j', 82: 'J', 83: 'k',
    84: 'l', 85: 'L', 86: 'z', 87: 'Z', 88: 'x', 89: 'c', 90: 'C', 91: 'v', 92: 'V', 93: 'b', 94: 'B', 95: 'n',
    96: 'm', 97: '_', 98: 'u', 99: '_', 100: 'o', 101: '_', 102: 's', 103: 'f', 104: 'h', 105: 'j', 106: '_'
}

# Maps characters that require the Shift key to their base key.
SHIFT_MAP: Dict[str, str] = {
    '!': '1', '@': '2', '$': '4', '%': '5', '^': '6', '*': '8', '(': '9', '_': '-', 'Q': 'q', 'W': 'w', 'E': 'e',
    'T': 't', 'Y': 'y', 'I': 'i', 'O': 'o', 'P': 'p', 'S': 's', 'D': 'd', 'G': 'g', 'H': 'h', 'J': 'j', 'L': 'l',
    'Z': 'z', 'C': 'c', 'V': 'v', 'B': 'b'
}

# Dark theme stylesheet for the application.
DARK_STYLESHEET: str = """
QWidget { font-size: 11px; color: #e0e0e0; background-color: #2d2d2d; }
QMainWindow { background-color: #2d2d2d; }
QGroupBox { font-weight: bold; background-color: #3c3c3c; border: 1px solid #555; border-radius: 6px; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; }
QPushButton { background-color: #555; border: 1px solid #666; padding: 6px; border-radius: 4px; }
QPushButton:hover { background-color: #6a6a6a; }
QPushButton:pressed { background-color: #4a4a4a; }
QPushButton:disabled { background-color: #444; color: #888; }
QProgressBar { border: 1px solid #555; border-radius: 4px; text-align: center; background-color: #444; }
QProgressBar::chunk { background-color: #0078d7; border-radius: 3px; }
QSlider::groove:horizontal { border: 1px solid #555; height: 4px; background: #444; margin: 2px 0; border-radius: 2px; }
QSlider::handle:horizontal { background: #0078d7; border: 1px solid #0078d7; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }
QLabel#statusLabel { color: #a0a0e0; font-style: italic; }
QTextEdit, QListWidget { background-color: #252525; border: 1px solid #555; border-radius: 4px; }
"""


# --- GUI WIDGETS ---

class PianoWidget(QWidget):
    """A custom widget to visualize a piano keyboard with velocity-sensitive colors."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.active_notes: Dict[int, int] = {}  # {note_number: velocity}
        self._key_rects: Dict[int, QRectF] = {}

    def set_active_notes(self, notes: Dict[int, int]):
        """Updates the set of currently active notes and triggers a repaint."""
        self.active_notes = notes
        self.update()

    def paintEvent(self, event):
        """Renders the piano keyboard."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1c1c1c"))

        min_note = min(NOTE_MAP.keys()) if NOTE_MAP else 0
        max_note = max(NOTE_MAP.keys()) if NOTE_MAP else 127

        white_keys = [k for k in range(min_note, max_note + 1) if k % 12 in [0, 2, 4, 5, 7, 9, 11] and k in NOTE_MAP]
        black_keys = [k for k in range(min_note, max_note + 1) if k % 12 in [1, 3, 6, 8, 10] and k in NOTE_MAP]

        if not white_keys:
            return

        white_key_width = self.width() / len(white_keys)
        black_key_height = self.height() * 0.6
        black_key_width = white_key_width * 0.6

        # Draw white keys first
        for i, note in enumerate(white_keys):
            rect = QRectF(i * white_key_width, 0, white_key_width, self.height())
            self._key_rects[note] = rect
            painter.setPen(Qt.black)
            if note in self.active_notes:
                velocity = self.active_notes[note]
                color = QColor.fromHsvF(212 / 360.0, min(1.0, 0.4 + velocity / 127.0), 1.0)
                painter.setBrush(color)
            else:
                painter.setBrush(Qt.white)
            painter.drawRect(rect)

        # Draw black keys on top
        white_key_index_map = {note: i for i, note in enumerate(white_keys)}
        prev_white_key_index = -1
        for note in range(min_note, max_note + 1):
            if note in white_keys:
                prev_white_key_index = white_key_index_map.get(note, prev_white_key_index)
            if note in black_keys and prev_white_key_index != -1:
                x_pos = prev_white_key_index * white_key_width + (white_key_width - black_key_width / 2)
                rect = QRectF(x_pos, 0, black_key_width, black_key_height)
                self._key_rects[note] = rect
                painter.setPen(Qt.black)
                if note in self.active_notes:
                    velocity = self.active_notes[note]
                    color = QColor.fromHsvF(212 / 360.0, min(1.0, 0.4 + velocity / 127.0), 1.0)
                    painter.setBrush(color)
                else:
                    painter.setBrush(Qt.black)
                painter.drawRect(rect)


# --- WORKER THREADS ---

class MidiLoadingThread(QThread):
    """
    A worker thread to load and parse a MIDI file without freezing the GUI.
    It pre-calculates the absolute timestamp for every event for high-accuracy playback.
    """
    loading_complete = pyqtSignal(object, dict)

    def __init__(self, midi_path: str):
        super().__init__()
        self.midi_path = midi_path

    def run(self):
        """
        Loads the MIDI file, merges tracks, and calculates precise event timestamps.
        Emits the file object and a dictionary of info upon completion.
        """
        try:
            mid = mido.MidiFile(self.midi_path, clip=True)
            events: List[Tuple[float, mido.Message]] = []
            absolute_time: float = 0.0
            ticks_per_beat: int = mid.ticks_per_beat if mid.ticks_per_beat > 0 else 480
            tempo: int = 500000  # Default MIDI tempo (120 BPM)

            # Merge all tracks into a single chronological stream of messages with time in ticks
            for msg in mido.merge_tracks(mid.tracks):
                # Convert message time delta from ticks to seconds using the current tempo
                delta_seconds = mido.tick2second(msg.time, ticks_per_beat, tempo)
                absolute_time += delta_seconds

                if msg.is_meta and msg.type == 'set_tempo':
                    tempo = msg.tempo
                
                if not msg.is_meta:
                    events.append((absolute_time, msg))
            
            note_count = sum(1 for _, msg in events if msg.type == 'note_on' and msg.velocity > 0)
            
            info = {
                "path": self.midi_path,
                "filename": self.midi_path.split('/')[-1],
                "track_count": len(mid.tracks),
                "note_count": note_count,
                "total_messages": len(events),
                "length": mid.length,
                "events": events
            }
            self.loading_complete.emit(mid, info)

        except Exception as e:
            self.loading_complete.emit(None, {"error": str(e)})


class MidiPlayerThread(QThread):
    """
    A high-accuracy playback engine that processes pre-calculated MIDI events.
    Uses a high-resolution clock and polling loop to minimize timing jitter.
    """
    progress_update = pyqtSignal(int)
    note_event = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    status_update = pyqtSignal(str)

    def __init__(self, midi_info: dict):
        super().__init__()
        self.events: List[Tuple[float, mido.Message]] = midi_info["events"]
        self.keyboard = Controller()
        self.is_running = True
        self.is_paused = False
        self.speed_multiplier = 1.0
        self.transpose = 0
        self.active_midi_notes: Dict[int, int] = {}
        self.pressed_keys: Dict[int, str] = {} # Tracks which keys are physically down

    def run(self):
        """
        Starts the high-resolution playback loop.
        """
        self.status_update.emit("Playback will start in 3 seconds... Switch to your target window.")
        time.sleep(3)
        self.status_update.emit("Playing...")

        start_time = time.perf_counter()
        event_index = 0
        pause_offset = 0.0

        while event_index < len(self.events) and self.is_running:
            if self.is_paused:
                pause_start_time = time.perf_counter()
                while self.is_paused and self.is_running:
                    time.sleep(0.01)
                pause_offset += (time.perf_counter() - pause_start_time)

            elapsed_time = time.perf_counter() - start_time - pause_offset
            song_time = elapsed_time / self.speed_multiplier

            timestamp, msg = self.events[event_index]

            if song_time >= timestamp:
                self.log_message.emit(f"@{timestamp:.4f}s: {msg}")
                self._process_midi_message(msg)
                self.progress_update.emit(event_index + 1)
                event_index += 1
            else:
                time.sleep(0.001)

        self._release_all_keys()
        self.finished.emit()
            
    def _process_midi_message(self, msg: mido.Message):
        """Handles a single MIDI message for keyboard simulation and visualization."""
        if not hasattr(msg, 'note'):
            return

        original_note = msg.note
        transposed_note = original_note + self.transpose
        
        visual_note = transposed_note if 0 <= transposed_note <= 127 else original_note
        simulation_note = original_note

        if msg.type == 'note_on' and msg.velocity > 0:
            self.active_midi_notes[visual_note] = msg.velocity
            self._press_key(simulation_note)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if visual_note in self.active_midi_notes:
                del self.active_midi_notes[visual_note]
            self._release_key(simulation_note)
        
        self.note_event.emit(self.active_midi_notes.copy())

    def _press_key(self, note: int):
        """Simulates a single key press with robust, atomic shift handling."""
        char_to_press = NOTE_MAP.get(note)
        if not char_to_press or note in self.pressed_keys:
            return

        try:
            if char_to_press in SHIFT_MAP:
                with self.keyboard.pressed(Key.shift):
                    self.keyboard.press(SHIFT_MAP[char_to_press])
                self.pressed_keys[note] = SHIFT_MAP[char_to_press]
            else:
                self.keyboard.press(char_to_press)
                self.pressed_keys[note] = char_to_press
        except Exception as e:
            self.log_message.emit(f"Error pressing key for note {note}: {e}")

    def _release_key(self, note: int):
        """Simulates a single key release."""
        if note in self.pressed_keys:
            base_key_to_release = self.pressed_keys.pop(note)
            try:
                self.keyboard.release(base_key_to_release)
            except Exception as e:
                self.log_message.emit(f"Error releasing key '{base_key_to_release}': {e}")

    def stop(self):
        self.is_running = False

    def pause(self):
        self.is_paused = True
        self.status_update.emit("Playback paused.")

    def resume(self):
        self.is_paused = False
        self.status_update.emit("Resuming playback...")
    
    def _release_all_keys(self):
        """Releases any lingering keys upon stopping."""
        for base_key in self.pressed_keys.values():
            try:
                self.keyboard.release(base_key)
            except Exception:
                pass
        # Just in case shift was stuck from an error
        try:
            self.keyboard.release(Key.shift)
        except Exception:
            pass

        self.pressed_keys.clear()
        self.active_midi_notes.clear()
        self.note_event.emit(self.active_midi_notes.copy())


class MidiInputThread(QThread):
    """A worker thread to listen for incoming MIDI messages from a connected device."""
    note_event = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    
    def __init__(self, port_name: str):
        super().__init__()
        self.port_name = port_name
        self.is_running = True
        self.active_notes: Dict[int, int] = {}

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
                    elif msg.type in ('note_off', 'note_on') and msg.note in self.active_notes:
                        del self.active_notes[msg.note]
                    
                    self.note_event.emit(self.active_notes.copy())
        except Exception as e:
            self.log_message.emit(f"Error with MIDI input: {e}")
        
        self.active_notes.clear()
        self.note_event.emit(self.active_notes.copy())
        self.log_message.emit(f"Stopped listening on {self.port_name}")

    def stop(self):
        self.is_running = False


# --- MAIN APPLICATION ---

class MidiKeyboardApp(QMainWindow):
    """The main application window for the Advanced MIDI Keyboard Simulator."""

    def __init__(self):
        super().__init__()
        self.midi_infos: Dict[str, dict] = {}
        self.player_thread: Optional[MidiPlayerThread] = None
        self.loading_thread: Optional[MidiLoadingThread] = None
        self.input_thread: Optional[MidiInputThread] = None
        self._init_ui()

    def _init_ui(self):
        """Initializes the entire user interface."""
        self.setWindowTitle('Advanced MIDI Keyboard Simulator')
        self.setGeometry(100, 100, 950, 650)
        self.setStyleSheet(DARK_STYLESHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
        
        self._create_status_bar()
        self.update_button_states()
        self.show()

    def _create_left_panel(self) -> QWidget:
        """Creates the left panel containing all control widgets."""
        layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(layout)

        layout.addWidget(self._create_playlist_group())
        layout.addWidget(self._create_controls_group())
        layout.addWidget(self._create_transform_group())
        layout.addWidget(self._create_input_group())
        
        return widget

    def _create_right_panel(self) -> QWidget:
        """Creates the right panel containing visualization widgets."""
        layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(layout)

        piano_group = QGroupBox("Visualizer")
        piano_layout = QVBoxLayout()
        self.piano_widget = PianoWidget()
        piano_layout.addWidget(self.piano_widget)
        piano_group.setLayout(piano_layout)

        log_group = QGroupBox("Real-time MIDI Event Log")
        log_layout = QVBoxLayout()
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)
        log_group.setLayout(log_layout)

        layout.addWidget(piano_group, 2)
        layout.addWidget(log_group, 1)
        
        return widget

    def _create_playlist_group(self) -> QGroupBox:
        group = QGroupBox("Playlist")
        layout = QVBoxLayout()
        
        self.playlist_widget = QListWidget()
        self.playlist_widget.itemDoubleClicked.connect(self.play_midi)
        
        buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Files")
        self.remove_button = QPushButton("Remove")
        self.clear_button = QPushButton("Clear")
        
        self.add_button.clicked.connect(self.add_files_to_playlist)
        self.remove_button.clicked.connect(self.remove_selected_from_playlist)
        self.clear_button.clicked.connect(self.clear_playlist)
        
        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.remove_button)
        buttons_layout.addWidget(self.clear_button)
        
        layout.addWidget(self.playlist_widget)
        layout.addLayout(buttons_layout)
        group.setLayout(layout)
        return group

    def _create_controls_group(self) -> QGroupBox:
        group = QGroupBox("Playback Controls")
        layout = QGridLayout()

        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        
        self.play_button.clicked.connect(self.play_midi)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.stop_button.clicked.connect(self.stop_midi)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.speed_changed)
        
        speed_value = self.speed_slider.value() / 100.0
        self.speed_label = QLabel(f"Speed: {speed_value:.2f}x")
        
        layout.addLayout(button_layout, 0, 0, 1, 2)
        layout.addWidget(self.progress_bar, 1, 0, 1, 2)
        layout.addWidget(self.speed_label, 2, 0)
        layout.addWidget(self.speed_slider, 2, 1)
        group.setLayout(layout)
        return group

    def _create_transform_group(self) -> QGroupBox:
        group = QGroupBox("Real-time Transformation")
        layout = QFormLayout()
        
        self.transpose_spinbox = QSpinBox()
        self.transpose_spinbox.setRange(-24, 24)
        self.transpose_spinbox.setValue(0)
        self.transpose_spinbox.valueChanged.connect(self.transpose_changed)
        
        layout.addRow("Transpose (Semitones):", self.transpose_spinbox)
        group.setLayout(layout)
        return group

    def _create_input_group(self) -> QGroupBox:
        group = QGroupBox("MIDI Input")
        layout = QHBoxLayout()
        
        self.midi_input_combo = QComboBox()
        try:
            self.midi_input_combo.addItems(mido.get_input_names())
        except Exception as e:
            print(f"Could not get MIDI devices: {e}")

        self.connect_button = QPushButton("Connect")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_midi_input)
        
        layout.addWidget(self.midi_input_combo)
        layout.addWidget(self.connect_button)
        group.setLayout(layout)
        return group

    def _create_status_bar(self):
        self.status_label = QLabel("Welcome! Please add MIDI files to the playlist.")
        self.status_label.setObjectName("statusLabel")
        self.statusBar().addPermanentWidget(self.status_label, 1)

    def add_files_to_playlist(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add MIDI Files", "", "MIDI Files (*.mid *.midi)")
        for file_path in files:
            if file_path and not self.playlist_widget.findItems(file_path, Qt.MatchExactly):
                self.playlist_widget.addItem(QListWidgetItem(file_path))
        self.update_button_states()

    def remove_selected_from_playlist(self):
        for item in self.playlist_widget.selectedItems():
            path = item.text()
            if path in self.midi_infos:
                del self.midi_infos[path]
            self.playlist_widget.takeItem(self.playlist_widget.row(item))
        self.update_button_states()

    def clear_playlist(self):
        self.playlist_widget.clear()
        self.midi_infos.clear()
        self.update_button_states()

    def play_midi(self):
        current_item = self.playlist_widget.currentItem()
        if not current_item and self.playlist_widget.count() > 0:
            self.playlist_widget.setCurrentRow(0)
            current_item = self.playlist_widget.item(0)
        
        if not current_item:
            self.status_label.setText("Playlist is empty.")
            return

        file_path = current_item.text()
        if file_path in self.midi_infos:
            self.start_playback(self.midi_infos[file_path])
        else:
            self.status_label.setText(f"Loading {file_path.split('/')[-1]}...")
            self.set_controls_enabled(False)
            self.loading_thread = MidiLoadingThread(file_path)
            self.loading_thread.loading_complete.connect(self.on_loading_finished_and_play)
            self.loading_thread.start()

    def on_loading_finished_and_play(self, mid_obj, info: dict):
        self.set_controls_enabled(True)
        if mid_obj:
            self.midi_infos[info["path"]] = info
            self.start_playback(info)
        else:
            self.status_label.setText(f"Error loading file: {info.get('error', 'Unknown error')}")

    def start_playback(self, midi_info: dict):
        if self.input_thread and self.input_thread.isRunning():
            self.toggle_midi_input(False)
        
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()

        self.player_thread = MidiPlayerThread(midi_info)
        self.progress_bar.setMaximum(midi_info["total_messages"])
        
        # Connect signals
        self.player_thread.progress_update.connect(self.progress_bar.setValue)
        self.player_thread.note_event.connect(self.piano_widget.set_active_notes)
        self.player_thread.log_message.connect(self.append_to_log)
        self.player_thread.finished.connect(self.on_playback_finished)
        self.player_thread.status_update.connect(self.status_label.setText)
        
        # Set initial parameters
        self.player_thread.speed_multiplier = 1.0 / (self.speed_slider.value() / 100.0) # Invert for calculation
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

    def on_playback_finished(self, is_stopped: bool = False):
        self.status_label.setText("Playback stopped by user." if is_stopped else "Playback finished.")
        self.progress_bar.setValue(0)
        self.piano_widget.set_active_notes({})
        self.pause_button.setText("Pause")
        self.update_button_states()

    def speed_changed(self, value: int):
        speed = value / 100.0
        self.speed_label.setText(f"Speed: {speed:.2f}x")
        if self.player_thread and self.player_thread.isRunning():
            # Invert the multiplier for the calculation (e.g., 2x speed means dividing time by 2)
            self.player_thread.speed_multiplier = 1.0 / speed

    def transpose_changed(self, value: int):
        self.status_label.setText(f"Transposition set to {value} semitones.")
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.transpose = value

    def append_to_log(self, message: str):
        self.log_edit.append(message)
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def toggle_midi_input(self, checked: bool):
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
            self.piano_widget.set_active_notes({})

    def update_button_states(self):
        is_playlist_non_empty = self.playlist_widget.count() > 0
        is_playing = bool(self.player_thread and self.player_thread.isRunning())
        
        self.play_button.setEnabled(is_playlist_non_empty and not is_playing)
        self.pause_button.setEnabled(is_playing)
        self.stop_button.setEnabled(is_playing)
        
        self.set_controls_enabled(not is_playing)

    def set_controls_enabled(self, enabled: bool):
        """Helper to enable/disable controls that shouldn't be used during playback."""
        self.playlist_widget.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled and self.playlist_widget.currentItem() is not None)
        self.clear_button.setEnabled(enabled and self.playlist_widget.count() > 0)

    def closeEvent(self, event):
        """Ensures all threads are stopped before closing the application."""
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop()
            self.player_thread.wait()
        if self.input_thread and self.input_thread.isRunning():
            self.input_thread.stop()
            self.input_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MidiKeyboardApp()
    sys.exit(app.exec_())