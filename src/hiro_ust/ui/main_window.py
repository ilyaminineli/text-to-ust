"""Main PySide6 application window.

The UI owns presentation state only. Generation remains in HiroUSTProcessor.
"""
from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QGroupBox,
)

from ..config import GeneratorConfig, HiroConfig
from ..core import HiroUSTProcessor
from ..melody import SCALES
from .theme import apply_theme


class HiroMainWindow(QMainWindow):
    APP_NAME = "Hiro UST"
    SETTINGS_ORG = "EliLab"
    SETTINGS_APP = "HiroUST"

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
        self.current_file: Path | None = None
        self.last_output = ""
        self.last_output_format = "ustx"

        self.setWindowTitle(self.APP_NAME)
        self.resize(1440, 900)
        self._build_ui()
        self._build_actions()
        self._load_settings()
        self._set_status("Ready")

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar(self))

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        self.new_action = QAction("New", self)
        self.open_action = QAction("Open", self)
        self.save_action = QAction("Save Lyrics", self)
        self.generate_action = QAction("Generate", self)
        self.export_action = QAction("Export UST", self)
        self.generate_action.setShortcut("Ctrl+Enter")

        for action in (self.new_action, self.open_action, self.save_action):
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addAction(self.generate_action)
        toolbar.addAction(self.export_action)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        eyebrow = QLabel("GENERATIVE JAPANESE UTAU")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Hiro UST")
        title.setObjectName("title")
        subtitle = QLabel("Lyrics → musical structure → UST / USTX")
        subtitle.setObjectName("eyebrow")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.project_edit = QLineEdit("Hiro_Main")
        self.project_edit.setPlaceholderText("Project name")
        self.project_edit.setMaximumWidth(260)
        header.addWidget(self.project_edit)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        lyrics_panel = self._make_panel("LYRICS")
        self.lyrics_edit = QPlainTextEdit()
        self.lyrics_edit.setPlaceholderText(
            "Paste Japanese lyrics here…\n\n"
            "Section markers are supported:\n"
            "[A]\n"
            "[B]"
        )
        lyrics_panel.layout().addWidget(self.lyrics_edit, 1)

        analysis_panel = self._make_panel("ANALYSIS / GENERATED NOTES")
        self.analysis_label = QLabel("No generation yet.")
        self.analysis_label.setWordWrap(True)
        analysis_panel.layout().addWidget(self.analysis_label)

        self.notes_table = QTableWidget(0, 5)
        self.notes_table.setHorizontalHeaderLabels(["#", "Lyric", "MIDI", "Length", "Position"])
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notes_table.horizontalHeader().setStretchLastSection(True)
        analysis_panel.layout().addWidget(self.notes_table, 1)

        settings_panel = self._make_panel("MUSICAL SETTINGS")
        form = QFormLayout()

        self.tempo = QDoubleSpinBox()
        self.tempo.setRange(HiroConfig.MIN_TEMPO, HiroConfig.MAX_TEMPO)
        self.tempo.setDecimals(1)
        self.tempo.setSuffix(" BPM")
        self.tempo.setValue(120.0)

        self.root_key = QSpinBox()
        self.root_key.setRange(0, 127)
        self.root_key.setValue(60)

        self.scale = QComboBox()
        self.scale.addItems(list(SCALES))
        self.scale.setCurrentText("Major Pentatonic")

        self.base_length = QSpinBox()
        self.base_length.setRange(HiroConfig.MIN_NOTE_LEN, HiroConfig.MAX_NOTE_LEN)
        self.base_length.setSingleStep(60)
        self.base_length.setSuffix(" ticks")
        self.base_length.setValue(240)

        self.length_var = QDoubleSpinBox()
        self.length_var.setRange(0.0, 1.0)
        self.length_var.setSingleStep(0.05)
        self.length_var.setDecimals(2)
        self.length_var.setValue(0.30)

        self.stretch_prob = QDoubleSpinBox()
        self.stretch_prob.setRange(0.0, 1.0)
        self.stretch_prob.setSingleStep(0.05)
        self.stretch_prob.setDecimals(2)
        self.stretch_prob.setValue(0.25)

        self.seed = QSpinBox()
        self.seed.setRange(0, 2_147_483_647)
        self.seed.setValue(1234)

        self.output_format = QComboBox()
        self.output_format.addItems(["ustx", "ust"])

        form.addRow("Tempo", self.tempo)
        form.addRow("Root", self.root_key)
        form.addRow("Scale", self.scale)
        form.addRow("Base length", self.base_length)
        form.addRow("Length variation", self.length_var)
        form.addRow("Stretch probability", self.stretch_prob)
        form.addRow("Seed", self.seed)
        form.addRow("Output", self.output_format)
        settings_panel.layout().addLayout(form)

        options = QGroupBox("Generation")
        options_layout = QVBoxLayout(options)
        self.use_motifs = QCheckBox("Use motifs")
        self.use_motifs.setChecked(True)
        self.quartertone = QCheckBox("Quarter-tone expression")
        self.lyrical_mode = QCheckBox("Phrase-aware melody")
        self.lyrical_mode.setChecked(True)
        for widget in (self.use_motifs, self.quartertone, self.lyrical_mode):
            options_layout.addWidget(widget)
        settings_panel.layout().addWidget(options)
        settings_panel.layout().addStretch()

        generate_button = QPushButton("Generate")
        generate_button.setObjectName("primary")
        generate_button.setMinimumHeight(42)
        generate_button.clicked.connect(self.generate)
        settings_panel.layout().addWidget(generate_button)

        splitter.addWidget(lyrics_panel)
        splitter.addWidget(analysis_panel)
        splitter.addWidget(settings_panel)
        splitter.setSizes([520, 620, 320])
        root_layout.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        self.progress_label.setObjectName("eyebrow")
        self.export_path_label = QLabel("")
        self.export_path_label.setObjectName("eyebrow")
        footer.addWidget(self.progress_label)
        footer.addStretch()
        footer.addWidget(self.export_path_label)
        root_layout.addLayout(footer)

        self.setCentralWidget(root)

    def _make_panel(self, title: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)
        label = QLabel(title)
        label.setObjectName("section")
        layout.addWidget(label)
        return panel

    def _build_actions(self) -> None:
        self.new_action.triggered.connect(self.new_document)
        self.open_action.triggered.connect(self.open_lyrics)
        self.save_action.triggered.connect(self.save_lyrics)
        self.generate_action.triggered.connect(self.generate)
        self.export_action.triggered.connect(self.export_project)

    def _build_config(self) -> GeneratorConfig:
        return GeneratorConfig(
            tempo=self.tempo.value(),
            base_length=self.base_length.value(),
            root_key=self.root_key.value(),
            scale=self.scale.currentText(),
            length_var=self.length_var.value(),
            stretch_prob=self.stretch_prob.value(),
            seed=self.seed.value(),
            use_motifs=self.use_motifs.isChecked(),
            quartertone_mode=self.quartertone.isChecked(),
            lyrical_mode=self.lyrical_mode.isChecked(),
        )

    def generate(self) -> None:
        lyrics = self.lyrics_edit.toPlainText().strip()
        if not lyrics:
            QMessageBox.warning(self, self.APP_NAME, "Enter lyrics before generating.")
            return

        self._set_status("Generating…")
        self.generate_action.setEnabled(False)
        QApplication.processEvents()

        try:
            config = self._build_config()
            processor = HiroUSTProcessor(config)
            output_format = self.output_format.currentText()

            self.last_output = processor.process_lyrics(
                lyrics,
                project_name=self.project_edit.text().strip() or "Hiro_Main",
                output_format=output_format,
            )
            self.last_output_format = output_format
            self._refresh_preview(processor, lyrics, self.last_output)
            self._set_status("Generation complete")
        except Exception as exc:
            self._set_status("Generation failed")
            QMessageBox.critical(self, self.APP_NAME, f"{type(exc).__name__}: {exc}")
        finally:
            self.generate_action.setEnabled(True)

    def _refresh_preview(self, processor: HiroUSTProcessor, lyrics: str, output: str) -> None:
        doc = processor.lyric_parser.parse(lyrics, processor.phonemizer)
        words = [word for section in doc.sections for line in section.lines for word in line.words]
        phoneme_count = sum(len(word.phonemes) for word in words)

        notes = []
        if self.last_output_format == "ustx":
            try:
                import yaml
                parsed = yaml.safe_load(output) or {}
                voice_parts = parsed.get("voice_parts", [])
                notes = voice_parts[0].get("notes", []) if voice_parts else []
            except Exception:
                notes = []

        self.notes_table.setRowCount(0)
        for index, note in enumerate(notes[:500], 1):
            row = self.notes_table.rowCount()
            self.notes_table.insertRow(row)
            values = [
                str(index),
                str(note.get("lyric", "")),
                str(note.get("tone", "")),
                str(note.get("duration", "")),
                str(note.get("position", "")),
            ]
            for column, value in enumerate(values):
                self.notes_table.setItem(row, column, QTableWidgetItem(value))

        note_count_text = str(len(notes)) if notes else "ready"
        self.analysis_label.setText(
            f"Sections: {len(doc.sections)}   Words: {len(words)}   "
            f"Phonemes: {phoneme_count}   Generated notes: {note_count_text}"
        )
        self.progress_label.setText(
            f"{len(doc.sections)} section(s) · {len(words)} word(s) · seed {self.seed.value()}"
        )

    def new_document(self) -> None:
        self.current_file = None
        self.last_output = ""
        self.project_edit.setText("Hiro_Main")
        self.lyrics_edit.clear()
        self.notes_table.setRowCount(0)
        self.analysis_label.setText("No generation yet.")
        self.export_path_label.clear()
        self._set_status("New document")

    def open_lyrics(self) -> None:
        start_dir = str(self.current_file.parent) if self.current_file else str(Path.cwd())
        path, _ = QFileDialog.getOpenFileName(
            self, "Open lyrics", start_dir,
            "Text files (*.txt *.md *.lyrics);;All files (*)"
        )
        if not path:
            return
        file_path = Path(path)
        self.lyrics_edit.setPlainText(file_path.read_text(encoding="utf-8"))
        self.current_file = file_path
        self.project_edit.setText(file_path.stem)
        self._set_status(f"Opened {file_path.name}")

    def save_lyrics(self) -> None:
        default = self.current_file or (Path.cwd() / f"{self.project_edit.text().strip() or 'Hiro_Main'}.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save lyrics", str(default),
            "Text files (*.txt);;Markdown (*.md);;All files (*)"
        )
        if not path:
            return
        file_path = Path(path)
        file_path.write_text(self.lyrics_edit.toPlainText(), encoding="utf-8")
        self.current_file = file_path
        self._set_status(f"Saved {file_path.name}")

    def export_project(self) -> None:
        if not self.last_output:
            self.generate()
            if not self.last_output:
                return

        suffix = self.last_output_format
        default = Path.cwd() / f"{self.project_edit.text().strip() or 'Hiro_Main'}.{suffix}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export UST project", str(default),
            f"{suffix.upper()} files (*.{suffix});;All files (*)"
        )
        if not path:
            return
        file_path = Path(path)
        file_path.write_text(self.last_output, encoding="utf-8")
        self.export_path_label.setText(str(file_path))
        self._set_status(f"Exported {file_path.name}")

    def _load_settings(self) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        numeric_widgets = (
            (self.tempo, "tempo"),
            (self.root_key, "root"),
            (self.base_length, "base_length"),
            (self.length_var, "length_var"),
            (self.stretch_prob, "stretch_prob"),
            (self.seed, "seed"),
        )
        for widget, key in numeric_widgets:
            value = self.settings.value(key)
            if value is not None:
                widget.setValue(float(value) if isinstance(widget, QDoubleSpinBox) else int(value))

        for widget, key in ((self.scale, "scale"), (self.output_format, "output")):
            value = self.settings.value(key)
            if value:
                widget.setCurrentText(str(value))

        for widget, key in (
            (self.use_motifs, "motifs"),
            (self.quartertone, "quartertone"),
            (self.lyrical_mode, "lyrical"),
        ):
            value = self.settings.value(key)
            if value is not None:
                widget.setChecked(str(value).lower() in {"1", "true", "yes"})

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("tempo", self.tempo.value())
        self.settings.setValue("root", self.root_key.value())
        self.settings.setValue("scale", self.scale.currentText())
        self.settings.setValue("base_length", self.base_length.value())
        self.settings.setValue("length_var", self.length_var.value())
        self.settings.setValue("stretch_prob", self.stretch_prob.value())
        self.settings.setValue("seed", self.seed.value())
        self.settings.setValue("output", self.output_format.currentText())
        self.settings.setValue("motifs", self.use_motifs.isChecked())
        self.settings.setValue("quartertone", self.quartertone.isChecked())
        self.settings.setValue("lyrical", self.lyrical_mode.isChecked())
        super().closeEvent(event)

    def _set_status(self, message: str) -> None:
        self.progress_label.setText(message)
        self.statusBar().showMessage(message)


def run_app(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv
    app = QApplication.instance() or QApplication(args)
    apply_theme(app)
    window = HiroMainWindow()
    window.show()
    return app.exec()


__all__ = ["HiroMainWindow", "run_app"]
