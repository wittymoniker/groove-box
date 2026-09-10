from pathlib import Path
p=Path(__file__).with_name('groovebox.py')
s=p.read_text(encoding='utf-8')
checks = [
 ('voxel panel embedded', 'self._main_voxel_tab_index = tabs.addTab(voxel, "🧊 3D Voxel Draw / Record")' in s),
 ('standalone launch button removed', 'self.btn_voxel_draw_kit = QPushButton' not in s),
 ('compat opener routes shared window', 'Compatibility entry point: open shared Draw/Record and select its voxel tab.' in s),
 ('full model preview', 'class VoxelModelPreview(QWidget):' in s and 'FULL MODEL REFERENCE' in s),
 ('indexed xy slice grid', 'X/Y INDEX · Z' in s),
 ('color chooser', 'QColorDialog.getColor' in s and 'Voxel Color:' in s),
 ('blend slider', "blend_slider.setRange(0,100)" in s and "Voxel Blend:" in s),
 ('blend undo checkpoint', "_push_undo('Voxel paint blend')" in s),
 ('rgba voxel schema', 'old XYZ-only projects normalize on load' in s and 'def _normalize_voxel_record' in s),
 ('legacy xyz compatibility', 'rgba=[80,220,200,220]' in s),
 ('state saves color', '"paint_color"' in s and '"paint_blend_pct"' in s),
 ('state restores color', 'self.voxel_paint_color = ' in s and 'self.voxel_paint_blend_pct = ' in s),
 ('undo snapshot includes paint state', '"voxel_paint_color", "voxel_paint_blend_pct", "voxel_cells"' in s),
 ('video voxelization uses RGB', "format=rgb24" in s and "records[(x,y,min(n-1,z0+dz))]=[rr,gg,bb,alpha]" in s),
 ('live/offline renderer uses voxel rgb', 'col=np.asarray([float(c[3])/255.0,float(c[4])/255.0,float(c[5])/255.0]' in s),
 ('renderer uses voxel alpha', 'voxel_alpha=float(np.clip(float(c[6])/255.0' in s),
 ('PLY exports RGBA', 'property uchar red' in s and 'property uchar alpha' in s),
 ('OBJ exports material blend', "mtllib {mtl_name}" in s and "d {a/255:.6f}" in s),
 ('fingerprint includes rich voxels', 'tuple(self._normalize_voxel_record(v) or [])' in s),
 ('full model highlights active slice', 'if z == zsel' in s and 'selected Z {zsel}' in s),
]
failed=[]
for name, ok in checks:
 print(('PASS' if ok else 'FAIL').ljust(5), name)
 if not ok: failed.append(name)
if failed: raise SystemExit('FAILED: '+', '.join(failed))
print(f'PASS  {len(checks)}/{len(checks)} Draw/Record voxel merge checks')
