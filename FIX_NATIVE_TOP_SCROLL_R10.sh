#!/usr/bin/env bash
# Restore the main workspace's native two-dimensional side-scroll behavior.
# Run from the project root; this intentionally does not build or test the ISO.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
source = root / "groovebox.py"
if not source.is_file():
    raise SystemExit(f"FAIL: missing {source}")
text = source.read_text(encoding="utf-8")
marker = "GROOVEBOX_R10_NATIVE_TOP_SCROLL_RESTORED_20261104"
if marker in text:
    print("PASS: native top-scroll fix already applied")
else:
    anchor = text.find("# STRUCTURAL_SCROLL_2026")
    start = text.find("        top_scroll = QScrollArea()", anchor)
    if anchor < 0 or start < 0:
        raise SystemExit("FAIL: could not locate the main STRUCTURAL_SCROLL_2026 top-scroll block")
    end = text.find("        top_scroll.setAlignment", start)
    if end < 0:
        raise SystemExit("FAIL: top-scroll block is incomplete; no alignment setup found")
    old = text[start:end]
    if "self._wrap_wide_main_rows()" not in old or "top_scroll.setWidgetResizable(True)" not in old:
        raise SystemExit("FAIL: top-scroll block differs from the expected responsive-wrap regression; no changes made")
    new = '''        top_scroll = QScrollArea()
        # GROOVEBOX_R10_NATIVE_TOP_SCROLL_RESTORED_20261104:
        # Preserve the main control deck's native two-dimensional layout. The
        # responsive-wrap pass stacked long control strips and made the top pane
        # track the viewport, removing the horizontal side-scroll workspace.
        # Keep the content at its natural layout size; QScrollArea exposes both
        # scrollbars as needed without stretching or wrapping the control deck.
        top_content.adjustSize()
        _top_native = top_content.sizeHint()
        top_content.setMinimumSize(max(1, _top_native.width()), max(1, _top_native.height()))
        top_scroll.setWidgetResizable(False)
'''
    source.write_text(text[:start] + new + text[end:], encoding="utf-8")
    print("PASS: restored native-size main top scroll in groovebox.py")

# Refresh the active ISO payload directly as well as running the project's sync.
active = root / "BUILD_ISO" / "app-overlay-v35.22zz" / "groovebox.py"
if not active.parent.is_dir():
    raise SystemExit(f"FAIL: active ISO overlay not found: {active.parent}")
active.write_bytes(source.read_bytes())
print("PASS: active v35.22zz overlay updated")
PY
bash "$ROOT/BUILD_ISO/sync_overlay_from_root.sh"
python3 -m py_compile "$ROOT/groovebox.py" "$ROOT/BUILD_ISO/app-overlay-v35.22zz/groovebox.py"
python3 "$ROOT/BUILD_ISO/verify_v35_22zz_r10.py" "$ROOT"
cmp -s "$ROOT/groovebox.py" "$ROOT/BUILD_ISO/app-overlay-v35.22zz/groovebox.py"
echo "PASS: root and active ISO overlay are identical"
echo "DONE: native top scrolling restored; no ISO build or boot was run."
