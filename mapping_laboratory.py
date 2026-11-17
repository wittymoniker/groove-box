"""Math-first mapping laboratory: inspect transformations without rewriting source data."""
from __future__ import annotations

def open_mapping_laboratory(parent=None, values=None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPainter, QPen
    from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QDoubleSpinBox,QSpinBox,QWidget,QFormLayout)
    import automation_math as am
    class Curve(QWidget):
        def __init__(self): super().__init__(); self.mode='linear'; self.exponent=2.0; self.coefficients=(0.0,1.0,0.0,0.0); self.depth=1; self.res=0; self.data=[]; self.setMinimumHeight(180)
        def paintEvent(self, ev):
            p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); r=self.rect().adjusted(24,12,-12,-24)
            p.setPen(QPen(self.palette().mid().color(),1)); p.drawRect(r)
            p.setPen(QPen(self.palette().text().color(),2)); last=None
            for i in range(401):
                x=i/400; y=am.transform_ex(x,self.mode,exponent=self.exponent,coefficients=self.coefficients,depth=self.depth,resolution=self.res)
                pt=(r.left()+x*r.width(),r.bottom()-y*r.height())
                if last is not None: p.drawLine(int(last[0]),int(last[1]),int(pt[0]),int(pt[1]))
                last=pt
            if self.data:
                p.setPen(QPen(self.palette().highlight().color(),3)); n=len(self.data)
                for i,v in enumerate(self.data):
                    y=am.transform_ex(v,self.mode,exponent=self.exponent,coefficients=self.coefficients,depth=self.depth,resolution=self.res)
                    p.drawPoint(int(r.left()+i/max(1,n-1)*r.width()), int(r.bottom()-y*r.height()))
            p.end()
    dlg=QDialog(parent); dlg.setWindowTitle('Mathematical Mapping Laboratory'); dlg.resize(760,520)
    lay=QVBoxLayout(dlg); lay.addWidget(QLabel('Dimensionless mapping preview · source values remain unchanged'))
    row=QHBoxLayout(); mode=QComboBox(); mode.addItems(list(am.TRANSFORMS)); exp=QDoubleSpinBox(); exp.setRange(.05,32); exp.setDecimals(3); exp.setValue(2); exp.setPrefix('Exponent / root degree ')
    resolution=QSpinBox(); resolution.setRange(16,65536); resolution.setValue(1024); resolution.setPrefix('Samples ')
    depth=QSpinBox(); depth.setRange(1,64); depth.setValue(1); depth.setPrefix('Iteration depth ')
    levels=QSpinBox(); levels.setRange(0,65536); levels.setValue(0); levels.setPrefix('Resolution levels '); levels.setSpecialValueText('Resolution: continuous')
    src=QComboBox(); src.addItems(['(given values)','Seed values','Canonical: selected sequence pitches','User: selected sequence amplitudes','Combined'])
    row.addWidget(mode,1); row.addWidget(exp); row.addWidget(resolution); row.addWidget(depth); row.addWidget(levels); lay.addLayout(row)
    row2=QHBoxLayout(); row2.addWidget(QLabel('Analyse')); row2.addWidget(src,1); lay.addLayout(row2)
    coeffs=[]; coeff_form=QFormLayout()
    for i, default in enumerate((0.0, 1.0, 0.0, 0.0)):
        spin=QDoubleSpinBox(); spin.setRange(-32.0,32.0); spin.setDecimals(5); spin.setSingleStep(0.1); spin.setValue(default)
        coeffs.append(spin); coeff_form.addRow(f'Polynomial coefficient x^{i}', spin)
    lay.addLayout(coeff_form)
    curve=Curve(); lay.addWidget(curve)
    report=QLabel('Representation analysis is advisory; it never overwrites Seed, Canonical or User values.'); report.setWordWrap(True); lay.addWidget(report)
    def update(*_):
        curve.mode=mode.currentText(); curve.exponent=exp.value(); curve.coefficients=tuple(c.value() for c in coeffs)
        curve.depth=depth.value(); curve.res=levels.value(); data=_source(src.currentIndex()); curve.data=data[:4096]; curve.update()
        for spin in coeffs: spin.setEnabled(curve.mode == 'polynomial')
        try:
            result=am.ideal_representation(data); rec=am.recommend(data)
            report.setText(f"Preview: {curve.mode} · exponent/root degree {exp.value():.3f} · depth {depth.value()} · "
                           f"{'continuous' if not levels.value() else str(levels.value())+' levels'} · {resolution.value()} samples\n"
                           f"Shape suggestion: {result.get('mode')} · fit {result.get('score',0):.3f} · {result.get('count',0)} values\n"
                           f"Most efficient lossless form: {rec.get('representation')} · {rec.get('parameters')} parameter(s) instead of {rec.get('original_count', len(data))}")
        except Exception: pass
    host=getattr(parent,'host',None) or parent
    def _norm(v):
        v=[float(x) for x in v if isinstance(x,(int,float))]
        if not v: return []
        lo,hi=min(v),max(v); return [0.5]*len(v) if hi-lo<1e-12 else [(x-lo)/(hi-lo) for x in v]
    def _source(i):
        try:
            if i==0: return _norm(values or [])
            app=host if hasattr(host,'get_seed_values') else getattr(host,'host',None)
            if app is None: return []
            if i==1: return _norm(app.get_seed_values(0.0) or [])
            name=app.instrument_selector_dropdown.currentText(); mem=app._current_sequence_mem(name)
            if i==2:
                view=app._sequence_display_mem(name,mem); return _norm(view.get('pitches',[]))
            if i==3: return _norm(mem.get('amplitudes',[]))
            return _source(1)+_source(2)+_source(3)
        except Exception: return []
    src.currentIndexChanged.connect(update); depth.valueChanged.connect(update); levels.valueChanged.connect(update)
    mode.currentTextChanged.connect(update); exp.valueChanged.connect(update); resolution.valueChanged.connect(update); [c.valueChanged.connect(update) for c in coeffs]; update(); dlg.show(); return dlg
