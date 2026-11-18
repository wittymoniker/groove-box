# Selected Instrument Background Tint

Applied to the available Mathematician's Groovebox source archive (`matgroovebox(35).zip`).

## Change
- The currently selected instrument's existing playlist color now supplies a very subtle ambient tint to the existing ParametricMathBackground layer (alpha 13/255).
- Tint refreshes when the selected instrument color is refreshed; the existing color swatch and playlist row tint behavior remain intact.
- The tint is painted in the existing background paint path for both user-selected image backgrounds and the generated mathematical background.
- No extra overlay widget, timer, stylesheet cascade, audio callback, or synth state mutation is introduced.
- Mirrored the implementation into root `groovebox.py` and the packaged v35.22zu, v35.22zv, and v35.22zz overlay copies to avoid build/runtime drift.

## Validation
- `python -m py_compile` passed for all four modified `groovebox.py` files.
- `pytest -q test_r32_selected_instrument_background_tint.py test_algorithm_automation_parity.py test_instrument_translation_determinism.py`: 2 passed.
- Added `test_r32_selected_instrument_background_tint.py` to assert selected-color propagation, low alpha, and both background paint modes.

## Limits
- This source archive identifies its top-level release marker as R28.4.19 while also containing v35.22zy/zz overlay directories. It is the latest Groovebox ZIP available in the Library listing, but it does not prove it is the user's currently booted ISO/source revision.
- No ISO was mastered and no live GUI/compositor test was possible in this pass. This is a source-level change only.
