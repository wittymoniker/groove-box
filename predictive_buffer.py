"""Low-priority single-process exact canonical look-ahead, independent of playback."""
import os
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context


def _low_priority_worker():
    try:
        os.nice(12)
    except (AttributeError, OSError):
        pass
    try:
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {allowed[-1]})
    except (AttributeError, OSError):
        pass
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(limits=1)
    except ImportError:
        pass


def _predict(identity, payload, kernels):
    from canonical_pool import project
    begin = time.process_time()
    result = project(identity, payload, kernels)
    result["predictive_cpu_seconds"] = time.process_time() - begin
    return result


class PredictiveBuffer:
    def __init__(self):
        from thread_budget import usable_cores
        self.cores = usable_cores()
        self.enabled = os.environ.get("GROOVEBOX_PREDICTIVE_BUFFER", "1") != "0" and self.cores >= 3
        self.pool = self.future = self.identity = None
        self.hits = self.requests = 0
        self.next_admission = 0.0
        self._accounted = None

    def lookup(self, identity):
        if self.future is None or self.identity != identity or not self.future.done():
            return None
        try:
            result = self.future.result()
        except Exception:
            return None
        if result.get("identity") != identity:
            return None
        self.hits += 1
        return result

    def prefetch(self, payload, kernels, *, selected=0.0, activity=0.0):
        if not self.enabled:
            return
        if self.future is not None:
            if not self.future.done():
                return  # No speculative backlog; foreground never waits.
            if self._accounted != self.identity:
                from scheduling_weights import predictive_fraction
                try:
                    seconds = self.future.result().get("predictive_cpu_seconds", 0.0)
                except Exception:
                    seconds = 0.0
                duty = max(0.01, min(1.0, self.cores * predictive_fraction(selected, activity)))
                self.next_admission = time.monotonic() + seconds * (1.0 / duty - 1.0)
                self._accounted = self.identity
        if time.monotonic() < self.next_admission:
            return
        import hashlib
        import pickle
        predicted = dict(payload)
        sources = set(payload["sources"])
        for source in ("seeded", "euclidean", "phase_lock", "randomizer", "fractal_seed"):
            if source not in sources:
                sources.add(source)
                break
        else:
            sources.discard("fractal_seed")
        predicted["sources"] = sorted(sources)
        serialized = pickle.dumps(predicted, protocol=5)
        if len(serialized) > 8 * 1024 * 1024:
            return
        identity = hashlib.sha256(serialized).hexdigest()
        if identity == self.identity:
            return
        try:
            if self.pool is None:
                self.pool = ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn"),
                                                initializer=_low_priority_worker)
            self.identity = identity
            self.future = self.pool.submit(_predict, identity, predicted, kernels)
            self.requests += 1
        except Exception as exc:
            self.enabled = False
            print(f"[Predictive buffer] unavailable: {exc}; foreground pooling remains active")

    def shutdown(self):
        if self.future is not None:
            self.future.cancel()
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
