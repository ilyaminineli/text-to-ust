"""Piano-roll editor for the generated melody."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import platform
import shutil
import tempfile
import uuid
import wave

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal, QUrl
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:
    QSoundEffect = None


@dataclass(frozen=True)
class PreviewNote:
    position: int
    duration: int
    tone: int
    lyric: str

    @property
    def end(self) -> int:
        return self.position + self.duration


def notes_from_output(output: str, output_format: str) -> list[PreviewNote]:
    if not output:
        return []
    if output_format == "ustx":
        import yaml
        try:
            parsed = yaml.safe_load(output) or {}
            parts = parsed.get("voice_parts", [])
            raw_notes = parts[0].get("notes", []) if parts else []
        except Exception:
            return []
        result = []
        for note in raw_notes:
            try:
                duration = int(note.get("duration", 0))
                position = int(note.get("position", 0))
                tone = int(note.get("tone", 60))
            except (TypeError, ValueError):
                continue
            lyric = str(note.get("lyric", ""))
            if duration > 0 and lyric not in {"R", ""}:
                result.append(PreviewNote(position, duration, tone, lyric))
        return result

    result = []
    position = 0
    for raw in output.split("[#"):
        if "]" not in raw:
            continue
        _, body = raw.split("]", 1)
        fields = {}
        for line in body.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()
        try:
            length = int(float(fields.get("Length", "0")))
            tone = int(float(fields.get("NoteNum", "60")))
        except ValueError:
            length, tone = 0, 60
        lyric = fields.get("Lyric", "")
        if length > 0 and lyric not in {"", "R"}:
            result.append(PreviewNote(position, length, tone, lyric))
        position += max(0, length)
    return result


class PianoRollWidget(QFrame):
    selectionChanged = Signal(int, int)
    selectionIndicesChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.notes: list[PreviewNote] = []
        self._selected: set[int] = set()
        self._anchor_index: int | None = None
        self._drag_origin: QPoint | None = None
        self._dragging = False
        self._selection_base: set[int] = set()
        self._fit_mode = True
        self.pixels_per_tick = 0.08
        self.row_height = 18
        self.left_margin = 54
        self.top_margin = 28
        self.min_tone = 48
        self.max_tone = 72

    def set_notes(self, notes: list[PreviewNote]) -> None:
        self.notes = sorted(notes, key=lambda n: (n.position, n.tone))
        self._selected.clear()
        self._anchor_index = None
        self._update_range()
        self._update_size()
        self._emit_selection()
        self.update()

    def fit_to_width(self, width: int) -> None:
        usable = max(200, width - self.left_margin - 16)
        self.pixels_per_tick = max(0.012, usable / max(1, self._total_duration()))
        self._fit_mode = True
        self._update_size()
        self.update()

    def zoom(self, factor: float) -> None:
        self.pixels_per_tick = max(0.012, min(0.75, self.pixels_per_tick * factor))
        self._fit_mode = False
        self._update_size()
        self.update()

    def _total_duration(self) -> int:
        return max((n.end for n in self.notes), default=480)

    def _update_range(self) -> None:
        if not self.notes:
            self.min_tone, self.max_tone = 48, 72
        else:
            self.min_tone = max(0, min(n.tone for n in self.notes) - 3)
            self.max_tone = min(127, max(n.tone for n in self.notes) + 3)

    def _content_size(self) -> QSize:
        return QSize(
            self.left_margin + int(max(480, self._total_duration()) * self.pixels_per_tick) + 20,
            self.top_margin + (self.max_tone - self.min_tone + 1) * self.row_height + 24,
        )

    def _update_size(self) -> None:
        size = self._content_size()
        self.setMinimumSize(size)
        self.resize(size)

    def minimumSizeHint(self) -> QSize:
        return self._content_size()

    def sizeHint(self) -> QSize:
        return self._content_size()

    def _note_rect(self, index: int) -> QRect:
        note = self.notes[index]
        x = self.left_margin + int(note.position * self.pixels_per_tick)
        width = max(4, int(note.duration * self.pixels_per_tick))
        y = self.top_margin + (self.max_tone - note.tone) * self.row_height + 2
        return QRect(x, y, width, self.row_height - 4)

    def _note_at(self, point: QPoint) -> int | None:
        for i in range(len(self.notes) - 1, -1, -1):
            if self._note_rect(i).contains(point):
                return i
        return None

    def _indices_in_rect(self, rect: QRect) -> set[int]:
        return {i for i in range(len(self.notes)) if rect.intersects(self._note_rect(i))}

    def selected_notes(self) -> list[PreviewNote]:
        return [self.notes[i] for i in sorted(self._selected) if 0 <= i < len(self.notes)]

    def selection_indices(self) -> list[int]:
        return sorted(self._selected)

    def selection_range(self) -> tuple[int, int]:
        selected = self.selected_notes()
        return (min(n.position for n in selected), max(n.end for n in selected)) if selected else (0, 0)

    def clear_selection(self) -> None:
        self._selected.clear()
        self._anchor_index = None
        self._emit_selection()
        self.update()

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(*self.selection_range())
        self.selectionIndicesChanged.emit(self.selection_indices())

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self.setFocus()
        self._drag_origin = event.position().toPoint()
        index = self._note_at(self._drag_origin)
        self._dragging = False
        self._selection_base = set(self._selected)
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        shift = bool(event.modifiers() & Qt.ShiftModifier)
        if index is None:
            if not ctrl:
                self.clear_selection()
        elif shift and self._anchor_index is not None:
            a, b = sorted((self._anchor_index, index))
            self._selected = set(range(a, b + 1)) | (self._selected if ctrl else set())
            self._emit_selection()
        elif ctrl:
            if index in self._selected:
                self._selected.remove(index)
            else:
                self._selected.add(index)
            self._anchor_index = index
            self._emit_selection()
        else:
            self._selected = {index}
            self._anchor_index = index
            self._emit_selection()
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            current = event.position().toPoint()
            if (current - self._drag_origin).manhattanLength() > 4:
                self._dragging = True
            if self._dragging:
                rect = QRect(self._drag_origin, current).normalized()
                chosen = self._indices_in_rect(rect)
                self._selected = self._selection_base | chosen if event.modifiers() & Qt.ControlModifier else chosen
                self._emit_selection()
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = None
            self._dragging = False
            self._selection_base = set()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _midi_name(note: int) -> str:
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        return f"{names[note % 12]}{note // 12 - 1}"

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        pal = self.palette()
        painter.fillRect(self.rect(), pal.base().color())
        total = max(480, self._total_duration())
        x_end = self.left_margin + int(total * self.pixels_per_tick) + 12
        y_bottom = self.top_margin + (self.max_tone - self.min_tone + 1) * self.row_height

        for tone in range(self.min_tone, self.max_tone + 1):
            y = self.top_margin + (self.max_tone - tone) * self.row_height
            painter.setPen(QPen(pal.placeholderText().color() if tone % 12 == 0 else pal.mid().color(), 1))
            painter.drawLine(self.left_margin, y, x_end, y)
            if tone % 12 == 0:
                painter.drawText(3, y + self.row_height - 3, self._midi_name(tone))

        tick = 0
        while tick <= total:
            x = self.left_margin + int(tick * self.pixels_per_tick)
            strong = tick % 1920 == 0
            painter.setPen(QPen(pal.text().color() if strong else pal.mid().color(), 1))
            painter.drawLine(x, self.top_margin, x, y_bottom)
            if strong:
                painter.drawText(x + 3, 18, f"{tick // 1920 + 1}")
            tick += 480

        if self._dragging and self._drag_origin:
            current = self.mapFromGlobal(self.cursor().pos())
            painter.setPen(QPen(pal.highlight().color(), 1, Qt.DashLine))
            painter.drawRect(QRect(self._drag_origin, current).normalized())

        metrics = QFontMetrics(painter.font())
        for index, note in enumerate(self.notes):
            rect = self._note_rect(index)
            selected = index in self._selected
            painter.fillRect(rect, pal.highlight().color() if selected else pal.alternateBase().color())
            painter.setPen(QPen(pal.highlightedText().color() if selected else pal.placeholderText().color(), 1))
            painter.drawRect(rect)
            if rect.width() >= 28 and metrics.horizontalAdvance(note.lyric) + 8 <= rect.width():
                painter.setPen(pal.highlightedText().color() if selected else pal.text().color())
                painter.drawText(rect.x() + 4, rect.bottom() - 4, note.lyric)


class SimpleMelodySynth:
    SAMPLE_RATE = 44100

    def __init__(self):
        self._path: Path | None = None
        self._effect = QSoundEffect() if QSoundEffect is not None else None

    def stop(self):
        if self._effect:
            self._effect.stop()
        elif platform.system() == "Windows":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def play(self, notes: list[PreviewNote], tempo: float, selection: tuple[int, int] | None = None):
        if not notes:
            raise ValueError("No melody notes available.")
        self.stop()
        start_tick, end_tick = (notes[0].position, notes[-1].end) if selection is None else selection
        path = self._render_wav(notes, tempo, start_tick, end_tick)
        self._path = path
        if self._effect:
            self._effect.setSource(QUrl.fromLocalFile(str(path)))
            self._effect.setVolume(0.30)
            self._effect.play()
        elif platform.system() == "Windows":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            player = shutil.which("afplay") or shutil.which("aplay")
            if not player:
                raise RuntimeError("No audio player is available.")
            import subprocess
            subprocess.Popen([player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _render_wav(self, notes, tempo, start_tick, end_tick):
        ticks_per_second = 480.0 * float(tempo) / 60.0
        duration_seconds = max(0.1, (end_tick - start_tick) / ticks_per_second)
        samples = max(1, int(math.ceil(duration_seconds * self.SAMPLE_RATE)))
        audio = np.zeros(samples, dtype=np.float32)
        for note in notes:
            if note.end <= start_tick or note.position >= end_tick:
                continue
            a = int((max(note.position, start_tick) - start_tick) / ticks_per_second * self.SAMPLE_RATE)
            b = min(samples, int((min(note.end, end_tick) - start_tick) / ticks_per_second * self.SAMPLE_RATE))
            if b <= a:
                continue
            t = np.arange(b - a, dtype=np.float32) / self.SAMPLE_RATE
            frequency = 440.0 * (2.0 ** ((note.tone - 69) / 12.0))
            wave_data = 0.78 * np.sin(2 * np.pi * frequency * t) + 0.16 * np.sin(4 * np.pi * frequency * t)
            audio[a:b] += 0.22 * wave_data
        peak = float(np.max(np.abs(audio))) if audio.size else 0
        if peak > 0.95:
            audio *= 0.95 / peak
        pcm = np.int16(np.clip(audio, -1, 1) * 32767)
        path = Path(tempfile.gettempdir()) / f"hiro_ust_preview_{os.getpid()}_{uuid.uuid4().hex}.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.SAMPLE_RATE)
            handle.writeframes(pcm.tobytes())
        return path


class MelodyPreviewPanel(QWidget):
    selectionChanged = Signal(int, int)
    selectionIndicesChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.piano_roll = PianoRollWidget()
        self.play_button = QPushButton("Play")
        self.play_selection_button = QPushButton("Selection")
        self.stop_button = QPushButton("Stop")
        self.fit_button = QPushButton("Fit")
        self.zoom_out_button = QPushButton("−")
        self.zoom_in_button = QPushButton("+")
        self.selection_label = QLabel("No selection")
        self.selection_label.setObjectName("eyebrow")

        controls = QHBoxLayout()
        for widget in (
            self.play_button,
            self.play_selection_button,
            self.stop_button,
            self.fit_button,
            self.zoom_out_button,
            self.zoom_in_button,
            self.selection_label,
        ):
            controls.addWidget(widget)
        controls.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.piano_roll)
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QFrame.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.scroll, 1)

        self.piano_roll.selectionChanged.connect(self._on_selection)
        self.piano_roll.selectionIndicesChanged.connect(self.selectionIndicesChanged)
        self.fit_button.clicked.connect(self.fit)
        self.zoom_out_button.clicked.connect(lambda: self.piano_roll.zoom(0.8))
        self.zoom_in_button.clicked.connect(lambda: self.piano_roll.zoom(1.25))

    def set_notes(self, notes):
        self.piano_roll.set_notes(notes)
        has_notes = bool(notes)
        self.play_button.setEnabled(has_notes)
        self.stop_button.setEnabled(has_notes)
        self.play_selection_button.setEnabled(False)
        self.selection_label.setText("No selection")
        if has_notes:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.fit)

    def fit(self):
        self.piano_roll.fit_to_width(max(320, self.scroll.viewport().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.piano_roll._fit_mode:
            self.fit()

    def _on_selection(self, start, end):
        count = len(self.piano_roll.selection_indices())
        self.play_selection_button.setEnabled(count > 0)
        self.selection_label.setText(f"{count} notes · {start}–{end}" if count else "No selection")
        self.selectionChanged.emit(start, end)
