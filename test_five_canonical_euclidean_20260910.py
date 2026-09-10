#!/usr/bin/env python3
"""Static release contract: Euclidean promoted to a fifth canonical."""
from pathlib import Path
SRC = Path(__file__).with_name('groovebox.py')
text = SRC.read_text(encoding='utf-8', errors='replace')
checks = {
    'five canonical visual channels': '_VISUAL_ENGINE_CHANNELS = ("seeded", "randomizer", "phase_lock", "euclidean", "goava")' in text,
    'euclidean canonical button': 'QPushButton("EUCLIDEAN")' in text,
    'playlist takes old euclidean slot': 'transport_layout_row2.insertWidget(0, self.btn_view_playlist)' in text,
    'euclidean moved to canonical row': 'global_context_layout.addWidget(self.btn_idealize_rhythm)' in text,
    'all canonical buttons matched size': '("euclidean", self.btn_idealize_rhythm)' in text and '_canon_button_size = (168, 52)' in text,
    'euclidean level slider': 'slider_level_euclidean' in text,
    'euclidean level saved in canonical level dict': '"euclidean": 1.00' in text,
    'euclidean active source': '("euclidean","btn_idealize_rhythm")' in text,
    'euclidean sequence canonical': 'canonical_order = ["goava", "phase_lock", "euclidean", "randomizer", "seeded"]' in text,
    'euclidean canonical dispatcher': 'elif engine == "euclidean":' in text,
    'euclidean own playlist source': 'mode="euclidean"' in text and 'source="euclidean"' in text,
    'five-engine full unison': 'def _full_canonical_unison_active' in text and '("seeded", "randomizer", "phase_lock", "euclidean", "goava")' in text,
    'euclidean in fingerprint': '"E" if (getattr(self, "btn_idealize_rhythm"' in text,
    'euclidean in export manifest': '"euclidean": _on("btn_idealize_rhythm")' in text,
    'euclidean restored from export provenance': '("euclidean", "btn_idealize_rhythm")' in text,
    'save schema upgraded': '"canonical_engines": {"schema": 5' in text,
    'legacy save compatibility retained': '"four_canonical"' in text,
    'euclidean visible in cross-media canonical context': '"canonical_euclidean": int("euclidean" in active)' in text and '"canonical_level_euclidean": levels["euclidean"]' in text,
    'euclidean affects visual structure': 'ch_euc = (0.5 * _lev["euclidean"] if eng.get("euclidean") else 0.0) * k5' in text,
    'euclidean affects cross-media node field': 'field["euclid_weight"] = lv' in text,
    'undo snapshot includes euclidean toggle': '"btn_idealize_rhythm", "btn_seeded_randomize"' in text,
    'ui save load includes euclidean slider': '"slider_level_seeded", "slider_level_rand", "slider_level_lock", "slider_level_euclidean", "slider_level_goava"' in text,
    'true RAND retained': 'secrets.randbits(64)' in text,
    '3D voxel retained': 'class VoxelDrawKitDialog' in text and 'def export_3d_model_dialog' in text,
}
failed=[]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL')+'  '+name)
    if not ok: failed.append(name)
if failed:
    raise SystemExit('release contract failed: '+', '.join(failed))
print(f'PASS  {len(checks)}/{len(checks)} Euclidean fifth-canonical integration checks')
