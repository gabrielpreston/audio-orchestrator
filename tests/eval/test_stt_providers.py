from pathlib import Path

from scripts.eval_stt import read_phrases, normalize_text


def test_phrase_parsing() -> None:
    files = [
        Path("tests/fixtures/phrases/en/wake.txt"),
        Path("tests/fixtures/phrases/en/core.txt"),
        Path("tests/fixtures/phrases/en/non_wake.txt"),
        Path("tests/fixtures/phrases/en/confusers.txt"),
    ]
    for phrase_file in files:
        assert phrase_file.exists(), f"Missing phrase file: {phrase_file}"
        phrases = read_phrases([phrase_file])
        assert len(phrases) > 0
        for p in phrases:
            assert normalize_text(p)
