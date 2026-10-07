"""Main PySide6 application window.

The UI is an editor around the UI-independent HiroUSTProcessor.
"""
from __future__ import annotations

from pathlib import Path
import json
import random
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
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
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import GeneratorConfig, HiroConfig
from ..core import HiroUSTProcessor
from ..data.example_lyrics import EXAMPLE_LYRICS
from ..melody import SCALES
from .highlighter import LyricHighlighter
from .melody_preview import MelodyPreviewPanel, SimpleMelodySynth, notes_from_output
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
        self.last_processor: HiroUSTProcessor | None = None
        self.analysis_summary = ""
        self.melody_synth = SimpleMelodySynth()
        self.melody_selection: tuple[int, int] = (0, 0)

        self.setWindowTitle(self.APP_NAME)
        self.resize(1500, 920)
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
        self.generate_action.setShortcut("Ctrl+Enter")
        self.export_action = QAction("Export UST", self)

        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.generate_action)
        toolbar.addAction(self.export_action)

        advanced = QToolButton()
        advanced.setText("More")
        advanced.setPopupMode(QToolButton.InstantPopup)
        from PySide6.QtWidgets import QMenu
        advanced_menu = QMenu(advanced)
        self.analyze_action = QAction("Analyze Lyrics", self)
        self.random_seed_action = QAction("Randomize Seed", self)
        self.load_example_action = QAction("Load Example", self)
        self.debug_action = QAction("Show Debug Structure", self)
        advanced_menu.addAction(self.analyze_action)
        advanced_menu.addAction(self.random_seed_action)
        advanced_menu.addSeparator()
        advanced_menu.addAction(self.load_example_action)
        advanced_menu.addAction(self.debug_action)
        advanced.setMenu(advanced_menu)
        toolbar.addWidget(advanced)

        self._build_menus()

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
        subtitle = QLabel("lyrics → words → morphemes → melody → UST / USTX")
        subtitle.setObjectName("eyebrow")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.project_edit = QLineEdit("Hiro_Main")
        self.project_edit.setPlaceholderText("Project name")
        self.project_edit.setMaximumWidth(280)
        header.addWidget(self.project_edit)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        lyrics_panel = self._make_panel("LYRICS")
        self.lyrics_edit = QPlainTextEdit()
        self.lyrics_edit.setPlaceholderText(
            "Paste Japanese lyrics here…\n\n"
            "Section markers:\n"
            "[Verse 1]\n"
            "[Chorus]"
        )
        self.highlighter = LyricHighlighter(self.lyrics_edit.document())
        lyrics_panel.layout().addWidget(self.lyrics_edit, 1)

        analysis_panel = self._make_panel("ANALYSIS / PREVIEW")
        self.analysis_label = QLabel("No analysis yet.")
        self.analysis_label.setWordWrap(True)
        analysis_panel.layout().addWidget(self.analysis_label)

        self.preview_tabs = QTabWidget()

        self.structure_table = QTableWidget(0, 6)
        self.structure_table.setHorizontalHeaderLabels(
            ["Surface", "Reading", "POS", "Unit", "Flags", "Phonemes"]
        )
        self.structure_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.structure_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.structure_table.horizontalHeader().setStretchLastSection(True)

        self.notes_table = QTableWidget(0, 5)
        self.notes_table.setHorizontalHeaderLabels(
            ["#", "Lyric", "MIDI", "Length", "Position"]
        )
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notes_table.horizontalHeader().setStretchLastSection(True)

        self.melody_preview = MelodyPreviewPanel()
        self.melody_preview.selectionChanged.connect(self._on_melody_selection_changed)
        self.melody_preview.play_button.clicked.connect(self._play_full_melody)
        self.melody_preview.play_selection_button.clicked.connect(self._play_selected_melody)
        self.melody_preview.stop_button.clicked.connect(self._stop_melody)

        self.preview_tabs.addTab(self.structure_table, "Structure")
        self.preview_tabs.addTab(self.melody_preview, "Melody")
        self.preview_tabs.addTab(self.notes_table, "Notes")
        analysis_panel.layout().addWidget(self.preview_tabs, 1)

        settings_panel = self._make_panel("INSPECTOR")

        inspector_tabs = QTabWidget()
        inspector_tabs.setObjectName("inspector")

        song_tab = QWidget()
        song_form = QFormLayout(song_tab)
        song_form.setContentsMargins(4, 4, 4, 4)

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

        self.output_format = QComboBox()
        self.output_format.addItems(["ustx", "ust"])

        song_form.addRow("Tempo", self.tempo)
        song_form.addRow("Root", self.root_key)
        song_form.addRow("Scale", self.scale)
        song_form.addRow("Base length", self.base_length)
        song_form.addRow("Output", self.output_format)

        melody_tab = QWidget()
        melody_form = QFormLayout(melody_tab)
        melody_form.setContentsMargins(4, 4, 4, 4)

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

        self.use_motifs = QCheckBox("Use motifs")
        self.use_motifs.setChecked(True)
        self.lyrical_mode = QCheckBox("Phrase-aware melody")
        self.lyrical_mode.setChecked(True)

        melody_form.addRow("Length variation", self.length_var)
        melody_form.addRow("Stretch probability", self.stretch_prob)
        melody_form.addRow("Seed", self.seed)
        melody_form.addRow(self.use_motifs)
        melody_form.addRow(self.lyrical_mode)

        expression_tab = QWidget()
        expression_form = QFormLayout(expression_tab)
        expression_form.setContentsMargins(4, 4, 4, 4)
        self.quartertone = QCheckBox("Quarter-tone expression")
        expression_form.addRow(self.quartertone)
        expression_form.addRow(QLabel(
            "Expression controls will grow here as the editor gains "
            "note-level and phrase-level editing."
        ))

        inspector_tabs.addTab(song_tab, "Song")
        inspector_tabs.addTab(melody_tab, "Melody")
        inspector_tabs.addTab(expression_tab, "Expression")
        settings_panel.layout().addWidget(inspector_tabs, 1)

        splitter.addWidget(lyrics_panel)
        splitter.addWidget(analysis_panel)
        splitter.addWidget(settings_panel)
        splitter.setSizes([520, 700, 320])
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

    def _make_panel(self, title_text: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("section")
        layout.addWidget(title)
        return panel

    def _build_menus(self) -> None:
        bar = self.menuBar()

        project = bar.addMenu("Project")
        project.addAction(self.new_action)
        project.addAction(self.open_action)
        project.addAction(self.save_action)
        project.addSeparator()
        project.addAction(self.export_action)

        generation = bar.addMenu("Generation")
        generation.addAction(self.generate_action)
        generation.addAction(self.random_seed_action)

        analysis = bar.addMenu("Analyze")
        analysis.addAction(self.analyze_action)
        analysis.addAction(self.debug_action)

        debug_menu = bar.addMenu("Debug")
        debug_menu.addAction(self.load_example_action)
        debug_menu.addAction(self.debug_action)

    def _build_actions(self) -> None:
        self.new_action.triggered.connect(self.new_document)
        self.open_action.triggered.connect(self.open_lyrics)
        self.save_action.triggered.connect(self.save_lyrics)
        self.generate_action.triggered.connect(self.generate)
        self.export_action.triggered.connect(self.export_project)
        self.analyze_action.triggered.connect(self.analyze_lyrics)
        self.random_seed_action.triggered.connect(self.randomize_seed)
        self.load_example_action.triggered.connect(self.load_example)
        self.debug_action.triggered.connect(self.show_debug_structure)

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

    def _make_processor(self) -> HiroUSTProcessor:
        processor = HiroUSTProcessor(self._build_config())
        self.last_processor = processor
        return processor

    def analyze_lyrics(self) -> bool:
        lyrics = self.lyrics_edit.toPlainText().strip()
        if not lyrics:
            QMessageBox.warning(self, self.APP_NAME, "Enter lyrics before analyzing.")
            return False

        try:
            processor = self._make_processor()
            doc = processor.lyric_parser.parse(lyrics, processor.phonemizer)
            self._populate_structure(doc)
            self.analysis_summary = (
                f"Backend: {doc.analyzer_backend} · "
                f"Sections: {len(doc.sections)} · Words: {doc.word_count} · "
                f"Morphemes: {doc.morpheme_count} · Kanji morphemes: {doc.kanji_word_count}"
            )
            self.analysis_label.setText(self.analysis_summary)
            self.preview_tabs.setCurrentWidget(self.structure_table)
            self._set_status("Analysis complete")
            return True
        except Exception as exc:
            self._set_status("Analysis failed")
            QMessageBox.critical(self, self.APP_NAME, f"{type(exc).__name__}: {exc}")
            return False

    def _populate_structure(self, doc) -> None:
        self.structure_table.setRowCount(0)
        for section in doc.sections:
            for line in section.lines:
                for word in line.words:
                    for morpheme in word.morphemes:
                        row = self.structure_table.rowCount()
                        self.structure_table.insertRow(row)
                        flags = []
                        if morpheme.is_kanji:
                            flags.append("KANJI")
                        elif morpheme.token.kana:
                            flags.append("KANA")
                        if morpheme.is_punctuation:
                            flags.append("PUNCT")
                        values = [
                            morpheme.surface,
                            morpheme.reading or "—",
                            morpheme.pos or "—",
                            word.text,
                            ", ".join(flags) or "—",
                            " ".join(morpheme.phonemes) or "—",
                        ]
                        for column, value in enumerate(values):
                            self.structure_table.setItem(row, column, QTableWidgetItem(value))

    def generate(self) -> None:
        lyrics = self.lyrics_edit.toPlainText().strip()
        if not lyrics:
            QMessageBox.warning(self, self.APP_NAME, "Enter lyrics before generating.")
            return

        self._set_status("Generating…")
        self.generate_action.setEnabled(False)
        QApplication.processEvents()

        try:
            if not self.analyze_lyrics():
                return
            processor = self._make_processor()
            output_format = self.output_format.currentText()
            self.last_output = processor.process_lyrics(
                lyrics,
                project_name=self.project_edit.text().strip() or "Hiro_Main",
                output_format=output_format,
            )
            self.last_output_format = output_format
            self._refresh_notes_preview(self.last_output)
            self.preview_tabs.setCurrentWidget(self.melody_preview)
            self._set_status("Generation complete")
        except Exception as exc:
            self._set_status("Generation failed")
            QMessageBox.critical(self, self.APP_NAME, f"{type(exc).__name__}: {exc}")
        finally:
            self.generate_action.setEnabled(True)

    def _refresh_notes_preview(self, output: str) -> None:
        notes = notes_from_output(output, self.last_output_format)
        self.melody_preview.set_notes(notes)

        self.notes_table.setRowCount(0)
        for index, note in enumerate(notes[:500], 1):
            row = self.notes_table.rowCount()
            self.notes_table.insertRow(row)
            values = [
                str(index),
                note.lyric,
                str(note.tone),
                str(note.duration),
                str(note.position),
            ]
            for column, value in enumerate(values):
                self.notes_table.setItem(row, column, QTableWidgetItem(value))

        generated = f" · Generated notes: {len(notes)}"
        self.analysis_label.setText(f"{self.analysis_summary}{generated}")

    def _on_melody_selection_changed(self, start: int, end: int) -> None:
        self.melody_selection = (start, end)
        if end > start:
            self._set_status(f"Melody range selected: {start}–{end} ticks")
        elif self.last_output:
            self._set_status("Melody preview ready")

    def _play_full_melody(self) -> None:
        notes = self.melody_preview.piano_roll.notes
        if not notes:
            return
        try:
            self.melody_synth.play(notes, self.tempo.value())
            self._set_status("Playing melody preview")
        except Exception as exc:
            QMessageBox.warning(self, self.APP_NAME, f"Audio preview unavailable: {exc}")

    def _stop_melody(self) -> None:
        self.melody_synth.stop()
        self._set_status("Melody preview stopped")

    def _play_selected_melody(self) -> None:
        notes = self.melody_preview.piano_roll.selected_notes()
        if not notes:
            return
        start, end = self.melody_selection
        try:
            self.melody_synth.play(notes, self.tempo.value(), (start, end))
            self._set_status(f"Playing selected melody range: {start}–{end}")
        except Exception as exc:
            QMessageBox.warning(self, self.APP_NAME, f"Audio preview unavailable: {exc}")

    def show_debug_structure(self) -> None:
        if not self.analyze_lyrics():
            return

        processor = self.last_processor
        if processor is None:
            return
        doc = processor.lyric_parser.parse(
            self.lyrics_edit.toPlainText().strip(),
            processor.phonemizer,
        )

        payload = {
            "backend": doc.analyzer_backend,
            "sections": [
                {
                    "name": section.name,
                    "lines": [
                        {
                            "text": line.text,
                            "words": [
                                {
                                    "surface": word.text,
                                    "reading": word.reading,
                                    "structure": word.structure,
                                    "morphemes": [
                                        {
                                            "surface": m.surface,
                                            "reading": m.reading,
                                            "lemma": m.token.lemma,
                                            "normalized": m.token.normalized,
                                            "pos": m.pos,
                                            "phonemes": m.phonemes,
                                            "kanji": m.is_kanji,
                                        }
                                        for m in word.morphemes
                                    ],
                                }
                                for word in line.words
                            ],
                        }
                        for line in section.lines
                    ],
                }
                for section in doc.sections
            ],
        }

        dialog = QDialog(self)
        dialog.setWindowTitle("Hiro UST — Debug Structure")
        dialog.resize(1000, 700)
        layout = QVBoxLayout(dialog)
        debug_edit = QPlainTextEdit()
        debug_edit.setReadOnly(True)
        debug_edit.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
        layout.addWidget(debug_edit)
        dialog.exec()

    def randomize_seed(self) -> None:
        self.seed.setValue(random.randint(0, 2_147_483_647))
        self._set_status(f"Seed: {self.seed.value()}")

    def load_example(self) -> None:
        self.current_file = None
        self.last_output = ""
        self.project_edit.setText("hiro_example")
        self.lyrics_edit.setPlainText(EXAMPLE_LYRICS)
        self.notes_table.setRowCount(0)
        self.structure_table.setRowCount(0)
        self.melody_preview.set_notes([])
        self.analysis_summary = ""
        self.analysis_label.setText("Example loaded. Analyze or Generate.")
        self._set_status("Example lyrics loaded")

    def new_document(self) -> None:
        self.current_file = None
        self.last_output = ""
        self.project_edit.setText("Hiro_Main")
        self.lyrics_edit.clear()
        self.notes_table.setRowCount(0)
        self.structure_table.setRowCount(0)
        self.melody_preview.set_notes([])
        self.analysis_summary = ""
        self.analysis_label.setText("No analysis yet.")
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
        default = self.current_file or (
            Path.cwd() / f"{self.project_edit.text().strip() or 'Hiro_Main'}.txt"
        )
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
                widget.setValue(
                    float(value) if isinstance(widget, QDoubleSpinBox) else int(value)
                )

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

        if not self.lyrics_edit.toPlainText().strip():
            self.load_example()

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
