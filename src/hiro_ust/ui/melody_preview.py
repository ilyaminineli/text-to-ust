"""Interactive piano-roll melody preview and lightweight audition."""
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
from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:  # pragma: no cover
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
    """Extract note events from USTX YAML or classic UST text."""
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

        result: list[PreviewNote] = []
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

    result: list[PreviewNote] = []
    position = 0
    for raw in output.split("[#"):
        if "]" not in raw:
            continue
        _, body = raw.split("]", 1)
        fields: dict[str, str] = {}
        for line in body.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()

        try:
            length = int(float(fields.get("Length", "0")))
            tone = int(float(fields.get("NoteNum", "60")))
        except ValueError:
            length = 0
            tone = 60

        lyric = fields.get("Lyric", "")
        if length > 0 and lyric not in {"", "R"}:
            result.append(PreviewNote(position, length, tone, lyric))
        position += max(0, length)

    return result


class PianoRollWidget(QFrame):
    """Piano roll with Ctrl/Shift selection and mouse-marquee selection."""

    selectionChanged = Signal(int, int)
    selectionIndicesChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)

        self.notes: list[PreviewNote] = []
        self._selected: set[int] = set()
        self._anchor_index: int | None = None
        self._press_index: int | None = None
        self._drag_origin: QPoint | None = None
        self._dragging = False
        self._selection_base: set[int] = set()
        self._fit_mode = True

        self.pixels_per_tick = 0.08
        self.row_height = 18
        self.left_margin = 58
        self.top_margin = 28
        self.min_tone = 48
        self.max_tone = 72

    def set_notes(self, notes: list[PreviewNote]) -> None:
        self.notes = sorted(notes, key=lambda n: (n.position, n.tone))
        self._selected.clear()
        self._anchor_index = None
        self._press_index = None
        self._drag_origin = None
        self._dragging = False
        self._update_range()
        self._update_size()
        self._emit_selection()
        self.update()
        QTimer.singleShot(0, self._fit_if_needed)

    def _fit_if_needed(self) -> None:
        if self._fit_mode and self.width() > 0:
            self.fit_to_width(max(280, self.width()))

    def fit_to_width(self, available_width: int) -> None:
        total = max(1, self._total_duration())
        usable = max(180, int(available_width) - self.left_margin - 24)
        self.pixels_per_tick = max(0.012, usable / total)
        self._fit_mode = True
        self._update_size()
        self.update()

    def zoom(self, factor: float) -> None:
        self.pixels_per_tick = max(0.012, min(0.50, self.pixels_per_tick * factor))
        self._fit_mode = False
        self._update_size()
        self.update()

    def selected_notes(self) -> list[PreviewNote]:
        return [self.notes[i] for i in sorted(self._selected) if 0 <= i < len(self.notes)]

    def selection_indices(self) -> list[int]:
        return sorted(self._selected)

    def selection_range(self) -> tuple[int, int]:
        selected = self.selected_notes()
        if not selected:
            return (0, 0)
        return min(n.position for n in selected), max(n.end for n in selected)

    def clear_selection(self) -> None:
        self._selected.clear()
        self._anchor_index = None
        self._emit_selection()
        self.update()

    def _emit_selection(self) -> None:
        start, end = self.selection_range()
        self.selectionChanged.emit(start, end)
        self.selectionIndicesChanged.emit(self.selection_indices())

    def minimumSizeHint(self) -> QSize:
        return self._content_size()

    def sizeHint(self) -> QSize:
        return self._content_size()

    def _content_size(self) -> QSize:
        width = self.left_margin + int(max(480, self._total_duration()) * self.pixels_per_tick) + 24
        height = self.top_margin + (self.max_tone - self.min_tone + 1) * self.row_height + 24
        return QSize(max(320, width), max(260, height))

    def _update_size(self) -> None:
        size = self._content_size()
        self.setMinimumSize(size)
        self.resize(size)

    def _total_duration(self) -> int:
        return max((note.end for note in self.notes), default=480)

    def _update_range(self) -> None:
        if not self.notes:
            self.min_tone, self.max_tone = 48, 72
            return
        self.min_tone = max(0, min(note.tone for note in self.notes) - 3)
        self.max_tone = min(127, max(note.tone for note in self.notes) + 3)

    def _x_to_tick(self, x: float) -> float:
        return max(0.0, (x - self.left_margin) / self.pixels_per_tick)

    def _note_rect(self, index: int) -> QRect:
        note = self.notes[index]
        x = self.left_margin + int(note.position * self.pixels_per_tick)
        width = max(4, int(note.duration * self.pixels_per_tick))
        y = self.top_margin + (self.max_tone - note.tone) * self.row_height + 2
        return QRect(x, y, width, max(5, self.row_height - 4))

    def _note_at(self, point: QPoint) -> int | None:
        for index in range(len(self.notes) - 1, -1, -1):
            if self._note_rect(index).contains(point):
                return index
        return None

    def _indices_in_rect(self, rect: QRect) -> set[int]:
        return {index for index in range(len(self.notes)) if rect.intersects(self._note_rect(index))}

    def _select_range(self, a: int, b: int, *, add: bool = False) -> None:
        start, end = sorted((a, b))
        chosen = set(range(start, end + 1))
        self._selected = (self._selected | chosen) if add else chosen
        self._anchor_index = b
        self._emit_selection()
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        self.setFocus()
        self._drag_origin = event.position().toPoint()
        self._press_index = self._note_at(self._drag_origin)
        self._dragging = False
        self._selection_base = set(self._selected)

        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.ControlModifier)
        shift = bool(modifiers & Qt.ShiftModifier)

        if self._press_index is None:
            if not ctrl:
                self._selected.clear()
                self._anchor_index = None
                self._emit_selection()
        elif shift and self._anchor_index is not None:
            self._select_range(self._anchor_index, self._press_index, add=ctrl)
        elif ctrl:
            if self._press_index in self._selected:
                self._selected.remove(self._press_index)
            else:
                self._selected.add(self._press_index)
            self._anchor_index = self._press_index
            self._emit_selection()
        else:
            self._selected = {self._press_index}
            self._anchor_index = self._press_index
            self._emit_selection()

        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            current = event.position().toPoint()
            if (current - self._drag_origin).manhattanLength() > 4:
                self._dragging = True

            if self._dragging:
                rect = QRect(self._drag_origin, current).normalized()
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
                chosen = self._indices_in_rect(rect)
                self._selected = (self._selection_base | chosen) if ctrl else chosen
                self._emit_selection()
                self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._dragging:
            self._drag_origin = None
            self._press_index = None
            self._dragging = False
            self._selection_base = set()
            self.update()
        elif event.button() == Qt.LeftButton:
            self._drag_origin = None
            self._press_index = None
            self._dragging = False
            self._selection_base = set()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.clear_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        palette = self.palette()
        background = palette.base().color()
        grid = palette.mid().color()
        text = palette.text().color()
        muted = palette.placeholderText().color()
        highlight = palette.highlight().color()
        highlight_text = palette.highlightedText().color()

        painter.fillRect(self.rect(), background)

        total = max(480, self._total_duration())
        x_end = self.left_margin + int(total * self.pixels_per_tick) + 20
        y_bottom = self.top_margin + (self.max_tone - self.min_tone + 1) * self.row_height

        for tone in range(self.min_tone, self.max_tone + 1):
            y = self.top_margin + (self.max_tone - tone) * self.row_height
            painter.setPen(QPen(muted if tone % 12 == 0 else grid, 1))
            painter.drawLine(self.left_margin, y, x_end, y)
            if tone % 12 == 0:
                painter.drawText(4, y + self.row_height - 2, f"C{tone // 12 - 1}")

        tick = 0
        while tick <= total:
            x = self.left_margin + int(tick * self.pixels_per_tick)
            strong = tick % 1920 == 0
            painter.setPen(QPen(text if strong else grid, 1))
            painter.drawLine(x, self.top_margin, x, y_bottom)
            if strong:
                painter.drawText(x + 3, 18, f"{tick // 1920 + 1}")
            tick += 480

        if self._dragging and self._drag_origin is not None:
            rect = QRect(self._drag_origin, self.mapFromGlobal(self.cursor().pos())).normalized()
            painter.setPen(QPen(highlight, 1, Qt.DashLine))
            painter.drawRect(rect)

        for index, note in enumerate(self.notes):
            rect = self._note_rect(index)
            selected = index in self._selected
            painter.fillRect(rect, highlight if selected else palette.alternateBase().color())
            painter.setPen(QPen(text if selected else muted, 1))
            painter.drawRect(rect)

            metrics = QFontMetrics(painter.font())
            if metrics.horizontalAdvance(note.lyric) + 8 <= rect.width():
                painter.setPen(highlight_text if selected else text)
                painter.drawText(rect.x() + 4, rect.bottom() - 4, note.lyric)


