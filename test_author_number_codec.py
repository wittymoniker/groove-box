from decimal import Decimal
from author_number_codec import *

assert SCHEME == 'base16-squiggle-crossbar-subscale-v7'
assert PRECOMPUTED_VARIANT_COUNT == 5188
assert glyph_variant(16).solid_mask == 15 and glyph_variant(16).dotted_mask == 0
assert tuple(glyph_variant(16).crossbar_value(i) for i in range(4)) == (Decimal(1),)*4
v = glyph_variant(5, solid_mask=0b0101, dotted_mask=0b1010)
assert tuple(v.crossbar_value(i) for i in range(4)) == (Decimal(1), Decimal('0.5'), Decimal(1), Decimal('0.5'))
assert v.variant_index >= 0 and v.variant_index < 5188
assert spell_number('1.5').half_squiggle
assert decode_spelling(spell_number('1.5')) == Decimal('1.5')
sp=spell_number('1.25')
assert sp.fractional_cells[0].variant.value == 4
assert sp.fractional_cells[0].variant.solid_mask == 0
assert decode_authored([1], fractional_cells=[(4,True)]) == Decimal('1.25')
assert decode_authored([1], fractional_cells=[(4,False)]) == Decimal('1.125')
sv=set_fraction_spacing(sp,1,False)
assert sv.fractional_cells[0].variant.spaced is False
manifest=scheme_manifest()
assert manifest['precomputed_variant_count'] == 5188
assert manifest['divider_semantics']['crossbar_count_per_glyph'] == 4
print('PASS author number codec crossbars', PRECOMPUTED_VARIANT_COUNT)
sp16 = spell_number('16')
assert sp16.integer_variants()[0].solid_mask == 15
sp5 = set_integer_crossbars(spell_number('5'), 0, solid_mask=0b0011, dotted_mask=0b1100)
iv = sp5.integer_variants()[0]
assert tuple(iv.crossbar_value(i) for i in range(4)) == (Decimal(1), Decimal(1), Decimal('0.5'), Decimal('0.5'))
roundtrip = spelling_from_dict(sp5.to_dict())
assert roundtrip.integer_variants()[0].solid_mask == 0b0011
assert roundtrip.integer_variants()[0].dotted_mask == 0b1100
print('PASS integer crossbar authored packets')

# Full-cycle 16 is invariant: alternate crossbar masks are invalid.
try:
    glyph_variant(16, solid_mask=0, dotted_mask=15)
    raise AssertionError("16 accepted non-solid subdividers")
except ValueError:
    pass
assert glyph_variant(16).solid_mask == 15 and glyph_variant(16).dotted_mask == 0
print("PASS full-cycle 16 invariant: 12 solid main strokes + 4 solid subdividers")
