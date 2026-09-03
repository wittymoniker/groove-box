module GrooveboxMeumOT
using SHA

export MEUM, MEUM_INV, MEUM_NORM, EQR_FINITE_INFINITY, TAU
export ot_prod, ot_add, ot_sub, ot_div, ot_pow, ot_band
export ot_equiv_add, ot_equiv_sub, ot_equiv_mul, ot_equiv_div, ot_equiv_pow, ot_equiv_root
export eqr_isn, eqr_ics, eqr_isn_inv, book_isn, book_isn_inv, book_ics, book_ics_inv
export eqr_tensor_step, eqr_tensor_audio
export MeumOscillator, render!, meum_field, amplitude_modulation, instantaneous_frequency
export phase_modulation, waveform_sample, audible_hz, identity_unit
export set_operator_theory!, operator_theory_enabled

const MEUM = 1.1975807343385265188
const MEUM_MINUS_1 = MEUM - 1.0
const MEUM_INV = 1.0 / MEUM
const MEUM_NORM = MEUM_MINUS_1 * MEUM_INV
const EQR_FINITE_INFINITY = 134964356.0
const AUDIBLE_HI_HZ = 27500.0
const TAU = 2π
# Canonical engine contract: the oscillator uses OT-equivalent transcendental
# functions, so enabling OT preserves the canonical DSP waveform.  The flag is
# retained here so future Julia hot paths can share the exact engine state.
const OP_THEORY_ENABLED = Ref(true)

set_operator_theory!(enabled::Bool) = (OP_THEORY_ENABLED[] = enabled)
operator_theory_enabled() = OP_THEORY_ENABLED[]

identity_unit(parts...) = reinterpret(UInt64, sha1(join(string.(parts), "|"))[1:8])[1] / 18446744073709551616.0

@inline audible_hz(freq, sample_rate=0.0) = begin
    f = isfinite(Float64(freq)) ? Float64(freq) : 5.2
    hi = sample_rate > 1 ? min(AUDIBLE_HI_HZ, sample_rate*0.75) : AUDIBLE_HI_HZ
    max(5.2, min(hi, f))
end

@inline ot_equiv_add(a,b) = Float64(a)+Float64(b)
@inline ot_equiv_sub(a,b) = Float64(a)-Float64(b)
@inline ot_equiv_mul(a,b) = Float64(a)*Float64(b)
@inline function ot_equiv_div(a,b)
    a=Float64(a); b=Float64(b); b==0.0 ? 0.0 : a/b
end
@inline ot_equiv_pow(b,e) = Float64(b)^Float64(e)
@inline function ot_equiv_root(x,n=2.0)
    x=Float64(x); n=Float64(n)
    n==0.0 && return 0.0
    x<0 && isodd(Int(n)) ? -abs(x)^(1/n) : (x<0 ? NaN : x^(1/n))
end
@inline ot_equiv_i_pow(k) = iseven(Int(k)) ? 1.0 : -1.0

@inline function ot_band(x)
    a=abs(Float64(x)); a<=1 ? 1.0 : a<=2 ? 2.0 : a<=3 ? 3.0 : 1.0
end
@inline function ot_add(n,v)
    n=Float64(n); v=Float64(v)
    n==0 && v==0 && return 1.0
    sign=n<0 ? -1.0 : 1.0
    sign*(ot_band(n)+ot_band(v)-1.0)
end
@inline function ot_sub(n,v)
    n=Float64(n); v=Float64(v)
    n==0 && v==0 && return 1.0
    n - (v<0 ? -ot_band(v) : ot_band(v))
end
@inline function ot_prod(a,b)
    a=Float64(a); b=Float64(b)
    a==0 && b==0 && return 1.0
    (a==0 || b==0) && return 0.0
    mag=abs(a*b); (a<0)==(b<0) ? (a<0 ? -mag : mag) : -mag
end
@inline function ot_pow(b,e)
    b=Float64(b); e=Float64(e); r=abs(b)^abs(e)
    ((b>=0)==(e>=0)) ? r : -r
end
@inline function ot_div(a,b)
    a=Float64(a); b=Float64(b)
    a==0 && b==0 && return 1.0
    ab=abs(b); ab==0 && return copysign(1.0,a)*1e9
    a==0 && return 0.0
    copysign(abs(a)/ab,a)
end
@inline ot_i_phase(x,k) = Float64(x)*(iseven(Int(k)) ? -1.0 : 1.0)

@inline eqr_isn(x) = begin
    x=Float64(x); sin(x)*MEUM_NORM + sin(x*MEUM)*(1-MEUM_NORM)
end
@inline eqr_ics(x) = begin
    x=Float64(x); cos(x)*MEUM_NORM + cos(x*MEUM)*(1-MEUM_NORM)
