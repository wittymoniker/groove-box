#!/usr/bin/env python3
from time import perf_counter_ns
from author_number_codec import spell_number, _spell_cached, PRECOMPUTED_VARIANT_COUNT
from scode_optimizer_bridge import require_scode_runtime

values=[f"{(i%97)+((i*37)%1000)/1000:.3f}" for i in range(1000)]
_spell_cached.cache_clear()
t0=perf_counter_ns(); cold=[spell_number(v) for v in values]; t1=perf_counter_ns()
t2=perf_counter_ns(); hot=[spell_number(v) for v in values]; t3=perf_counter_ns()
bridge=require_scode_runtime()
# warm a dedicated sCode-routed semantic packet cache
for v in values:
    bridge.memoized_symbol_spelling(("base16-squiggle-subscale-v4",v), lambda v=v: spell_number(v))
t4=perf_counter_ns()
for _ in range(20):
    for v in values:
        bridge.memoized_symbol_spelling(("base16-squiggle-subscale-v4",v), lambda v=v: spell_number(v))
t5=perf_counter_ns()
print(f"precomputed semantic faces={PRECOMPUTED_VARIANT_COUNT}")
print(f"codec cold 1000={((t1-t0)/1e6):.4f} ms")
print(f"codec cached 1000={((t3-t2)/1e6):.4f} ms")
print(f"codec cache speedup={((t1-t0)/max(1,t3-t2)):.1f}x")
print(f"sCode memo cached per lookup={((t5-t4)/20/1000/1e3):.3f} us")
print("sample 1.20", spell_number("1.20").to_dict())