class SimpleMelodySynth:
    """Generate and audition a small monophonic WAV."""

    SAMPLE_RATE = 44_100

    def __init__(self) -> None:
        self._path: Path | None = None
        self._effect = QSoundEffect() if QSoundEffect is not None else None

    def stop(self) -> None:
        if self._effect is not None:
            self._effect.stop()
        elif platform.system() == "Windows":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def play(
        self,
        notes: list[PreviewNote],
        tempo: float,
        selection: tuple[int, int] | None = None,
    ) -> Path:
        if not notes:
            raise ValueError("No melody notes available.")

        self.stop()
        if selection is None:
            start_tick = notes[0].position
            end_tick = notes[-1].end
        else:
            start_tick, end_tick = selection
            start_tick = max(notes[0].position, start_tick)
            end_tick = min(notes[-1].end, end_tick)

        path = self._render_wav(notes, tempo, start_tick, end_tick)
        self._path = path

        if self._effect is not None:
            self._effect.setSource(QUrl.fromLocalFile(str(path)))
            self._effect.setVolume(0.30)
            self._effect.play()
        elif platform.system() == "Windows":
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            player = shutil.which("afplay") or shutil.which("aplay")
            if player:
                import subprocess
                subprocess.Popen([player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                raise RuntimeError("No Qt Multimedia or platform audio player is available.")
        return path

    def _render_wav(self, notes, tempo, start_tick, end_tick) -> Path:
        ticks_per_second = 480.0 * float(tempo) / 60.0
        duration_seconds = max(0.1, (end_tick - start_tick) / ticks_per_second)
        samples = max(1, int(math.ceil(duration_seconds * self.SAMPLE_RATE)))
        audio = np.zeros(samples, dtype=np.float32)

        for note in notes:
            if note.end <= start_tick or note.position >= end_tick:
                continue

            local_start = max(note.position, start_tick) - start_tick
            local_end = min(note.end, end_tick) - start_tick
            a = int(local_start / ticks_per_second * self.SAMPLE_RATE)
            b = min(samples, int(local_end / ticks_per_second * self.SAMPLE_RATE))
            if b <= a:
                continue

            length = b - a
            t = np.arange(length, dtype=np.float32) / self.SAMPLE_RATE
            frequency = 440.0 * (2.0 ** ((note.tone - 69) / 12.0))
            wave_data = (
                0.78 * np.sin(2.0 * np.pi * frequency * t)
                + 0.16 * np.sin(2.0 * np.pi * frequency * 2.0 * t)
            )

            attack = min(int(0.012 * self.SAMPLE_RATE), max(1, length // 4))
            release = min(int(0.045 * self.SAMPLE_RATE), max(1, length // 3))
            envelope = np.ones(length, dtype=np.float32)
            envelope[:attack] *= np.linspace(0.0, 1.0, attack, endpoint=False)
            envelope[-release:] *= np.linspace(1.0, 0.0, release)
            audio[a:b] += 0.22 * wave_data * envelope

        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 0.95:
            audio *= 0.95 / peak

        pcm = np.int16(np.clip(audio, -1.0, 1.0) * 32767)
        path = Path(tempfile.gettempdir()) / f"hiro_ust_preview_{os.getpid()}_{uuid.uuid4().hex}.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.SAMPLE_RATE)
            handle.writeframes(pcm.tobytes())
        return path


class MelodyPreviewPanel(QWidget):
    """Controls for audition, fit/zoom and future zone selection workflows."""

    selectionChanged = Signal(int, int)
    selectionIndicesChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.piano_roll = PianoRollWidget()

        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_selection_button = QPushButton("Play Selection")
        self.play_selection_button.setEnabled(False)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.fit_button = QPushButton("Fit")
        self.zoom_out_button = QPushButton("−")
        self.zoom_in_button = QPushButton("+")
        self.selection_label = QLabel("No selection")
        self.selection_label.setObjectName("eyebrow")

        controls = QHBoxLayout()
        controls.setSpacing(6)
        controls.addWidget(self.play_button)
        controls.addWidget(self.play_selection_button)
        controls.addWidget(self.stop_button)
        controls.addSpacing(6)
        controls.addWidget(self.fit_button)
        controls.addWidget(self.zoom_out_button)
        controls.addWidget(self.zoom_in_button)
        controls.addWidget(self.selection_label)
        controls.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.piano_roll)
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(controls)
        layout.addWidget(self.scroll, 1)

        self.piano_roll.selectionChanged.connect(self._on_selection)
        self.piano_roll.selectionIndicesChanged.connect(self.selectionIndicesChanged)

        self.fit_button.clicked.connect(self.fit)
        self.zoom_out_button.clicked.connect(lambda: self.piano_roll.zoom(1 / 1.25))
        self.zoom_in_button.clicked.connect(lambda: self.piano_roll.zoom(1.25))

    def set_notes(self, notes: list[PreviewNote]) -> None:
        self.piano_roll.set_notes(notes)
        self.play_button.setEnabled(bool(notes))
        self.play_selection_button.setEnabled(False)
        self.stop_button.setEnabled(bool(notes))
        self.selection_label.setText("No selection")

    def fit(self) -> None:
        self.piano_roll.fit_to_width(max(280, self.scroll.viewport().width()))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.piano_roll._fit_mode:
            self.fit()

    def _on_selection(self, start: int, end: int) -> None:
        count = len(self.piano_roll.selection_indices())
        self.play_selection_button.setEnabled(count > 0)
        if count:
            self.selection_label.setText(f"{count} notes · {start}–{end}")
        else:
            self.selection_label.setText("No selection")
        self.selectionChanged.emit(start, end)


__all__ = [
    "MelodyPreviewPanel",
    "PianoRollWidget",
    "PreviewNote",
    "SimpleMelodySynth",
    "notes_from_output",
]
