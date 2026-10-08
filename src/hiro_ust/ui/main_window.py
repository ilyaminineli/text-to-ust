"""Compact editor-oriented Hiro UST workspace."""
from __future__ import annotations

from pathlib import Path
import json
import random
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QDockWidget, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidget, QMenu, QDialogButtonBox,
)

from ..config import GeneratorConfig, HiroConfig
from ..core import HiroUSTProcessor
from ..data.example_lyrics import EXAMPLE_LYRICS
from ..melody import SCALES
from .highlighter import LyricHighlighter
from .melody_preview import MelodyPreviewPanel, SimpleMelodySynth, notes_from_output
from .theme import apply_theme


class GenerationDialog(QDialog):
    def __init__(self, owner: "HiroMainWindow"):
        super().__init__(owner)
        self.setWindowTitle("Hiro UST — Generation")
        self.resize(430, 420)
        form = QFormLayout(self)

        self.tempo = QDoubleSpinBox(); self.tempo.setRange(60, 240); self.tempo.setDecimals(1); self.tempo.setSuffix(" BPM"); self.tempo.setValue(owner.tempo.value())
        self.root = QSpinBox(); self.root.setRange(0,127); self.root.setValue(owner.root_key.value())
        self.scale = QComboBox(); self.scale.addItems(list(SCALES)); self.scale.setCurrentText(owner.scale.currentText())
        self.range_low = QSpinBox(); self.range_low.setRange(0,127); self.range_low.setValue(owner.range_low.value())
        self.range_high = QSpinBox(); self.range_high.setRange(0,127); self.range_high.setValue(owner.range_high.value())
        self.base = QSpinBox(); self.base.setRange(120,1920); self.base.setSingleStep(60); self.base.setValue(owner.base_length.value())
        self.length = QDoubleSpinBox(); self.length.setRange(0,1); self.length.setSingleStep(.05); self.length.setDecimals(2); self.length.setValue(owner.length_var.value())
        self.stretch = QDoubleSpinBox(); self.stretch.setRange(0,1); self.stretch.setSingleStep(.05); self.stretch.setDecimals(2); self.stretch.setValue(owner.stretch_prob.value())
        self.seed = QSpinBox(); self.seed.setRange(0,2_147_483_647); self.seed.setValue(owner.seed.value())
        self.motifs = QCheckBox("Use motifs"); self.motifs.setChecked(owner.use_motifs.isChecked())
        self.phrase = QCheckBox("Phrase-aware melody"); self.phrase.setChecked(owner.lyrical_mode.isChecked())
        self.quarter = QCheckBox("Quarter-tone expression"); self.quarter.setChecked(owner.quartertone.isChecked())
        self.output = QComboBox(); self.output.addItems(["ustx","ust"]); self.output.setCurrentText(owner.output_format.currentText())

        form.addRow("Tempo", self.tempo)
        form.addRow("Root MIDI", self.root)
        form.addRow("Scale", self.scale)
        form.addRow("Vocal low", self.range_low)
        form.addRow("Vocal high", self.range_high)
        form.addRow("Base length", self.base)
        form.addRow("Length variation", self.length)
        form.addRow("Stretch probability", self.stretch)
        form.addRow("Seed", self.seed)
        form.addRow(self.motifs)
        form.addRow(self.phrase)
        form.addRow(self.quarter)
        form.addRow("Output", self.output)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply(self, owner: "HiroMainWindow"):
        owner.tempo.setValue(self.tempo.value())
        owner.root_key.setValue(self.root.value())
        owner.scale.setCurrentText(self.scale.currentText())
        owner.range_low.setValue(min(self.range_low.value(), self.range_high.value() - 1))
        owner.range_high.setValue(max(self.range_high.value(), owner.range_low.value() + 1))
        owner.base_length.setValue(self.base.value())
        owner.length_var.setValue(self.length.value())
        owner.stretch_prob.setValue(self.stretch.value())
        owner.seed.setValue(self.seed.value())
        owner.use_motifs.setChecked(self.motifs.isChecked())
        owner.lyrical_mode.setChecked(self.phrase.isChecked())
        owner.quartertone.setChecked(self.quarter.isChecked())
        owner.output_format.setCurrentText(self.output.currentText())


