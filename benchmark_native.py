import ctypes, time, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
LIB = ROOT / 'native' / 'libgroovebox_accel.so'
lib = ctypes.CDLL(str(LIB))
P = ctypes.POINTER
lib.gb_hardclip_f32.argtypes=[P(ctypes.c_float),P(ctypes.c_float),ctypes.c_size_t,ctypes.c_float,P(ctypes.c_float)]
lib.gb_voice_synth_f32.argtypes=[P(ctypes.c_double),ctypes.c_size_t,ctypes.c_double,ctypes.c_double,ctypes.c_double,ctypes.c_double,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_double,ctypes.c_longlong,ctypes.c_int,ctypes.c_double,ctypes.c_double,P(ctypes.c_float)]

def bench_clip(n=9_600_000):
    x=np.linspace(-1.7,1.7,n,dtype=np.float32); out=np.empty_like(x); metrics=np.empty(3,np.float32)
    t=time.perf_counter(); np.clip(x*1.5,-1,1,out=out); tn=time.perf_counter()-t
    t=time.perf_counter(); lib.gb_hardclip_f32(x.ctypes.data_as(P(ctypes.c_float)),out.ctypes.data_as(P(ctypes.c_float)),n,1.5,metrics.ctypes.data_as(P(ctypes.c_float))); tc=time.perf_counter()-t
    print(f'hardclip {n:,}: NumPy {tn:.6f}s | C++ {tc:.6f}s | ratio {tn/tc:.2f}x | maxerr {np.max(np.abs(out-np.clip(x*1.5,-1,1))):.3g}')

def bench_voice(n=960_000):
    phase=np.linspace(0,2*math.pi*64,n,dtype=np.float64); out=np.empty(n,np.float32)
    M=1.1975807343385265; MN=(M-1)/M; e=.63; k1=.71; k3=.4; k4=.9; nh=12; ni=5; seed=12345; vo=7
    t=time.perf_counter();
    harm=np.sin(phase)
    for h in range(2,nh+1):
        roll=1+(1-e)*1.2; amp=(.35+.55*(1-e))/(h**roll); det=1e-4*((seed%97)-48)*(h-1)*(.3+.7*e); ph0=((seed*h*13+vo*7)%1000)/1000*2*math.pi
        harm += amp*np.sin(phase*h*(1+det)+ph0)
    inh=np.zeros_like(phase)
    for h in range(1,ni+1):
        ratio=1+h*(1+.37*math.sin((seed+h*17)*MN)); ratio=1+(ratio-1)*(.4+.6*e); amp=(.25+.6*e)/(h**(.9+.4*e)); ph0=((seed*h*31+vo*11)%1000)/1000*2*math.pi; inh += amp*np.sin(phase*ratio+ph0)
    fr=1+((seed%19)/19)*3*e; fd=(.05+.55*e)*(.5+.5*k1); harm*=np.cos(fd*np.sin(phase*fr)); ref=np.clip((1-e)*harm+e*inh,-1.5,1.5).astype(np.float32)
    tn=time.perf_counter()-t
    t=time.perf_counter(); lib.gb_voice_synth_f32(phase.ctypes.data_as(P(ctypes.c_double)),n,e,k1,k3,k4,nh,ni,0,0,.2,seed,vo,M,MN,out.ctypes.data_as(P(ctypes.c_float))); tc=time.perf_counter()-t
    print(f'voice {n:,}: NumPy {tn:.6f}s | C++ {tc:.6f}s | ratio {tn/tc:.2f}x | maxerr {np.max(np.abs(out-ref)):.3g} | rmse {np.sqrt(np.mean((out-ref)**2)):.3g}')

if __name__=='__main__':
    bench_clip(); bench_voice()
