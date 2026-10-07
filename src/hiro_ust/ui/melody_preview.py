"""Interactive melody preview and lightweight audio synthesis.

The preview is deliberately UI-facing: it turns generated UST/USTX note data
into a piano-roll representation and provides a tiny synthesized audition path.
The selection signal is intended to become the hand-off point for future
range-based regeneration.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import platform
import shutil
import tempfile
import wave

import numpy as np
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:  # pragma: no cover - depends on Qt multimedia availability
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
    """Extract note events from either USTX YAML or classic UST text."""
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

    result = []
    position = 0
    blocks = output.split("[#")
    for raw in blocks:
        if "]" not in raw:
            continue
        _, body = raw.split("]", 1)
        fields: dict[str, str] = {}
        for line in body.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()

        try:
            length = int(float(fields.get("Length", "0")))
        except ValueError:
            length = 0
        lyric = fields.get("Lyric", "")
        try:
            tone = int(float(fields.get("NoteNum", "60")))
        except ValueError:
            tone = 60

        if length > 0 and lyric not in {"", "R"}:
            result.append(PreviewNote(position, length, tone, lyric))
        position += max(0, length)

    return result


class PianoRollWidget(QFrame):
    """Minimal piano roll with note and contiguous-range selection."""

    selectionChanged = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.notes: list[PreviewNote] = []
        self._selected: tuple[int, int] | None = None
        self._anchor_index: int | None = None
        self.pixels_per_tick = 0.10
        self.row_height = 16
        self.left_margin = 54
        self.top_margin = 26
        self.min_tone = 48
        self.max_tone = 72

    def set_notes(self, notes: list[PreviewNote]) -> None:
        self.notes = sorted(notes, key=lambda n: (n.position, n.tone))
        self._selected = None
        self._anchor_index = None
        self._update_range()
        self.selectionChanged.emit(0, 0)
        self.updateGeometry()
        self.update()

    def selected_notes(self) -> list[PreviewNote]:
        if self._selected is None:
            return []
        start, end = self._selected
        return self.notes[start : end + 1]

    def selection_range(self) -> tuple[int, int]:
        if self._selected is None:
            return (0, 0)
        start, end = self._selected
        selected = self.notes[start : end + 1]
        if not selected:
            return (0, 0)
        return (selected[0].position, selected[-1].end)

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        width = self.left_margin + max(80, self._total_duration()) * self.pixels_per_tick + 20
        height = self.top_margin + (self.max_tone - self.min_tone + 1) * self.row_height + 20
        return QSize(int(width), int(height))

    def sizeHint(self):
        width = self.left_margin + max(1200, self._total_duration()) * self.pixels_per_tick + 20
        height = self.top_margin + (self.max_tone - self.min_tone + 1) * self.row_height + 20
        from PySide6.QtCore import QSize
        return QSize(int(width), int(height))

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

    def _note_at(self, x: float, y: float) -> int | None:
        tick = self._x_to_tick(x)
        tone = self.max_tone - int(max(0.0, y - self.top_margin) / self.row_height)
        for index, note in enumerate(self.notes):
            if note.position <= tick <= note.end and note.tone == tone:
                return index
        return None

    def _select_to(self, index: int) -> None:
        if self._anchor_index is None:
            self._anchor_index = index
        self._selected = tuple(sorted((self._anchor_index, index)))
        start, end = self.selection_range()
        self.selectionChanged.emit(start, end)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        index = self._note_at(event.position().x(), event.position().y())
        if index is None:
            self._selected = None
            self._anchor_index = None
            self.selectionChanged.emit(0, 0)
        else:
            self._anchor_index = index
            self._selected = (index, index)
            self.selectionChanged.emit(*self.selection_range())
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._anchor_index is not None and event.buttons() & Qt.LeftButton:
            index = self._note_at(event.position().x(), event.position().y())
            if index is not None:
                self._select_to(index)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            start, end = self.selection_range()
            self.selectionChanged.emit(start, end)
            self.update()
        super().mouseReleaseEvent(event)

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

        painter.setPen(QPen(grid, 1))
        for tone in range(self.min_tone, self.max_tone + 1):
            y = self.top_margin + (self.max_tone - tone) * self.row_height
            painter.drawLine(self.left_margin, y, x_end, y)
            if tone % 12 == 0:
                painter.setPen(QPen(muted, 1))
                painter.drawText(4, y + self.row_height - 2, f"C{tone // 12 - 1}")
                painter.setPen(QPen(grid, 1))

        tick = 0
        while tick <= total:
            x = self.left_margin + int(tick * self.pixels_per_tick)
            strong = tick % 1920 == 0
            painter.setPen(QPen(text if strong else grid, 1))
            painter.drawLine(x, self.top_margin, x, y_bottom)
            if strong:
                painter.drawText(x + 3, 17, f"{tick // 1920 + 1}")
            tick += 480

        selected_start, selected_end = self._selected or (-1, -1)
        for index, note in enumerate(self.notes):
            x = self.left_margin + int(note.position * self.pixels_per_tick)
            width = max(3, int(note.duration * self.pixels_per_tick))
            y = self.top_margin + (self.max_tone - note.tone) * self.row_height + 2
            height = max(4, self.row_height - 3)

            selected = selected_start <= index <= selected_end
            painter.fillRect(x, y, width, height, highlight if selected else palette.alternateBase().color())
            painter.setPen(QPen(text if selected else muted, 1))
            painter.drawRect(x, y, width, height)

            metrics = QFontMetrics(painter.font())
            label = note.lyric
            if metrics.horizontalAdvance(label) + 8 <= width:
                painter.setPen(highlight_text if selected else text)
                painter.drawText(x + 4, y + height - 4, label)


class SimpleMelodySynth:
    """Generate and audition a small monophonic WAV without extra dependencies."""

    SAMPLE_RATE = 44_100

    def __init__(self) -> None:
        self._path: Path | None = None
        self._effect = QSoundEffect() if QSoundEffect is not None else None

    @property
    def available(self) -> bool:
        return self._effect is not None or platform.system() == "Windows"

    def stop(self) -> None:
        if self._effect is not None:
            self._effect.stop()
        elif platform.system() == "Windows":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def play(self, notes: list[PreviewNote], tempo: float, selection: tuple[int, int] | None = None) -> Path:
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

    def _render_wav(
        self,
        notes: list[PreviewNote],
        tempo: float,
        start_tick: int,
        end_tick: int,
    ) -> Path:
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
        path = Path(tempfile.gettempdir()) / f"hiro_ust_preview_{os.getpid()}.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.SAMPLE_RATE)
            handle.writeframes(pcm.tobytes())
        return path


class MelodyPreviewPanel(QWidget):
    """Self-contained controls surrounding the piano-roll widget."""

    selectionChanged = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.piano_roll = PianoRollWidget()
        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_selection_button = QPushButton("Play Selection")
        self.play_selection_button.setEnabled(False)
        self.selection_label = QLabel("No range selected")
        self.selection_label.setObjectName("eyebrow")

        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.play_selection_button)
        controls.addWidget(self.selection_label)
        controls.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self.piano_roll)
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(scroll, 1)

        self.piano_roll.selectionChanged.connect(self._on_selection)

    def set_notes(self, notes: list[PreviewNote]) -> None:
        self.piano_roll.set_notes(notes)
        self.play_button.setEnabled(bool(notes))
        self.play_selection_button.setEnabled(False)
        self.selection_label.setText("No range selected")

    def _on_selection(self, start: int, end: int) -> None:
        has_selection = end > start
        self.play_selection_button.setEnabled(has_selection)
        if has_selection:
            self.selection_label.setText(f"Selection: {start}–{end} ticks")
        else:
            self.selection_label.setText("No range selected")
        self.selectionChanged.emit(start, end)


__all__ = [
    "MelodyPreviewPanel",
    "PianoRollWidget",
    "PreviewNote",
    "SimpleMelodySynth",
    "notes_from_output",
]
