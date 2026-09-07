import threading
import time
from scode_optimizer_bridge import SCodeOptimizerBridge, SCodeStaleCompletion

b = SCodeOptimizerBridge()
try:
    # PURE cache + inflight coalescing.
    started = threading.Event(); release = threading.Event(); calls = []
    def pure_work():
        calls.append('pure'); started.set(); release.wait(2); return 41
    f1 = b.submit_pooled('symbols', {'x':1}, pure_work, policy='pure', format_id='symbol')
    assert started.wait(1)
    f2 = b.submit_pooled('symbols', {'x':1}, pure_work, policy='pure', format_id='symbol')
    assert f1 is f2
    release.set(); assert f1.result(2) == 41
    f3 = b.submit_pooled('symbols', {'x':1}, lambda: 99, policy='pure', format_id='symbol')
    assert f3.result(1) == 41
    assert calls == ['pure']

    # GENERATION stale rejection.
    gate = threading.Event()
    b._last_plan['canonical_generation'] = 10
    old = b.submit_pooled('canonical', {'v':'old'}, lambda: (gate.wait(2), 'old')[1], policy='generation', format_id='sequence')
    b._last_plan['canonical_generation'] = 11
    new = b.submit_pooled('canonical', {'v':'new'}, lambda: 'new', policy='generation', format_id='sequence')
    gate.set()
    assert new.result(2) == 'new'
    try:
        old.result(2)
        raise AssertionError('stale generation was published')
    except SCodeStaleCompletion:
        pass

    # FRAME latest-only publication.
    gate2 = threading.Event()
    b._last_plan['visual_generation'] = 20
    oldf = b.submit_pooled('visual', {'frame':1}, lambda: (gate2.wait(2), 1)[1], policy='frame', format_id='image', frame=1)
    newf = b.submit_pooled('visual', {'frame':2}, lambda: 2, policy='frame', format_id='image', frame=2)
    gate2.set(); assert newf.result(2) == 2
    try:
        oldf.result(2)
        raise AssertionError('stale frame was published')
    except SCodeStaleCompletion:
        pass

    # STREAM publishes latest-ready monotonically and read path is lock-free.
    b._last_plan['audio_generation'] = 30
    s1 = b.submit_pooled('audio', {'chunk':1}, lambda: 'a', policy='stream', format_id='audio', frame=1)
    assert s1.result(2) == 'a'
    assert b.latest_stream_result('audio') == 'a'
    s2 = b.submit_pooled('audio', {'chunk':2}, lambda: 'b', policy='stream', format_id='audio', frame=2)
    assert s2.result(2) == 'b'
    assert b.latest_stream_result('audio') == 'b'
    assert b.latest_stream_metadata('audio') == {'generation':30,'frame':2}

    # SIDE_EFFECT never coalesces/reuses.
    side = []
    a = b.submit_pooled('project', {'save':'x'}, lambda: side.append(1) or 1, policy='side_effect', format_id='project')
    c = b.submit_pooled('project', {'save':'x'}, lambda: side.append(2) or 2, policy='side_effect', format_id='project')
    assert sorted([a.result(2), c.result(2)]) == [1,2]
    assert sorted(side) == [1,2]

    # Non-Qt callbacks execute on dedicated completion thread.
    seen = []
    ev = threading.Event()
    def cb(result, error):
        seen.append((threading.current_thread().name, result, error)); ev.set()
    b.submit_pooled('media', {'cb':1}, lambda: 7, policy='pure', format_id='object', callback=cb)
    assert ev.wait(2)
    assert seen[0][0] == 'scode-complete' and seen[0][1] == 7 and seen[0][2] is None

    stats = b.state_for_project()['stats']
    assert stats['completion_coalesced'] >= 1
    assert stats['completion_cache_hits'] >= 1
    assert stats['completion_stale_dropped'] >= 2
    assert stats['completion_published'] >= 7
    print('PASS sCode completion bridge ABI9', stats)
finally:
    b.shutdown(wait=True)