end
@inline book_isn(x) = 2sin(0.5*Float64(x))
@inline book_isn_inv(y) = 2asin(clamp(0.5*Float64(y),-1.0,1.0))
@inline book_ics(x) = 2cos(0.5*Float64(x))
@inline book_ics_inv(y) = 2acos(clamp(0.5*Float64(y),-1.0,1.0))

function eqr_isn_inv(y; iters=24)
    y=Float64(y); limit=eqr_isn(π/2); y=clamp(y,-limit,limit)
    a=-π/2; b=π/2; fa=eqr_isn(a)-y; x=0.0
    for _ in 1:iters
        x=(a+b)*0.5; fx=eqr_isn(x)-y
        if (fa<0) != (fx<0); b=x else a=x; fa=fx end
    end
    x
end

function eqr_tensor_step(sample, neighbours, t=0.0)
    s=Float64(sample); pts=isempty(neighbours) ? [s] : Float64.(neighbours); k=max(1,length(pts)-1)
    sp=0.0; se=0.0
    for v in pts
        d=abs(v-s)+1e-9
        sp += book_isn_inv((book_isn(d)+book_isn(t))*0.5)
        se += book_isn(v)/d
    end
    P=sp/k; E=se/k; D=0.0
    if abs(P)>1e-12
        acc=0.0
        for v in pts; acc += book_isn_inv(book_isn(v)*E/(EQR_FINITE_INFINITY*P)); end
        D=acc/k
    end
    (P,E,D,P*E+D)
end

function eqr_tensor_audio(sample,d_char,theta_char,t=0.0)
    d=abs(Float64(d_char))+1e-9; th=Float64(theta_char); tt=Float64(t)
    P=book_isn_inv((book_isn(d)+book_isn(tt))*0.5)
    E=book_isn(th)/d; D=0.0
    abs(P)>1e-12 && (D=book_isn_inv(book_isn(th)*E/(EQR_FINITE_INFINITY*P)))
    (P,E,D,P*E+D)
end

mutable struct MeumOscillator
    sample_rate::Float64
    frequency::Float64
    phase::Float64
    sample_index::Int
    phase_shift::Float64
    am_depth::Float64; am_rate::Float64
    fm_depth::Float64; fm_rate::Float64
    pm_depth::Float64; pm_rate::Float64
    pm_feedback::Float64; meum_depth::Float64
    waveform::Symbol
end
MeumOscillator(sr=44100.0,f=440.0)=MeumOscillator(Float64(sr),Float64(f),0.0,0,0.0,0.0,1.0,0.0,1.0,0.0,1.0,0.0,0.0,:isn)
@inline function meum_field(o,t,rate)
    a=sin(TAU*t*rate); b=sin(TAU*t*rate*MEUM_INV); clamp(0.5*(a+MEUM_NORM*b),-1.0,1.0)
end
@inline function amplitude_modulation(o,t)
    l=sin(TAU*t*o.am_rate+o.phase_shift); f=meum_field(o,t,o.am_rate)
    max(0.0,1.0+o.am_depth*(l+o.meum_depth*f))
end
@inline function instantaneous_frequency(o,t)
    l=sin(TAU*t*o.fm_rate+o.phase_shift); f=meum_field(o,t,o.fm_rate)
    clamp(o.frequency*(1.0+o.fm_depth*(l+o.meum_depth*f)),0.0,min(o.sample_rate*0.75,AUDIBLE_HI_HZ))
end
@inline phase_modulation(o,t) = o.pm_depth*sin(TAU*t*o.pm_rate+o.phase_shift)+o.pm_feedback*o.meum_depth*meum_field(o,t,o.pm_rate)
@inline function waveform_sample(o,phase)
    u=mod(phase/TAU,1.0); w=o.waveform
    w in (:saw,:sawtooth) && return 2u-1
    w in (:square,:pulse) && return u<0.5 ? 1.0 : -1.0
    w in (:triangle,:tri) && return 4abs(u-0.5)-1
    w in (:ics,:cos,:cosine) && return eqr_ics(phase)
    w in (:arcisn,:isn_inv,:isn_inverse) && return eqr_isn_inv(eqr_isn(phase))
    w in (:arcics,:ics_inv,:ics_inverse) && return eqr_isn_inv(clamp(eqr_ics(phase), -1.0, 1.0))
    eqr_isn(phase)
end
function render!(o,n; amplitude=1.0, frequency=nothing)
    n<=0 && return Float32[]
    frequency!==nothing && (o.frequency=max(0.0,Float64(frequency)))
    sr=max(1.0,o.sample_rate); out=Vector{Float32}(undef,n); phase=o.phase; idx=o.sample_index
    @inbounds for i in 1:n
        t=idx/sr; phase += TAU*instantaneous_frequency(o,t)/sr
        s=waveform_sample(o,phase+o.phase_shift+phase_modulation(o,t)); g=amplitude_modulation(o,t)
        out[i]=Float32(amplitude*g*s); idx+=1; phase=mod(phase,TAU)
    end
    o.phase=phase; o.sample_index=idx; out
end

end # module
