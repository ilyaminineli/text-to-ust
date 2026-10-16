from hiro_ust.config import GeneratorConfig
from hiro_ust.core import HiroUSTProcessor
from hiro_ust.converter.phonemizer import Phonemizer
from hiro_ust.generator import USTWriter
from hiro_ust.generator.ustx_writer import USTXWriter
from hiro_ust.melody.melody_logic import MelodyBrain
from hiro_ust.melody.phrase_engine import PhraseMelodyEngine


def test_generator_config_aliases():
    config = GeneratorConfig(intone_level="Tight (1)")
    assert config.intone == "Tight (1)"
    assert config.effective_root_key == 60


def test_phonemizer_preserves_phrase_punctuation():
    phonemes = Phonemizer().text_to_phonemes("こんにちは。")
    assert phonemes[-1] == "。"


def test_ust_writer_preserves_fractional_pitch_intent():
    writer = USTWriter("test", 120)
    writer.add_note(240, "a", 60.5, 0, 0, 80, "0,10,35,0,100,100,0")
    text = writer.finalize()
    assert "NoteNum=60" in text
    assert "PBY=25" in text


def test_ustx_writer_restores_tuning_expression():
    writer = USTXWriter("test", 120)
    writer.add_note(
        length=720,
        lyric="a",
        note_num=60,
        pre_utter=25,
        voice_overlap=10,
        intensity=90,
        envelope="Pop",
        pbs="0;-35",
    )
    assert len(writer.notes) == 1
    note = writer.notes[0]
    assert note["pitch"]["data"]
    assert note["pitch"]["data"][-1]["y"] == 0
    assert "vibrato" in note
    assert note["vibrato"]["length"] >= 0


def test_melody_seed_is_reproducible():
    kwargs = dict(root_midi=60, scale_name="Major Pentatonic", phoneme="a")
    a = MelodyBrain(seed=42).get_smart_note(**kwargs)
    b = MelodyBrain(seed=42).get_smart_note(**kwargs)
    assert a == b

def test_ustx_writer_preserves_fractional_pitch_as_cents():
    writer = USTXWriter("test", 120)
    writer.add_note(
        length=120,
        lyric="a",
        note_num=60.5,
        pre_utter=0,
        voice_overlap=0,
        intensity=80,
        envelope="Pop",
    )
    note = writer.notes[0]
    assert note["tone"] == 60
    assert note["pitch"]["data"][0]["y"] == 50


def test_phrase_engine_can_disable_motifs_and_flatten_notes():
    engine = PhraseMelodyEngine(seed=7)
    plan = engine.plan_phrase(5, 60, use_motifs=False)
    assert engine.motifs == []
    pitches = engine.render_phrase(
        plan,
        root=60,
        scale=[0, 2, 4, 7, 9],
        low=48,
        high=76,
        flat_mode=True,
    )
    assert len(pitches) == 5
    assert len(set(pitches)) == 1


def test_processor_reuse_is_deterministic():
    processor = HiroUSTProcessor(GeneratorConfig(seed=42))
    first = processor.process_lyrics("あ い う", output_format="ust")
    second = processor.process_lyrics("あ い う", output_format="ust")
    assert first == second
