from pathlib import Path

SRC = (Path(__file__).with_name('groovebox.py')).read_text(encoding='utf-8')


def test_background_uses_full_book_series_and_meum_identities():
    assert '(M−1)^M + (M−1)^(1/M) = 2^M/M² − M' in SRC
    assert 'isn⁻¹(x) = Σₙ₌₀^∞ [(2n)!·x^(2n+1)] / [16^n·(n!)²·(2n+1)]' in SRC
    assert 'ics⁻¹(x) = π − Σₙ₌₀^∞' in SRC
    assert 'isn(x) = Σₙ₌₁^∞ [x^(2n)/(2n)!]·i^n' in SRC
    assert '1 − isn(x) = Σₙ₌₀^∞ [x^(2n)/(2n)!]·i^(n−1)' in SRC
    assert 'π = Σₙ₌₀^∞ [(2n)!·2^(1−2n)] / [(n!)²·(2n+1)]' in SRC


def test_outdated_compact_background_entries_are_removed():
    block = SRC[SRC.index('MEUM_EQUATION_CELLS = ('):SRC.index('def _paint_meum_equation_cells')]
    assert 'isn(x) = 2·sin(x/2)' not in block
    assert 'ics(x) = 2·cos(x/2)' not in block
    assert 'ics⁻¹(y) = 2·acos(y/2)' not in block


def test_background_still_draws_twelve_cells_per_frame():
    body = SRC[SRC.index('def _paint_meum_equation_cells'):SRC.index('MEUM_BLOCKS = (')]
    assert 'range(min(12, len(_all)))' in body