class HiroMainWindow(QMainWindow):
    APP_NAME = "Hiro UST"
    SETTINGS_ORG = "EliLab"
    SETTINGS_APP = "HiroUST"

    def __init__(self):
        super().__init__()
        self.settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
        self.current_file: Path | None = None
        self.last_output = ""
        self.last_output_format = "ustx"
        self.last_processor: HiroUSTProcessor | None = None
        self.analysis_summary = ""
        self.melody_synth = SimpleMelodySynth()
        self.melody_selection = (0, 0)

        self.setWindowTitle(self.APP_NAME)
        self.resize(1500, 900)
        self._build_state_widgets()
        self._build_ui()
        self._build_actions()
        self._load_settings()
        self._set_status("Ready")

    def _build_state_widgets(self):
        def spin(value, lo, hi):
            w = QSpinBox(); w.setRange(lo, hi); w.setValue(value); return w
        self.tempo = QDoubleSpinBox(); self.tempo.setRange(60,240); self.tempo.setDecimals(1); self.tempo.setValue(120)
        self.root_key = spin(60,0,127)
        self.scale = QComboBox(); self.scale.addItems(list(SCALES)); self.scale.setCurrentText("Major Pentatonic")
        self.range_low = spin(48,0,127); self.range_high = spin(76,0,127)
        self.base_length = spin(240,120,1920); self.length_var = QDoubleSpinBox(); self.length_var.setRange(0,1); self.length_var.setSingleStep(.05); self.length_var.setDecimals(2); self.length_var.setValue(.3)
        self.stretch_prob = QDoubleSpinBox(); self.stretch_prob.setRange(0,1); self.stretch_prob.setSingleStep(.05); self.stretch_prob.setDecimals(2); self.stretch_prob.setValue(.25)
        self.seed = spin(1234,0,2_147_483_647)
        self.use_motifs = QCheckBox(); self.use_motifs.setChecked(True)
        self.lyrical_mode = QCheckBox(); self.lyrical_mode.setChecked(True)
        self.quartertone = QCheckBox(); self.output_format = QComboBox(); self.output_format.addItems(["ustx","ust"])

    def _build_ui(self):
        toolbar = self.addToolBar("Main"); toolbar.setMovable(False)
        self._add_menu_button(toolbar, "Project", self._project_menu())
        self._add_menu_button(toolbar, "Generation", self._generation_menu())
        self._add_menu_button(toolbar, "Analyze", self._analysis_menu())
        self._add_menu_button(toolbar, "View", self._view_menu())
        self._add_menu_button(toolbar, "Debug", self._debug_menu())
        toolbar.addSeparator()
        self.generate_action = QAction("Generate", self); self.generate_action.setShortcut("Ctrl+Enter"); toolbar.addAction(self.generate_action)
        self.export_action = QAction("Export UST", self); toolbar.addAction(self.export_action)

        central = QFrame(); central.setObjectName("panel")
        layout = QVBoxLayout(central); layout.setContentsMargins(6,6,6,6); layout.setSpacing(4)
        title_row = QHBoxLayout(); title = QLabel("Hiro UST"); title.setObjectName("title"); title_row.addWidget(title); title_row.addStretch()
        self.project_edit = QLineEdit("hiro_example"); self.project_edit.setMaximumWidth(250); title_row.addWidget(self.project_edit); layout.addLayout(title_row)
        self.melody_preview = MelodyPreviewPanel(); layout.addWidget(self.melody_preview, 1)
        self.status_label = QLabel("Ready"); self.status_label.setObjectName("eyebrow"); layout.addWidget(self.status_label)
        self.setCentralWidget(central)

        self.lyrics_dock = QDockWidget("Lyrics", self); self.lyrics_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        lyrics = QPlainTextEdit(); lyrics.setPlainText(EXAMPLE_LYRICS); self.lyrics_edit = lyrics; self.highlighter = LyricHighlighter(lyrics.document()); self.lyrics_dock.setWidget(lyrics); self.addDockWidget(Qt.LeftDockWidgetArea, self.lyrics_dock)
        self.lyrics_dock.setMinimumWidth(230)

        self.inspector_dock = QDockWidget("Inspector", self); self.inspector_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        inspector = QWidget(); il = QVBoxLayout(inspector); il.addWidget(QLabel("Selection")); self.selection_info = QLabel("No selection"); il.addWidget(self.selection_info); il.addStretch(); self.inspector_dock.setWidget(inspector); self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock); self.inspector_dock.hide()

        self.melody_preview.selectionChanged.connect(self._on_melody_selection_changed)
        self.melody_preview.selectionIndicesChanged.connect(self._on_melody_indices_changed)
        self.melody_preview.play_button.clicked.connect(self._play_full_melody)
        self.melody_preview.play_selection_button.clicked.connect(self._play_selected_melody)
        self.melody_preview.stop_button.clicked.connect(self._stop_melody)

    def _add_menu_button(self, toolbar, text, menu):
        button = QToolButton(); button.setText(text); button.setPopupMode(QToolButton.InstantPopup); button.setMenu(menu); toolbar.addWidget(button)

    def _project_menu(self):
        m = QMenu(self); a=QAction("New",self); a.triggered.connect(self.new_document); m.addAction(a); a=QAction("Open Lyrics",self); a.triggered.connect(self.open_lyrics); m.addAction(a); a=QAction("Save Lyrics",self); a.triggered.connect(self.save_lyrics); m.addAction(a); m.addSeparator(); a=QAction("Export UST",self); a.triggered.connect(self.export_project); m.addAction(a); return m
    def _generation_menu(self):
        m=QMenu(self); a=QAction("Generate",self); a.triggered.connect(self.generate); m.addAction(a); a=QAction("Generation Settings…",self); a.triggered.connect(self.open_generation_settings); m.addAction(a); a=QAction("Randomize Seed",self); a.triggered.connect(self.randomize_seed); m.addAction(a); return m
    def _analysis_menu(self):
        m=QMenu(self); a=QAction("Analyze Lyrics",self); a.triggered.connect(self.analyze_lyrics); m.addAction(a); a=QAction("Show Structure…",self); a.triggered.connect(self.show_structure); m.addAction(a); return m
    def _view_menu(self):
        m=QMenu(self); self.toggle_lyrics_action=self.lyrics_dock.toggleViewAction(); self.toggle_lyrics_action.setText("Lyrics Drawer"); m.addAction(self.toggle_lyrics_action); self.toggle_inspector_action=self.inspector_dock.toggleViewAction(); self.toggle_inspector_action.setText("Inspector"); m.addAction(self.toggle_inspector_action); return m
    def _debug_menu(self):
        m=QMenu(self); a=QAction("Load Example",self); a.triggered.connect(self.load_example); m.addAction(a); a=QAction("Debug Structure JSON",self); a.triggered.connect(self.show_debug_structure); m.addAction(a); return m

    def _build_actions(self):
        self.generate_action.triggered.connect(self.generate); self.export_action.triggered.connect(self.export_project)

    def _build_config(self):
        return GeneratorConfig(
            tempo=self.tempo.value(), base_length=self.base_length.value(), root_key=self.root_key.value(),
            range_low=self.range_low.value(), range_high=self.range_high.value(), scale=self.scale.currentText(),
            length_var=self.length_var.value(), stretch_prob=self.stretch_prob.value(), seed=self.seed.value(),
            use_motifs=self.use_motifs.isChecked(), quartertone_mode=self.quartertone.isChecked(), lyrical_mode=self.lyrical_mode.isChecked(),
        )

    def _make_processor(self):
        self.last_processor = HiroUSTProcessor(self._build_config()); return self.last_processor

    def open_generation_settings(self):
        dialog=GenerationDialog(self)
        if dialog.exec(): dialog.apply(self); self._set_status("Generation settings updated")

    def analyze_lyrics(self):
        lyrics=self.lyrics_edit.toPlainText().strip()
        if not lyrics: QMessageBox.warning(self,self.APP_NAME,"Enter lyrics before analyzing."); return False
        try:
            p=self._make_processor(); doc=p.lyric_parser.parse(lyrics,p.phonemizer)
            self.analysis_summary=f"{doc.analyzer_backend} · {doc.word_count} units · {doc.morpheme_count} tokens · {doc.kanji_word_count} Kanji units"
            self._set_status("Analysis complete"); return True
        except Exception as exc:
            QMessageBox.critical(self,self.APP_NAME,f"{type(exc).__name__}: {exc}"); return False

    def generate(self):
        lyrics=self.lyrics_edit.toPlainText().strip()
        if not lyrics: QMessageBox.warning(self,self.APP_NAME,"Enter lyrics before generating."); return
        try:
            self._set_status("Generating…"); self.analyze_lyrics(); p=self._make_processor(); self.last_output_format=self.output_format.currentText(); self.last_output=p.process_lyrics(lyrics, project_name=self.project_edit.text().strip() or "Hiro_Main", output_format=self.last_output_format); self.melody_preview.set_notes(notes_from_output(self.last_output,self.last_output_format)); self._set_status(f"Generated · {len(self.melody_preview.piano_roll.notes)} notes")
        except Exception as exc:
            QMessageBox.critical(self,self.APP_NAME,f"{type(exc).__name__}: {exc}")

    def show_structure(self):
        if not self.analyze_lyrics(): return
        p=self.last_processor; doc=p.lyric_parser.parse(self.lyrics_edit.toPlainText().strip(), p.phonemizer)
        table=QTableWidget(0,6); table.setHorizontalHeaderLabels(["Surface","Reading","POS","Unit","Flags","Phonemes"]); table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for section in doc.sections:
            for line in section.lines:
                for word in line.words:
                    row=table.rowCount(); table.insertRow(row)
                    values=[word.text,word.reading,"/".join(m.pos for m in word.morphemes if m.pos) or "—",word.text,"KANJI" if word.kanji_count else "KANA"," ".join(word.phonemes) or "—"]
                    for c,v in enumerate(values): table.setItem(row,c,QTableWidgetItem(v))
        dialog=QDialog(self); dialog.setWindowTitle("Japanese Structure"); dialog.resize(1000,650); lay=QVBoxLayout(dialog); lay.addWidget(table); dialog.exec()

    def show_debug_structure(self):
        if not self.analyze_lyrics(): return
        p=self.last_processor; doc=p.lyric_parser.parse(self.lyrics_edit.toPlainText().strip(), p.phonemizer)
        payload={"backend":doc.analyzer_backend,"sections":[{"name":s.name,"lines":[{"text":l.text,"words":[{"surface":w.text,"reading":w.reading,"morphemes":[{"surface":m.surface,"reading":m.reading,"pos":m.pos,"phonemes":m.phonemes} for m in w.morphemes]} for w in l.words]} for l in s.lines]} for s in doc.sections]}
        dialog=QDialog(self); dialog.setWindowTitle("Debug Structure"); dialog.resize(1000,700); lay=QVBoxLayout(dialog); edit=QPlainTextEdit(); edit.setReadOnly(True); edit.setPlainText(json.dumps(payload,ensure_ascii=False,indent=2)); lay.addWidget(edit); dialog.exec()

    def new_document(self): self.lyrics_edit.clear(); self.project_edit.setText("Hiro_Main"); self.last_output=""; self.melody_preview.set_notes([])
    def load_example(self): self.lyrics_edit.setPlainText(EXAMPLE_LYRICS); self.project_edit.setText("hiro_example"); self._set_status("Example loaded")
    def randomize_seed(self): self.seed.setValue(random.randint(0,2_147_483_647)); self._set_status(f"Seed: {self.seed.value()}")

    def open_lyrics(self):
        path,_=QFileDialog.getOpenFileName(self,"Open lyrics",str(Path.cwd()),"Text files (*.txt *.md *.lyrics);;All files (*)")
        if path: self.lyrics_edit.setPlainText(Path(path).read_text(encoding="utf-8")); self.project_edit.setText(Path(path).stem)
    def save_lyrics(self):
        path,_=QFileDialog.getSaveFileName(self,"Save lyrics",str(Path.cwd()/"lyrics.txt"),"Text files (*.txt);;All files (*)")
        if path: Path(path).write_text(self.lyrics_edit.toPlainText(),encoding="utf-8")
    def export_project(self):
        if not self.last_output: self.generate()
        if not self.last_output: return
        suffix=self.last_output_format; path,_=QFileDialog.getSaveFileName(self,"Export project",str(Path.cwd()/f"{self.project_edit.text().strip() or 'Hiro_Main'}.{suffix}"),f"{suffix.upper()} (*.{suffix})")
        if path: Path(path).write_text(self.last_output,encoding="utf-8"); self._set_status(f"Exported {Path(path).name}")

    def _on_melody_selection_changed(self,start,end):
        self.melody_selection=(start,end); self.selection_info.setText(f"{start}–{end} ticks")
        self._set_status(f"Selection: {start}–{end}" if end>start else "No selection")
    def _on_melody_indices_changed(self,indices): self.selection_info.setText(f"{len(indices or [])} note(s)") if indices else self.selection_info.setText("No selection")
    def _play_full_melody(self):
        try: self.melody_synth.play(self.melody_preview.piano_roll.notes,self.tempo.value()); self._set_status("Playing melody")
        except Exception as exc: QMessageBox.warning(self,self.APP_NAME,str(exc))
    def _play_selected_melody(self):
        notes=self.melody_preview.piano_roll.selected_notes()
        if not notes: return
        try: self.melody_synth.play(notes,self.tempo.value(),self.melody_selection); self._set_status("Playing selection")
        except Exception as exc: QMessageBox.warning(self,self.APP_NAME,str(exc))
    def _stop_melody(self): self.melody_synth.stop(); self._set_status("Stopped")
    def _set_status(self,text): self.status_label.setText(f"{self.analysis_summary} · {text}" if self.analysis_summary else text)

    def _load_settings(self):
        if not self.lyrics_edit.toPlainText().strip(): self.load_example()
    def closeEvent(self,event): super().closeEvent(event)


def run_app(argv: list[str] | None = None) -> int:
    args=argv if argv is not None else sys.argv
    app=QApplication.instance() or QApplication(args); apply_theme(app); window=HiroMainWindow(); window.show(); return app.exec()


__all__=["HiroMainWindow","run_app"]
