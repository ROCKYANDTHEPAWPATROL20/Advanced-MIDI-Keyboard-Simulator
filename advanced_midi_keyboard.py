import sys
import time
import collections
from typing import Dict, List, Tuple, Optional

import mido
from pynput.keyboard import Controller, Key
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRectF, QEvent
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QClipboard
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                             QLabel, QFileDialog, QProgressBar, QSlider, QGridLayout,
                             QGroupBox, QMainWindow, QFormLayout, QTextEdit, QListWidget,
                             QComboBox, QSpinBox, QListWidgetItem, QDialog, QTableWidget,
                             QTableWidgetItem, QAbstractItemView, QDialogButtonBox,
                             QHeaderView, QTabWidget)

# --- APPLICATION CONSTANTS ---

# Default mapping of MIDI note numbers to keyboard characters.
DEFAULT_NOTE_MAP: Dict[int, str] = {
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
QTextEdit, QListWidget, QTableWidget { background-color: #252525; border: 1px solid #555; border-radius: 4px; }
QHeaderView::section { background-color: #3c3c3c; border: 1px solid #555; padding: 4px; }
QTabWidget::pane { border: 1px solid #555; }
QTabBar::tab { background: #3c3c3c; padding: 6px; border: 1px solid #555; border-bottom: none; }
QTabBar::tab:selected { background: #555; }
"""

def note_number_to_name(note_number: int) -> str:
    if not (0 <= note_number <= 127): return "Invalid"
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note_number // 12) - 1
    return f"{notes[note_number % 12]}{octave}"


# --- GUI WIDGETS ---

class PianoRollWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.midi_info: Optional[dict] = None
        self.current_time: float = 0.0
        self.active_notes: Dict[int, int] = {}
        self.time_window_seconds: float = 4.0
        self.note_rects: Dict[int, QRectF] = {}
        self.white_note_color = QColor("#0078d7")
        self.black_note_color = QColor("#4cc2ff")
        self.highlight_color = QColor("#ffc107")

    def set_midi_info(self, info: Optional[dict]): self.midi_info = info; self.update()
    def set_current_time(self, song_time: float): self.current_time = song_time; self.update()
    def set_active_notes(self, notes: Dict[int, int]): self.active_notes = notes; self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1c1c1c"))
        min_note, max_note = 21, 108
        white_keys = {k for k in range(min_note, max_note + 1) if k % 12 in [0, 2, 4, 5, 7, 9, 11]}
        if not (num_white_keys := len(white_keys)): return
        white_key_width = self.width() / num_white_keys
        keyboard_height, roll_height = 80, self.height() - 80
        if self.midi_info:
            for start_time, duration, msg in self.midi_info.get("notes", []):
                if start_time > self.current_time + self.time_window_seconds or start_time + duration < self.current_time: continue
                if (note := msg.note) not in self.note_rects: continue
                key_rect = self.note_rects[note]
                start_y = ((start_time - self.current_time) / self.time_window_seconds) * roll_height
                end_y = ((start_time + duration - self.current_time) / self.time_window_seconds) * roll_height
                note_height = max(1.0, end_y - start_y)
                note_y = roll_height - start_y - note_height
                color = self.white_note_color if note in white_keys else self.black_note_color
                painter.setBrush(color); painter.setPen(Qt.black)
                painter.drawRect(QRectF(key_rect.x(), note_y, key_rect.width(), note_height))
        black_key_height, black_key_width = keyboard_height * 0.6, white_key_width * 0.6
        white_key_counter = 0
        for note in range(min_note, max_note + 1):
            if note in white_keys:
                key_x = white_key_counter * white_key_width
                self.note_rects[note] = QRectF(key_x, 0, white_key_width, roll_height)
                painter.setPen(Qt.black); painter.setBrush(self.highlight_color if note in self.active_notes else Qt.white)
                painter.drawRect(int(key_x), int(roll_height), int(white_key_width), int(keyboard_height))
                white_key_counter += 1
        white_key_counter = 0
        for note in range(min_note, max_note + 1):
            if note in white_keys: white_key_counter += 1; continue
            prev_note_x = (white_key_counter - 1) * white_key_width
            key_x = prev_note_x + white_key_width - (black_key_width / 2)
            self.note_rects[note] = QRectF(key_x, 0, black_key_width, roll_height)
            painter.setPen(Qt.black); painter.setBrush(self.highlight_color if note in self.active_notes else Qt.black)
            painter.drawRect(int(key_x), int(roll_height), int(black_key_width), int(black_key_height))


class StatisticsWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent); layout = QFormLayout(self)
        self.labels = { "note_count": QLabel("N/A"), "duration": QLabel("N/A"), "density": QLabel("N/A"), "highest_note": QLabel("N/A"),
                        "lowest_note": QLabel("N/A"), "common_note": QLabel("N/A"), "velocity_range": QLabel("N/A"), "avg_velocity": QLabel("N/A") }
        for key, text in [("note_count", "Total Notes:"), ("duration", "Duration:"), ("density", "Avg. Notes/Sec:"), ("highest_note", "Highest Note:"),
                           ("lowest_note", "Lowest Note:"), ("common_note", "Most Common Note:"), ("velocity_range", "Velocity Range:"), ("avg_velocity", "Average Velocity:")]:
            layout.addRow(text, self.labels[key])
    def update_stats(self, stats: dict):
        self.labels["note_count"].setText(str(stats.get("note_count", "N/A")))
        duration = stats.get("duration", 0); self.labels["duration"].setText(f"{int(duration // 60):02d}:{int(duration % 60):02d}")
        self.labels["density"].setText(f"{stats.get('density', 0):.2f}")
        self.labels["highest_note"].setText(note_number_to_name(stats.get("highest_note", 0)))
        self.labels["lowest_note"].setText(note_number_to_name(stats.get("lowest_note", 127)))
        self.labels["common_note"].setText(note_number_to_name(stats.get("common_note", 0)))
        self.labels["velocity_range"].setText(f"{stats.get('min_velocity', 0)} - {stats.get('max_velocity', 0)}")
        self.labels["avg_velocity"].setText(str(int(stats.get('avg_velocity', 0))))
    def clear(self):
        for label in self.labels.values(): label.setText("N/A")

# --- WORKER THREADS ---

class MidiLoadingThread(QThread):
    loading_complete = pyqtSignal(dict)
    def __init__(self, midi_path: str): super().__init__(); self.midi_path = midi_path
    def run(self):
        try:
            mid = mido.MidiFile(self.midi_path, clip=True); events, notes, has_sustain = [], [], False
            absolute_time, ticks_per_beat, tempo = 0.0, mid.ticks_per_beat if mid.ticks_per_beat > 0 else 480, 500000
            for msg in mido.merge_tracks(mid.tracks):
                absolute_time += mido.tick2second(msg.time, ticks_per_beat, tempo)
                if msg.is_meta and msg.type == 'set_tempo': tempo = msg.tempo
                if not msg.is_meta:
                    events.append((absolute_time, msg))
                    if msg.type == 'control_change' and msg.control == 64: has_sustain = True
            open_notes, all_velocities, note_counter = {}, [], collections.Counter()
            for t, msg in events:
                if msg.type == 'note_on' and msg.velocity > 0: open_notes[msg.note] = (t, msg)
                elif msg.type in ('note_off', 'note_on') and msg.note in open_notes:
                    start_time, start_msg = open_notes.pop(msg.note)
                    if (duration := t - start_time) > 0:
                        notes.append((start_time, duration, start_msg))
                        all_velocities.append(start_msg.velocity); note_counter[start_msg.note] += 1
            stats = {}
            if (note_events := [n for _, _, n in notes]):
                stats = {"note_count": len(note_events), "duration": absolute_time, "density": len(note_events) / absolute_time if absolute_time > 0 else 0,
                         "highest_note": max(n.note for n in note_events), "lowest_note": min(n.note for n in note_events),
                         "common_note": note_counter.most_common(1)[0][0], "min_velocity": min(all_velocities),
                         "max_velocity": max(all_velocities), "avg_velocity": sum(all_velocities) / len(all_velocities)}
            self.loading_complete.emit({"path": self.midi_path, "filename": self.midi_path.split('/')[-1], "events": events, "notes": notes, "stats": stats, "has_sustain": has_sustain})
        except Exception as e: self.loading_complete.emit({"error": str(e)})


class MidiPlayerThread(QThread):
    progress_update, time_update, note_event, log_message = pyqtSignal(int), pyqtSignal(float), pyqtSignal(dict), pyqtSignal(str)
    finished, status_update = pyqtSignal(), pyqtSignal(str)
    def __init__(self, midi_info: dict, note_map: Dict[int, str]):
        super().__init__()
        self.events, self.note_map, self.default_sustain_on = midi_info["events"], note_map, not midi_info["has_sustain"]
        self.keyboard = Controller()
        self.is_running, self.is_paused, self.speed_multiplier, self.transpose = True, False, 1.0, 0
        self.active_notes, self.pressed_keys, self.is_space_pressed = {}, {}, False
    def run(self):
        for i in range(3, 0, -1):
            if not self.is_running: self.finished.emit(); return
            self.status_update.emit(f"Playback will start in {i}..."); time.sleep(1)
        if not self.is_running: self.finished.emit(); return
        
        self.status_update.emit("Playing...");
        if self.default_sustain_on: self._release_space()
        start_time, event_index, pause_offset = time.perf_counter(), 0, 0.0
        while event_index < len(self.events) and self.is_running:
            if self.is_paused:
                pause_start_time = time.perf_counter()
                while self.is_paused and self.is_running: time.sleep(0.01)
                pause_offset += (time.perf_counter() - pause_start_time)
            
            song_time = (time.perf_counter() - start_time - pause_offset) / self.speed_multiplier
            self.time_update.emit(song_time)
            
            timestamp, msg = self.events[event_index]
            
            while song_time < timestamp:
                if not self.is_running: break
                song_time = (time.perf_counter() - start_time - pause_offset) / self.speed_multiplier
            if not self.is_running: break

            self.log_message.emit(f"@{timestamp:.4f}s: {msg}"); self._process_midi_message(msg)
            self.progress_update.emit(event_index + 1); event_index += 1
            
        self._release_all_keys(); self.finished.emit()
    def _process_midi_message(self, msg: mido.Message):
        if msg.type == 'control_change' and msg.control == 64:
            if msg.value >= 64: self._release_space()
            else: self._press_space()
        elif hasattr(msg, 'note'):
            visual_note = msg.note + self.transpose
            if msg.type == 'note_on' and msg.velocity > 0: self.active_notes[visual_note] = msg.velocity; self._press_key(msg.note)
            elif msg.type in ('note_off', 'note_on'):
                if visual_note in self.active_notes: del self.active_notes[visual_note]
                self._release_key(msg.note)
            self.note_event.emit(self.active_notes.copy())
    def _press_key(self, note: int):
        char = self.note_map.get(note)
        if not char or note in self.pressed_keys: return
        try:
            if char in SHIFT_MAP:
                with self.keyboard.pressed(Key.shift): self.keyboard.press(SHIFT_MAP[char])
                self.pressed_keys[note] = SHIFT_MAP[char]
            else: self.keyboard.press(char); self.pressed_keys[note] = char
        except: pass
    def _release_key(self, note: int):
        if note in self.pressed_keys:
            try: self.keyboard.release(self.pressed_keys.pop(note))
            except: pass
    def _press_space(self):
        if not self.is_space_pressed:
            try: self.keyboard.press(Key.space); self.is_space_pressed = True
            except: pass
    def _release_space(self):
        if self.is_space_pressed:
            try: self.keyboard.release(Key.space); self.is_space_pressed = False
            except: pass
    def stop(self): self.is_running = False
    def pause(self): self.is_paused = True; self.status_update.emit("Playback paused.")
    def resume(self): self.is_paused = False; self.status_update.emit("Resuming playback...")
    def _release_all_keys(self):
        for key in self.pressed_keys.values():
            try: self.keyboard.release(key)
            except: pass
        try: self.keyboard.release(Key.shift); self._release_space()
        except: pass
        self.pressed_keys.clear(); self.active_notes.clear(); self.note_event.emit({})


class MidiInputThread(QThread):
    note_event, log_message = pyqtSignal(dict), pyqtSignal(str)
    def __init__(self, port_name: str): super().__init__(); self.port_name, self.is_running, self.active_notes = port_name, True, {}
    def run(self):
        try:
            with mido.open_input(self.port_name) as port:
                self.log_message.emit(f"Listening on: {self.port_name}")
                for msg in port:
                    if not self.is_running: break
                    self.log_message.emit(str(msg))
                    if msg.type == 'note_on' and msg.velocity > 0: self.active_notes[msg.note] = msg.velocity
                    elif msg.type in ('note_off', 'note_on') and msg.note in self.active_notes: del self.active_notes[msg.note]
                    self.note_event.emit(self.active_notes.copy())
        except Exception as e: self.log_message.emit(f"MIDI Input Error: {e}")
        self.active_notes.clear(); self.note_event.emit({}); self.log_message.emit("Stopped listening.")
    def stop(self): self.is_running = False


# --- MAIN APPLICATION ---

class MidiKeyboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.note_map = DEFAULT_NOTE_MAP.copy()
        self.midi_infos: Dict[str, dict] = {}
        self.player_thread: Optional[MidiPlayerThread] = None
        self.loading_threads: List[MidiLoadingThread] = []
        self.input_thread: Optional[MidiInputThread] = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle('Advanced MIDI Keyboard Simulator'); self.setGeometry(100, 100, 1050, 700); self.setStyleSheet(DARK_STYLESHEET)
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.addWidget(self._create_left_panel(), 1); main_layout.addWidget(self._create_right_panel(), 2)
        self._create_status_bar(); self.update_button_states(); self.show()

    def _create_left_panel(self) -> QWidget:
        layout, widget = QVBoxLayout(), QWidget(); widget.setLayout(layout)
        layout.addWidget(self._create_playlist_group()); layout.addWidget(self._create_controls_group())
        layout.addWidget(self._create_transform_group()); layout.addWidget(self._create_input_group())
        return widget

    def _create_right_panel(self) -> QWidget:
        layout, widget = QVBoxLayout(), QWidget(); widget.setLayout(layout)
        piano_group = QGroupBox("Visualizer"); piano_layout = QVBoxLayout()
        self.piano_roll_widget = PianoRollWidget()
        piano_layout.addWidget(self.piano_roll_widget); piano_group.setLayout(piano_layout)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_log_widget(), "MIDI Event Log")
        self.tabs.addTab(self._create_stats_widget(), "Statistics")
        self.text_mapping_widget = self._create_text_mapping_widget() # Create and store the new widget
        self.tabs.addTab(self.text_mapping_widget, "Text Mapping")

        layout.addWidget(piano_group, 2); layout.addWidget(self.tabs, 1)
        return widget

    def _create_playlist_group(self) -> QGroupBox:
        group = QGroupBox("Playlist"); layout = QVBoxLayout()
        self.playlist_widget = QListWidget(); self.playlist_widget.itemSelectionChanged.connect(self.on_playlist_selection_changed)
        
        buttons_layout_top = QHBoxLayout()
        self.add_button, self.remove_button, self.clear_button = QPushButton("Add Files"), QPushButton("Remove"), QPushButton("Clear")
        self.add_button.clicked.connect(self.add_files_to_playlist)
        self.remove_button.clicked.connect(self.remove_selected_from_playlist)
        self.clear_button.clicked.connect(self.clear_playlist)
        buttons_layout_top.addWidget(self.add_button); buttons_layout_top.addWidget(self.remove_button); buttons_layout_top.addWidget(self.clear_button)
        
        self.generate_button = QPushButton("Generate & View Text")
        self.generate_button.clicked.connect(self.generate_and_display_text)

        layout.addWidget(self.playlist_widget)
        layout.addLayout(buttons_layout_top)
        layout.addWidget(self.generate_button)
        group.setLayout(layout)
        return group

    def _create_controls_group(self) -> QGroupBox:
        group = QGroupBox("Playback Controls"); layout = QGridLayout()
        self.play_button, self.pause_button, self.stop_button = QPushButton("Play"), QPushButton("Pause"), QPushButton("Stop")
        self.play_button.clicked.connect(self.play_midi); self.pause_button.clicked.connect(self.toggle_pause); self.stop_button.clicked.connect(self.stop_midi)
        button_layout = QHBoxLayout(); button_layout.addWidget(self.play_button); button_layout.addWidget(self.pause_button); button_layout.addWidget(self.stop_button)
        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(False)
        self.speed_slider = QSlider(Qt.Horizontal); self.speed_slider.setRange(50, 200); self.speed_slider.setValue(100); self.speed_slider.valueChanged.connect(self.speed_changed)
        self.speed_label = QLabel(f"Speed: {self.speed_slider.value() / 100.0:.2f}x")
        layout.addLayout(button_layout, 0, 0, 1, 2); layout.addWidget(self.progress_bar, 1, 0, 1, 2); layout.addWidget(self.speed_label, 2, 0); layout.addWidget(self.speed_slider, 2, 1)
        group.setLayout(layout)
        return group
    
    def _create_transform_group(self) -> QGroupBox:
        group = QGroupBox("Options"); layout = QFormLayout()
        self.transpose_spinbox = QSpinBox(); self.transpose_spinbox.setRange(-24, 24); self.transpose_spinbox.setValue(0); self.transpose_spinbox.valueChanged.connect(self.transpose_changed)
        self.edit_map_button = QPushButton("Edit Key Map"); self.edit_map_button.clicked.connect(self.open_key_map_editor)
        layout.addRow("Transpose (Semitones):", self.transpose_spinbox); layout.addRow(self.edit_map_button)
        group.setLayout(layout)
        return group

    def _create_input_group(self) -> QGroupBox:
        group = QGroupBox("MIDI Input"); layout = QHBoxLayout()
        self.midi_input_combo = QComboBox(); self.connect_button = QPushButton("Connect"); self.connect_button.setCheckable(True)
        try: self.midi_input_combo.addItems(mido.get_input_names())
        except: pass
        self.connect_button.clicked.connect(self.toggle_midi_input)
        layout.addWidget(self.midi_input_combo); layout.addWidget(self.connect_button); group.setLayout(layout)
        return group

    def _create_log_widget(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.log_edit = QTextEdit(); self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit); layout.setContentsMargins(0,0,0,0)
        return widget
    
    def _create_stats_widget(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.stats_display = StatisticsWidget()
        layout.addWidget(self.stats_display); layout.setContentsMargins(0,0,0,0)
        return widget

    def _create_text_mapping_widget(self) -> QWidget:
        """Creates the widget for the 'Text Mapping' tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.mapping_text_edit = QTextEdit()
        self.mapping_text_edit.setReadOnly(True)
        self.mapping_text_edit.setFont(QFont("Courier", 10))
        
        buttons_layout = QHBoxLayout()
        copy_button = QPushButton("Copy to Clipboard")
        save_button = QPushButton("Save to File...")
        copy_button.clicked.connect(self.copy_mapping_to_clipboard)
        save_button.clicked.connect(self.save_mapping_to_file)
        buttons_layout.addStretch() # Pushes buttons to the right
        buttons_layout.addWidget(copy_button)
        buttons_layout.addWidget(save_button)
        
        layout.addWidget(self.mapping_text_edit)
        layout.addLayout(buttons_layout)
        layout.setContentsMargins(0,0,0,0)
        
        return widget

    def _create_status_bar(self):
        self.status_label = QLabel("Welcome!"); self.status_label.setObjectName("statusLabel")
        self.statusBar().addPermanentWidget(self.status_label, 1)

    def add_files_to_playlist(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add MIDI Files", "", "MIDI Files (*.mid *.midi)")
        if not files: return
        self.set_controls_enabled(False); self.status_label.setText(f"Loading {len(files)} file(s)...")
        for file_path in files:
            if file_path not in self.midi_infos:
                thread = MidiLoadingThread(file_path)
                thread.loading_complete.connect(self.on_file_loaded)
                thread.finished.connect(lambda t=thread: self.loading_threads.remove(t) if t in self.loading_threads else None)
                thread.finished.connect(self.update_button_states)
                self.loading_threads.append(thread)
                thread.start()

    def on_file_loaded(self, info: dict):
        if "error" in info: self.status_label.setText(f"Error loading file: {info['error']}")
        else:
            path, filename = info["path"], info["filename"]
            self.midi_infos[path] = info
            item = QListWidgetItem(filename); item.setData(Qt.UserRole, path)
            self.playlist_widget.addItem(item)
            self.status_label.setText(f"Loaded: {filename}")
        if not self.loading_threads: self.update_button_states()

    def on_playlist_selection_changed(self):
        item = self.playlist_widget.currentItem()
        self.piano_roll_widget.set_midi_info(None); self.stats_display.clear()
        self.mapping_text_edit.clear() # Clear the text mapping on selection change
        if item and (path := item.data(Qt.UserRole)) in self.midi_infos:
            info = self.midi_infos[path]
            self.piano_roll_widget.set_midi_info(info); self.stats_display.update_stats(info["stats"])
        self.update_button_states()

    def remove_selected_from_playlist(self):
        if not (item := self.playlist_widget.currentItem()): return
        if (path := item.data(Qt.UserRole)) in self.midi_infos: del self.midi_infos[path]
        self.playlist_widget.takeItem(self.playlist_widget.row(item)); self.update_button_states()

    def clear_playlist(self):
        self.playlist_widget.clear(); self.midi_infos.clear()
        self.piano_roll_widget.set_midi_info(None); self.stats_display.clear(); self.update_button_states()

    def play_midi(self):
        if not (item := self.playlist_widget.currentItem()):
            if self.playlist_widget.count() > 0:
                self.playlist_widget.setCurrentRow(0)
                item = self.playlist_widget.currentItem()
            else:
                self.status_label.setText("Playlist is empty."); return
        if (path := item.data(Qt.UserRole)) in self.midi_infos: self.start_playback(self.midi_infos[path])

    def start_playback(self, midi_info: dict):
        if self.input_thread: self.toggle_midi_input(False)
        if self.player_thread and self.player_thread.isRunning(): self.player_thread.stop(); self.player_thread.wait()
        self.player_thread = MidiPlayerThread(midi_info, self.note_map)
        self.progress_bar.setMaximum(len(midi_info["events"]))
        self.player_thread.progress_update.connect(self.progress_bar.setValue); self.player_thread.time_update.connect(self.piano_roll_widget.set_current_time)
        self.player_thread.note_event.connect(self.piano_roll_widget.set_active_notes)
        self.player_thread.log_message.connect(self.append_to_log); self.player_thread.finished.connect(self.on_playback_finished); self.player_thread.status_update.connect(self.status_label.setText)
        self.player_thread.speed_multiplier = 1.0 / (self.speed_slider.value() / 100.0)
        self.player_thread.transpose = self.transpose_spinbox.value()
        self.player_thread.start(); self.update_button_states()
    
    def generate_and_display_text(self):
        """Generates the mapping string and shows it in the Text Mapping tab."""
        current_item = self.playlist_widget.currentItem()
        if not current_item:
            self.status_label.setText("Please select a file to generate text from.")
            return

        midi_path = current_item.data(Qt.UserRole)
        midi_info = self.midi_infos.get(midi_path)
        if not midi_info:
            self.status_label.setText("Could not find loaded data for the selected file.")
            return
        
        self.status_label.setText(f"Generating text for {midi_info['filename']}...")
        QApplication.processEvents()

        try:
            # Group notes by their start time
            notes_by_time = collections.defaultdict(list)
            for timestamp, msg in midi_info['events']:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes_by_time[timestamp].append(msg.note)
            
            # Build the output string
            output_parts = []
            for timestamp in sorted(notes_by_time.keys()):
                mapped_chars = [self.note_map.get(note) for note in notes_by_time[timestamp] if note in self.note_map]
                if not mapped_chars: continue
                
                if len(mapped_chars) == 1:
                    output_parts.append(mapped_chars[0])
                else:
                    output_parts.append(f"[{''.join(sorted(mapped_chars))}]")
            
            final_text = " ".join(output_parts)
            self.mapping_text_edit.setText(final_text)
            self.tabs.setCurrentWidget(self.text_mapping_widget) # Switch to the tab
            self.status_label.setText("Text generation complete.")
        except Exception as e:
            self.status_label.setText(f"An error occurred during text generation: {e}")

    def copy_mapping_to_clipboard(self):
        """Copies the content of the mapping text edit to the clipboard."""
        text = self.mapping_text_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText("Generated text copied to clipboard.")
        else:
            self.status_label.setText("Nothing to copy.")
            
    def save_mapping_to_file(self):
        """Saves the content of the mapping text edit to a file."""
        text_to_save = self.mapping_text_edit.toPlainText()
        if not text_to_save:
            self.status_label.setText("Nothing to save.")
            return
        
        # Suggest a filename based on the selected MIDI
        current_item = self.playlist_widget.currentItem()
        default_name = "mapping.txt"
        if current_item:
            midi_path = current_item.data(Qt.UserRole)
            default_name = midi_path.rsplit('.', 1)[0] + "_mapping.txt"

        output_path, _ = QFileDialog.getSaveFileName(self, "Save Mapping File", default_name, "Text Files (*.txt)")
        
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text_to_save)
                self.status_label.setText(f"Successfully saved file: {output_path.split('/')[-1]}")
            except Exception as e:
                self.status_label.setText(f"Error saving file: {e}")

    def toggle_pause(self):
        if self.player_thread and self.player_thread.isRunning():
            if self.player_thread.is_paused: self.player_thread.resume(); self.pause_button.setText("Pause")
            else: self.player_thread.pause(); self.pause_button.setText("Resume")

    def stop_midi(self):
        if self.player_thread and self.player_thread.isRunning():
            self.player_thread.stop(); self.player_thread.wait(); self.on_playback_finished(is_stopped=True)

    def on_playback_finished(self, is_stopped: bool = False):
        if not is_stopped and (current_item := self.playlist_widget.currentItem()):
            next_row = self.playlist_widget.row(current_item) + 1
            if next_row < self.playlist_widget.count():
                self.status_label.setText("Finished. Starting next song...")
                self.playlist_widget.setCurrentRow(next_row)
                QApplication.processEvents(); time.sleep(0.5)
                self.play_midi()
                return
        self.status_label.setText("Playback stopped." if is_stopped else "Playlist finished.")
        self.progress_bar.setValue(0); self.pause_button.setText("Pause")
        self.piano_roll_widget.set_current_time(0); self.piano_roll_widget.set_active_notes({})
        self.update_button_states()

    def speed_changed(self, value: int):
        speed = value / 100.0; self.speed_label.setText(f"Speed: {speed:.2f}x")
        if self.player_thread and self.player_thread.isRunning(): self.player_thread.speed_multiplier = 1.0 / speed

    def transpose_changed(self, value: int):
        self.status_label.setText(f"Transposition set to {value} semitones.")
        if self.player_thread and self.player_thread.isRunning(): self.player_thread.transpose = value
            
    def open_key_map_editor(self):
        dialog = KeyMappingDialog(self.note_map, self)
        if dialog.exec_() == QDialog.Accepted: self.note_map = dialog.get_note_map(); self.status_label.setText("Key map updated.")
            
    def append_to_log(self, message: str):
        self.log_edit.append(message); self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def toggle_midi_input(self, checked: bool):
        if checked:
            if self.player_thread and self.player_thread.isRunning(): self.stop_midi()
            port = self.midi_input_combo.currentText()
            if not port: self.status_label.setText("No MIDI input device selected."); self.connect_button.setChecked(False); return
            self.input_thread = MidiInputThread(port); self.input_thread.note_event.connect(self.piano_roll_widget.set_active_notes); self.input_thread.log_message.connect(self.append_to_log)
            self.input_thread.start(); self.connect_button.setText("Disconnect"); self.midi_input_combo.setEnabled(False)
        else:
            if self.input_thread: self.input_thread.stop(); self.input_thread.wait(); self.input_thread = None
            self.connect_button.setText("Connect"); self.connect_button.setChecked(False); self.midi_input_combo.setEnabled(True); self.piano_roll_widget.set_active_notes({})

    def update_button_states(self):
        is_playing = bool(self.player_thread and self.player_thread.isRunning())
        is_loading = bool(self.loading_threads)
        is_file_selected = self.playlist_widget.currentItem() is not None
        
        self.play_button.setEnabled(is_file_selected and not is_playing and not is_loading)
        self.pause_button.setEnabled(is_playing); self.stop_button.setEnabled(is_playing)
        self.set_controls_enabled(not is_playing and not is_loading)

    def set_controls_enabled(self, enabled: bool):
        is_file_selected = self.playlist_widget.currentItem() is not None
        self.playlist_widget.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled and is_file_selected)
        self.clear_button.setEnabled(enabled and self.playlist_widget.count() > 0)
        self.edit_map_button.setEnabled(enabled)
        self.generate_button.setEnabled(enabled and is_file_selected)

    def closeEvent(self, event):
        if self.player_thread: self.player_thread.stop(); self.player_thread.wait()
        if self.input_thread: self.input_thread.stop(); self.input_thread.wait()
        event.accept()

# --- KEY MAPPING EDITOR DIALOG ---

class KeyMappingDialog(QDialog):
    def __init__(self, note_map: Dict[int, str], parent: Optional[QWidget] = None):
        super().__init__(parent); self.note_map = note_map.copy()
        self.setWindowTitle("Edit Key Map"); self.setMinimumSize(400, 500)
        layout = QVBoxLayout(self); self.table = QTableWidget(); self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["MIDI Note", "Note Name", "Mapped Key"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.populate_table(); self.table.keyPressEvent = self.table_key_press_event
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.restore_defaults)
        layout.addWidget(QLabel("Select a row and press a key to change its mapping.")); layout.addWidget(self.table); layout.addWidget(buttons)

    def populate_table(self):
        self.table.setRowCount(0)
        for note_num in sorted(self.note_map.keys()):
            row = self.table.rowCount(); self.table.insertRow(row)
            num_item = QTableWidgetItem(str(note_num)); num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            name_item = QTableWidgetItem(note_number_to_name(note_num)); name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            key_item = QTableWidgetItem(self.note_map[note_num]); key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, num_item); self.table.setItem(row, 1, name_item); self.table.setItem(row, 2, key_item)
    
    def table_key_press_event(self, event: QEvent):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows or not event.text(): super(QTableWidget, self.table).keyPressEvent(event); return
        row, note_num, new_key = selected_rows[0].row(), int(self.table.item(selected_rows[0].row(), 0).text()), event.text()
        for num, key in self.note_map.items():
            if key == new_key and num != note_num and (old_row := self.get_row_for_note(num)) != -1:
                self.table.item(old_row, 2).setText(""); self.note_map[num] = ""
        self.note_map[note_num] = new_key; self.table.item(row, 2).setText(new_key)
        
    def get_row_for_note(self, note_num: int) -> int:
        for row in range(self.table.rowCount()):
            if int(self.table.item(row, 0).text()) == note_num: return row
        return -1

    def restore_defaults(self): self.note_map = DEFAULT_NOTE_MAP.copy(); self.populate_table()
    def get_note_map(self) -> Dict[int, str]: return {k: v for k, v in self.note_map.items() if v}


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MidiKeyboardApp()
    sys.exit(app.exec_())