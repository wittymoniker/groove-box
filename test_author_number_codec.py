from decimal import Decimal
from author_number_codec import (
    spell_number, decode_spelling, decode_authored, fractional_cell_value,
    PRECOMPUTED_VARIANT_COUNT, SCHEME,
)

def test_codec():
    assert PRECOMPUTED_VARIANT_COUNT == 68
    assert SCHEME == 'base16-squiggle-subscale-v4'

    p = spell_number('1.5')
    assert p.integer_values == (1,)
    assert p.half_squiggle is True
    assert p.fractional_cells == ()
    assert decode_spelling(p) == Decimal('1.5')

    p = spell_number('1.25')
    assert p.integer_values == (1,)
    assert p.half_squiggle is False
    assert [c.variant.value for c in p.fractional_cells] == [4]
    assert decode_spelling(p) == Decimal('1.25')

    p = spell_number('1.20')
    assert p.integer_values == (1,)
    assert p.half_squiggle is False
    assert len(p.fractional_cells) == 2
    assert [c.variant.value for c in p.fractional_cells] == [3,3]
    assert p.error <= Decimal('0.005')
    assert Decimal(p.source_text) == Decimal('1.20')

    p = spell_number('16')
    assert p.integer_values == (16,)
    assert p.fractional_cells == ()
    assert decode_spelling(p) == Decimal(16)

    p = spell_number('16.5')
    assert p.integer_values == (16,)
    assert p.half_squiggle is True
    assert decode_spelling(p) == Decimal('16.5')

    assert fractional_cell_value(4, 1, True) == Decimal('0.25')
    assert fractional_cell_value(4, 1, False) == Decimal('0.125')
    assert decode_authored((1,), fractional_cells=((4, True),)) == Decimal('1.25')
    assert decode_authored((1,), fractional_cells=((4, False),)) == Decimal('1.125')

    # Integer shortening: visible zeros do not force dead fractional cells.
    p = spell_number('2.00')
    assert p.integer_values == (2,)
    assert p.fractional_cells == ()

    # Negative direction/sign is semantic, not another number cell.
    p = spell_number('-1.5')
    assert p.negative and decode_spelling(p) == Decimal('-1.5')

if __name__ == '__main__':
    test_codec()
    for txt in ('1.5','1.25','1.20','16','16.5','3.14159','0.1','255','256'):
        p=spell_number(txt)
        print(txt, p.to_dict())
