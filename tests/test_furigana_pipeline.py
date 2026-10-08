from hiro_ust.analyzer.japanese import normalize_reading


def test_normalize_reading_expands_long_vowel_marker():
    assert normalize_reading("すたーず") == "すたあず"
