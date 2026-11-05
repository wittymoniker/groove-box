"""Generated static cooperative canonical kernels; regenerate with scripts/build_cooperative_kernels.py."""

def _cooperative__apply_active_engines_meum_composite(self, active_engines):
    """Composite canonical dispatcher used when 'Engines simplified by Meum' is ON.

        Provable equivalence boundary:
        - active engine set is sorted exactly as before;
        - the canonical seed is computed once instead of once per engine;
        - each unchanged engine receives the identical per-engine RNG seed;
        - panel writes/signatures/baseline resets remain in the same order.

        Therefore this is a code-path simplification, not a replacement of the
        SEEDED/RAND/LOCK/EUCLIDEAN/GOAVA canonical engines. Euclidean is a full
        canonical vote because it can reshape both generated and protected user material.
        """
    yield None
    seed = _safe_int_seed(self.get_numeric_seed())
    prepared = self._prepare_active_canonical_engines_threaded(active_engines)
    for engine in sorted(active_engines):
        yield None
        yield from self._cooperative__apply_engine_with_shared_context(engine, seed, prepared=prepared.get(engine))

def _cooperative__apply_engine_with_shared_context(self, engine, seed, prepared=None):
    """Apply one canonical; its pure preparation may arrive from its own lane."""
    yield None
    if prepared is None:
        src_seed = self._canonical_seed_for_source(engine)
        eng_h = int(_safe_int_seed(_stable_hash(str(engine)) & 2147483647))
        rng = np.random.default_rng((_safe_int_seed(src_seed) ^ eng_h) & 2147483647)
    else:
        src_seed, rng = prepared
    self._active_engine_write_source = engine
    try:
        if engine == 'goava':
            yield from self._cooperative__apply_goava_deterministically(seed, rng)
        elif engine == 'randomizer':
            yield from self._cooperative__apply_randomizer_deterministically(src_seed, rng)
        elif engine == 'phase_lock':
            yield from self._cooperative__apply_phase_lock_deterministically(seed, rng)
        elif engine == 'euclidean':
            yield from self._cooperative__apply_euclidean_deterministically(seed, rng)
        elif engine == 'seeded':
            yield from self._cooperative__apply_seeded_deterministically(seed, rng)
        elif engine == 'fractal_seed':
            pass
        try:
            if hasattr(self, '_engine_write_sequence_panels'):
                yield from self._cooperative__engine_write_sequence_panels(source=str(engine))
        except Exception as _pe:
            print(f'[Unison] sequence panels ({engine}): {_pe}')
        self._live_offset_baselines = {}
        self._live_param_baselines = {}
        self._store_engine_signature(engine, int(_safe_int_seed(src_seed)))
    finally:
        self._active_engine_write_source = None

def _cooperative__apply_euclidean_deterministically(self, seed, rng):
    """EUCLIDEAN canonical: deterministic rhythm/structure reshaping at its saved level."""
    yield None
    level = self._canonical_level('euclidean')
    if level <= 0.0:
        return
    yield from self._cooperative_apply_euclidean_and_idealized_rhythms()

def _cooperative__apply_goava_deterministically(self, seed, rng):
    """Deterministic GOAVA application"""
    yield None
    self.goava_note_events = self._build_goava_composition()
    self._apply_goava_to_canonical_playlist()

def _cooperative__apply_live_engine_once(self, which, force=False):
    yield None
    if getattr(self, '_live_engine_update_guard', False):
        return
    if not force and getattr(self, '_composition_generation_guard', False):
        return
    sig = self._live_engine_signature(which) if hasattr(self, '_live_engine_signature') else None
    if not force and sig is not None and (getattr(self, '_live_engine_signatures', {}).get(which) == sig):
        return
    snap = self._snapshot_global_effect_sliders()
    self._live_engine_update_guard = True
    self._composition_generation_guard = True
    try:
        self._active_engine_write_source = str(which)
        if which == 'euclidean':
            yield from self._cooperative_apply_euclidean_and_idealized_rhythms()
        else:
            yield from self._cooperative_apply_seeded_harmonic_randomization()
    except Exception as exc:
        print(f'[LiveEngine:{which}] {type(exc).__name__}: {exc}')
    finally:
        self._active_engine_write_source = None
        self._live_engine_update_guard = False
        self._composition_generation_guard = False
        self._restore_global_effect_sliders(snap)
        if sig is not None:
            if not hasattr(self, '_live_engine_signatures'):
                self._live_engine_signatures = {}
            self._live_engine_signatures[which] = self._live_engine_signature(which) if hasattr(self, '_live_engine_signature') else sig

def _cooperative__apply_phase_lock_deterministically(self, seed, rng):
    """LOCK with user-adjustable relationship/timing/velocity characteristics."""
    yield None
    level = self._canonical_level('phase_lock')
    if level <= 0.0:
        return
    chars = self._lock_characteristics()
    if hasattr(self, 'wavefield_engine') and self.wavefield_engine:
        self.wavefield_engine.apply_phase_locked_randomization()
    else:
        yield from self._cooperative_apply_euclidean_and_idealized_rhythms()
    if hasattr(self, '_canonical_playlist_paint'):
        yield from self._cooperative__canonical_playlist_paint(rng=rng, mode='phase_lock', strength=0.55 * level * chars['coupling'])
    try:
        self._phase_lock_playlist_velocity(rng=rng, strength=chars['velocity_link'] * level, randomize=True)
    except Exception:
        pass

def _cooperative__apply_randomizer_deterministically(self, seed, rng):
    """Replayable RAND generated from the captured OS-entropy token."""
    yield None
    level = self._canonical_level('randomizer')
    if level <= 0.0:
        return
    try:
        self._mark_generated_synth_context(source='randomizer', rng=rng)
    except Exception:
        pass
    try:
        self._engines_write_automation_lanes(source='randomizer')
    except Exception:
        pass
    if hasattr(self, '_canonical_playlist_paint'):
        yield from self._cooperative__canonical_playlist_paint(rng=rng, mode='randomizer', strength=0.55 * level)

def _cooperative__apply_seeded_deterministically(self, seed, rng):
    """Deterministic seeded application"""
    yield None
    if hasattr(self, '_apply_live_engine_once'):
        yield from self._cooperative__apply_live_engine_once('seeded', force=True)

def _cooperative__canonical_playlist_paint(self, rng, mode='randomize', strength=0.55):
    yield None
    if getattr(self, '_composition_generation_guard', False):
        pass
    _eng_rhythm_own = self._heuristic_owns('engine_rhythm') if hasattr(self, '_heuristic_owns') else None
    _eng_melody_own = self._heuristic_owns('engine_melody') if hasattr(self, '_heuristic_owns') else None
    _pl_rhythm_own = self._heuristic_owns('playlist_rhythm') if hasattr(self, '_heuristic_owns') else None
    _pl_melody_own = self._heuristic_owns('playlist_melody') if hasattr(self, '_heuristic_owns') else None
    _prev_skip_er = getattr(self, '_canonical_skip_engine_rhythm', False)
    _prev_skip_em = getattr(self, '_canonical_skip_engine_melody', False)
    _prev_skip_pr = getattr(self, '_canonical_skip_playlist_rhythm', False)
    _prev_skip_pm = getattr(self, '_canonical_skip_playlist_melody', False)
    self._canonical_skip_engine_rhythm = isinstance(_eng_rhythm_own, dict) and float(_eng_rhythm_own.get('strength', 0)) >= 1.0
    self._canonical_skip_engine_melody = isinstance(_eng_melody_own, dict) and float(_eng_melody_own.get('strength', 0)) >= 1.0
    self._canonical_skip_playlist_rhythm = isinstance(_pl_rhythm_own, dict) and float(_pl_rhythm_own.get('strength', 0)) >= 1.0
    self._canonical_skip_playlist_melody = isinstance(_pl_melody_own, dict) and float(_pl_melody_own.get('strength', 0)) >= 1.0
    table = getattr(self, 'paintbrush_table', None)
    if table is None:
        table = getattr(self, 'playlist_paint_table', None)
    if table is None:
        for name in ('paint_table', 'paintbrush', 'playlist_paintbrush', 'playlist_paint_surface'):
            yield None
            candidate = getattr(self, name, None)
            if candidate is not None and hasattr(candidate, 'engage_paint'):
                table = candidate
                break
    if table is None or not hasattr(table, 'rowCount'):
        if hasattr(self, '_paint_operator_pattern_to_playlist'):
            yield from self._cooperative__paint_operator_pattern_to_playlist(source=mode, rng=rng)
        if hasattr(self, '_paint_generated_parameters'):
            self._paint_generated_parameters(rng=rng, source=mode)
        if hasattr(self, '_run_composition_context_engine'):
            self._run_composition_context_engine(source=mode, rng=rng)
        if getattr(self, 'goava_active', False):
            self._apply_goava_to_canonical_playlist()
        return
    rows = table.rowCount()
    cols = min(table.columnCount(), PLAYLIST_COLUMN_COUNT)
    if self._canonical_protect_user() and hasattr(self, '_canonical_prune_stale_playlist_touches'):
        self._canonical_prune_stale_playlist_touches()
    old_expanding = getattr(table, '_paint_expanding', False)
    table._paint_expanding = True
    try:
        if mode in _EXPLICIT_ENGINE_SOURCES:
            if hasattr(self, '_mark_generated_synth_context'):
                self._mark_generated_synth_context(source=mode, rng=rng)
            if hasattr(self, '_write_generated_domain_context'):
                self._write_generated_domain_context(source=mode)
            if hasattr(self, '_write_generated_patch_context'):
                self._write_generated_patch_context(source=mode)
            if hasattr(self, '_engine_write_sequence_panels'):
                try:
                    n_panels = (yield from self._cooperative__engine_write_sequence_panels(source=mode))
                    if n_panels:
                        print(f'[{mode}] wrote sequence panels for {n_panels} instrument(s)')
                except Exception as _pe:
                    print(f'[{mode}] sequence panel write skipped: {_pe}')
        if hasattr(self, '_paint_operator_pattern_to_playlist'):
            yield from self._cooperative__paint_operator_pattern_to_playlist(source=mode, rng=rng)
        elif hasattr(self, '_run_composition_context_engine'):
            self._run_composition_context_engine(source=mode, rng=rng)
        else:
            for row in range(rows):
                yield None
                for col in range(cols):
                    yield None
                    try:
                        table.engage_paint(row, col)
                    except Exception as exc:
                        print(f'[CanonicalPaint] row={row} col={col}: {type(exc).__name__}: {exc}')
        if hasattr(self, '_paint_generated_parameters'):
            self._paint_generated_parameters(rng=rng, source=mode)
        if hasattr(self, '_phase_lock_playlist_velocity'):
            self._phase_lock_playlist_velocity(rng=rng, strength=0.35 if mode == 'randomize' else 0.45, randomize=mode == 'randomize')
        if hasattr(self, '_sync_playlist_paint_table_from_memory'):
            self._sync_playlist_paint_table_from_memory()
        if getattr(self, 'goava_active', False):
            self._apply_goava_to_canonical_playlist()
    finally:
        table._paint_expanding = old_expanding
        if hasattr(self, '_register_heuristic_ownership'):
            if not self._canonical_skip_playlist_rhythm:
                self._register_heuristic_ownership('playlist_rhythm', source='canonical', strength=0.55)
            if not self._canonical_skip_playlist_melody:
                self._register_heuristic_ownership('playlist_melody', source='canonical', strength=0.55)
        self._canonical_skip_engine_rhythm = _prev_skip_er
        self._canonical_skip_engine_melody = _prev_skip_em
        self._canonical_skip_playlist_rhythm = _prev_skip_pr
        self._canonical_skip_playlist_melody = _prev_skip_pm
        try:
            _own_str = self._heuristic_ownership_status()
            if _own_str and hasattr(self, 'scope_status_label'):
                self.scope_status_label.setText(f'🎵 Heuristic ownership: {_own_str}')
        except Exception:
            pass

def _cooperative__canonical_sequence_reconcile(self, trigger_source=None):
    """Reconcile canonical sequences deterministically, preserving resize identity.

        Normal canonical transactions regenerate canonical material from the active set.
        An ensemble resize is different: surviving instruments must retain the exact
        canonical sequence objects they were already playing, while only newly-created
        instruments receive newly generated canonical sequences.  This prevents the
        post-resize sound from changing until the user retoggles the engines.
        """
    yield None
    banks = getattr(self, 'instrument_sequence_banks', {}) or {}
    names = list(getattr(self, 'instrument_names_48', []) or [])
    active = set(self._active_engine_sources()) if hasattr(self, '_active_engine_sources') else set()
    active.discard('goava')
    canonical_order = ['goava', 'phase_lock', 'euclidean', 'randomizer', 'seeded', 'fractal_seed']
    active_order = [x for x in canonical_order if x in active]
    if not names:
        return
    prepared = getattr(self, '_canonical_prepared_sequence_plan', None)
    if not getattr(self, '_canonical_model_only', False) and prepared is not None and getattr(self, '_unison_composition_guard', False) and (not getattr(self, '_canonical_resize_preserve_sequences', False)) and (set(prepared['sources']) == set(active_order)) and (prepared['names'] == names):
        for name in names:
            yield None
            bank = banks.setdefault(name, {})
            for sid in list(bank):
                yield None
                if str((bank[sid] or {}).get('canonical_owner', '')).startswith('canonical:'):
                    del bank[sid]
            for sid, mem in prepared['banks'].get(name, {}).items():
                yield None
                if sid in bank:
                    raise RuntimeError('canonical projection would overwrite a user-owned sequence')
                bank[sid] = copy.deepcopy(mem)
            if not bank:
                continue
            selected = self.instrument_selected_sequence.get(name, min(bank))
            if selected not in bank:
                selected = min(bank)
            self.instrument_selected_sequence[name] = selected
            self.instrument_sequencer_memory[name] = bank[selected]
            param = self.instrument_param_state.setdefault(name, {})
            planned = prepared['params'].get(name, {})
            if not param.get('harmonic_freq_user_locked') and 'harmonic_freq' in planned:
                param['harmonic_freq'] = planned['harmonic_freq']
                param.setdefault('tuning_ratio', 1.0)
                getattr(self, 'instrument_param_generated', {}).setdefault(name, {})['harmonic_freq'] = planned['harmonic_freq']
        yield from self._cooperative__finish_canonical_sequence_projection(active_order)
        return
    seed = _safe_int_seed(self.get_numeric_seed())
    fractal_plan = self._fractal_seed_event_plan() if 'fractal_seed' in active_order else None
    for name in names:
        yield None
        bank = banks.setdefault(name, {})
        if not bank:
            bank[1] = copy.deepcopy(self.instrument_sequencer_memory.get(name, {}) or {'pattern_length': DEFAULT_SEQUENCE_LENGTH, 'steps': [False] * DEFAULT_SEQUENCE_LENGTH, 'gates': [True] * DEFAULT_SEQUENCE_LENGTH, 'amplitudes': [1.0] * DEFAULT_SEQUENCE_LENGTH, 'pitches': [1.0] * DEFAULT_SEQUENCE_LENGTH, 'probabilities': [100] * DEFAULT_SEQUENCE_LENGTH, 'offsets': [0.0] * DEFAULT_SEQUENCE_LENGTH, 'sequence_envelope_attack': 0.5, 'sequence_envelope_release': 0.5})
        user_ids = sorted((int(k) for k, v in bank.items() if str(k).isdigit() and isinstance(v, dict) and (not str(v.get('canonical_owner', '')).startswith('canonical:'))))
        if not user_ids:
            user_ids = [1]
            bank.setdefault(1, {'sequence_id': 1, 'pattern_length': DEFAULT_SEQUENCE_LENGTH, 'steps': [False] * DEFAULT_SEQUENCE_LENGTH, 'gates': [True] * DEFAULT_SEQUENCE_LENGTH, 'amplitudes': [1.0] * DEFAULT_SEQUENCE_LENGTH, 'pitches': [1.0] * DEFAULT_SEQUENCE_LENGTH, 'probabilities': [100] * DEFAULT_SEQUENCE_LENGTH, 'offsets': [0.0] * DEFAULT_SEQUENCE_LENGTH, 'user_owned': True})
        preserve_resize = bool(getattr(self, '_canonical_resize_preserve_sequences', False))
        existing_canonical = {}
        for idx, mem0 in bank.items():
            yield None
            if not isinstance(mem0, dict):
                continue
            owner = str(mem0.get('canonical_owner', ''))
            if owner.startswith('canonical:'):
                existing_canonical[owner] = (int(idx), mem0)
        if not preserve_resize:
            for idx in list(bank.keys()):
                yield None
                mem0 = bank.get(idx)
                if isinstance(mem0, dict) and str(mem0.get('canonical_owner', '')).startswith('canonical:'):
                    bank.pop(idx, None)
            existing_canonical = {}
        base_max = max(user_ids)
        for rank, source in enumerate(active_order, start=1):
            yield None
            owner = f'canonical:{source}'
            if preserve_resize and owner in existing_canonical:
                idx, prior_mem = existing_canonical[owner]
                bank[idx] = copy.deepcopy(prior_mem)
                continue
            idx = base_max + rank
            while idx in bank:
                yield None
                idx += 1
            channel = sum((ord(c) for c in source)) & 65535
            try:
                name_idx = list(names).index(name)
            except Exception:
                name_idx = 0
            inst_seed_i = self._instrument_seed_int(name_idx, name=name, sequence_id=idx) if hasattr(self, '_instrument_seed_int') else (seed ^ channel ^ int(idx)) & 2147483647
            try:
                inst_seed_f = float(self._instrument_seed_float(name_idx, sequence_id=idx))
            except Exception:
                inst_seed_f = float(inst_seed_i)
            base_len = int(bank.get(user_ids[0], {}).get('pattern_length', DEFAULT_SEQUENCE_LENGTH) or DEFAULT_SEQUENCE_LENGTH)
            if source == 'euclidean':
                stride = max(2, int(2 + inst_seed_i % 5))
                reps = max(1, 2 + inst_seed_i // 5 % 6)
                n = stride * reps
            elif source == 'goava':
                try:
                    n_vals = max(1, len(list(self.get_seed_values(t_value=0.0) or [])))
                except Exception:
                    n_vals = 1
                n = int(math.ceil(max(base_len, n_vals) / n_vals) * n_vals)
            elif source in ('phase_lock', 'fractal_seed'):
                n = base_len
            else:
                jitter = int(round(4 * series_sin(inst_seed_i * MEUM_INV)))
                n = base_len + jitter
            n = max(1, min(1024, n))
            mem = {'sequence_id': idx, 'pattern_length': n, 'canonical_owner': f'canonical:{source}', 'user_owned': False, 'steps': [False] * n, 'gates': [True] * n, 'amplitudes': [1.0] * n, 'pitches': [1.0] * n, 'probabilities': [100] * n, 'offsets': [0.0] * n, 'engine_step_sources': {}, 'touched': set()}
            rng = np.random.default_rng((inst_seed_i ^ channel) & 2147483647)
            phase_on = 'phase_lock' in active
            fractal_raster = None
            if source == 'fractal_seed' and isinstance(fractal_plan, dict):
                try:
                    from groovebox_v3.fractal_seed_engine import rasterize_sequence
                    _fr_hash = str(fractal_plan.get('event_plan_sha256', '') or '')
                    _fr_key = (_fr_hash, int((fractal_plan.get('interpretation') or {}).get('window_steps', 0) or 0), str((fractal_plan.get('seed') or {}).get('identity', '')), int(n)) if _fr_hash else None
                    _fr_cache = self.__dict__.setdefault('_fractal_raster_cache', {})
                    fractal_raster = _fr_cache.get(_fr_key) if _fr_key is not None else None
                    if fractal_raster is None:
                        fractal_raster = rasterize_sequence(fractal_plan, n)
                        if _fr_key is not None:
                            if len(_fr_cache) >= 64:
                                _fr_cache.clear()
                            _fr_cache[_fr_key] = fractal_raster
                except Exception as _fractal_exc:
                    print(f'[Fractal Seed] sequence projection failed for {name}: {_fractal_exc}')
            for j in range(n):
                yield None
                if source == 'fractal_seed':
                    if not isinstance(fractal_raster, dict):
                        continue
                    if not fractal_raster['steps'][j]:
                        continue
                    mem['steps'][j] = True
                    mem['pitches'][j] = float(fractal_raster['pitches'][j])
                    mem['amplitudes'][j] = float(fractal_raster['amplitudes'][j])
                    mem['gates'][j] = bool(fractal_raster['gates'][j])
                    mem['probabilities'][j] = 100
                    mem['offsets'][j] = float(fractal_raster['offsets'][j])
                    mem['engine_step_sources'][int(j)] = {'canonical:fractal_seed'}
                    continue
                if source == 'goava':
                    mem['steps'][j] = True
                elif source == 'euclidean':
                    pulses = max(2, n // 4)
                    stride = max(2, int(2 + inst_seed_i % 5))
                    mem['steps'][j] = bool((j * stride + inst_seed_i) % n < pulses)
                elif source == 'phase_lock':
                    mem['steps'][j] = bool((j * 3 + inst_seed_i) % 5 < 3)
                else:
                    threshold = 0.34 + 0.18 * series_sin((j + 1) * MEUM_INV + inst_seed_i * 0.0001)
                    mem['steps'][j] = bool(rng.random() > threshold)
                lattice = _seed_to_pitch_ratio(inst_seed_f, name_idx, j)
                if source == 'phase_lock':
                    mem['pitches'][j] = float(np.clip(lattice, 1.0 / 32.0, 32.0))
                elif phase_on and source in ('seeded', 'randomizer', 'euclidean'):
                    jitter = 0.06 * series_sin((j + 1) * MEUM + inst_seed_i * 0.01)
                    mem['pitches'][j] = float(np.clip(lattice * (1.0 + jitter), 1.0 / 32.0, 32.0))
                elif source == 'goava':
                    mem['pitches'][j] = float(np.clip(lattice, 1.0 / 32.0, 32.0))
                else:
                    mem['pitches'][j] = float(np.clip(lattice * (0.85 + 0.3 * float(rng.random())), 1.0 / 32.0, 32.0))
                _ph = (j + 1) * MEUM + inst_seed_i * 0.001317
                _ph2 = (j + 1) * MEUM_INV + inst_seed_i * 1.713e-05
                mem['amplitudes'][j] = float(0.5 + 0.5 * series_sin(_ph) * series_cos(_ph2 * 0.37))
                mem['amplitudes'][j] = float(abs(mem['amplitudes'][j]))
                if mem['amplitudes'][j] < 0.0:
                    mem['amplitudes'][j] = 0.0
                if mem['amplitudes'][j] > 1.0:
                    mem['amplitudes'][j] = 1.0
                mem['offsets'][j] = float(0.5 * series_sin(_ph2) * series_cos(_ph * MEUM_NORM))
                mem['engine_step_sources'][int(j)] = {f'canonical:{source}'}
            try:
                self._write_contour_lanes(mem, self._raw_contour(n, inst_seed_i), f'canonical:{source}', name, idx)
            except Exception as _contour_exc:
                print(f'[Canonical contour] {name}/{source}: {_contour_exc}')
            if source == 'fractal_seed' and isinstance(fractal_raster, dict) and isinstance(fractal_plan, dict):
                mem['fractal_seed_provenance'] = {'schema_version': fractal_plan.get('schema_version'), 'algorithm_version': fractal_plan.get('algorithm_version'), 'seed_identity': fractal_raster.get('seed_identity'), 'event_plan_sha256': fractal_raster.get('event_plan_sha256'), 'depth_requested': (fractal_plan.get('seed') or {}).get('depth_requested'), 'depth_completed': (fractal_plan.get('seed') or {}).get('depth_completed'), 'symbol_budget': (fractal_plan.get('evaluation') or {}).get('symbol_budget'), 'symbols_evaluated': (fractal_plan.get('evaluation') or {}).get('symbols_evaluated'), 'complete_for_requested_depth': (fractal_plan.get('evaluation') or {}).get('complete_for_requested_depth'), 'sequence_length': n, 'window_steps': fractal_raster.get('window_steps'), 'step_lineage': copy.deepcopy(fractal_raster.get('step_lineage', {}))}
            bank[idx] = mem
            try:
                if not hasattr(self, 'instrument_param_state') or self.instrument_param_state is None:
                    self.instrument_param_state = {}
                pst = self.instrument_param_state.setdefault(name, {})
                base_hz = float(self.spin_base_frequency.value()) if hasattr(self, 'spin_base_frequency') else 432.0
                if not pst.get('harmonic_freq_user_locked'):
                    pst['harmonic_freq'] = float(_seed_to_fundamental_hz(inst_seed_f, base_hz, name_idx, 0))
                    pst.setdefault('tuning_ratio', 1.0)
                    gen = getattr(self, 'instrument_param_generated', None)
                    if isinstance(gen, dict):
                        gen.setdefault(name, {})['harmonic_freq'] = pst['harmonic_freq']
            except Exception:
                pass
        selected_map = getattr(self, 'instrument_selected_sequence', {})
        selected = int(selected_map.get(name, user_ids[0]))
        if selected not in bank or (isinstance(bank.get(selected), dict) and str(bank[selected].get('canonical_owner', '')).startswith('canonical:')):
            selected = user_ids[0]
        selected_map[name] = selected
        self.instrument_selected_sequence[name] = selected
        self.instrument_sequencer_memory[name] = bank[selected]
    yield from self._cooperative__finish_canonical_sequence_projection(active_order)

def _cooperative__engine_resize_untouched_sequences(self):
    """Canonical engines may resize any sequence the user has not touched."""
    yield None
    banks = getattr(self, 'instrument_sequence_banks', {}) or {}
    names = list(getattr(self, 'instrument_names_48', []) or [])
    for name in names:
        yield None
        bank = banks.get(name) or {}
        if not isinstance(bank, dict):
            continue
        canon_ns = [max(1, int(m.get('pattern_length', DEFAULT_SEQUENCE_LENGTH) or DEFAULT_SEQUENCE_LENGTH)) for m in bank.values() if isinstance(m, dict) and str(m.get('canonical_owner', '')).startswith('canonical:')]
        if not canon_ns:
            continue
        adopt = int(canon_ns[0])
        for _sid, mem in list(bank.items()):
            yield None
            if not isinstance(mem, dict) or self._sequence_is_user_locked(mem):
                continue
            owner = str(mem.get('canonical_owner', ''))
            n = int(mem.get('pattern_length', adopt) or adopt) if owner.startswith('canonical:') else adopt
            n = max(1, min(1024, n))
            mem['pattern_length'] = n
            self._ensure_seq_mem_length(mem, n)
        sel = (getattr(self, 'instrument_selected_sequence', {}) or {}).get(name)
        if sel in bank:
            self.instrument_sequencer_memory[name] = bank[sel]
    try:
        mem = self._current_sequence_mem()
        if mem and (not self._sequence_is_user_locked(mem)) and hasattr(self, 'spin_seq_length'):
            n = max(1, int(mem.get('pattern_length', DEFAULT_SEQUENCE_LENGTH) or DEFAULT_SEQUENCE_LENGTH))
            if int(self.spin_seq_length.value()) != n:
                self.spin_seq_length.blockSignals(True)
                self.spin_seq_length.setValue(n)
                self.spin_seq_length.blockSignals(False)
                if hasattr(self, 'spin_pattern_length'):
                    self.spin_pattern_length.blockSignals(True)
                    self.spin_pattern_length.setValue(n)
                    self.spin_pattern_length.blockSignals(False)
                self.rebuild_sequencer_steps(n)
    except Exception:
        pass

def _cooperative__engine_write_sequence_panels(self, source='randomizer', instrument_names=None):
    """Write engine panel addons per sequence; they mix into master at render."""
    yield None
    names = list(instrument_names or getattr(self, 'instrument_names_48', []) or [])
    written = 0
    for name in names:
        yield None
        bank = (getattr(self, 'instrument_sequence_banks', {}) or {}).setdefault(name, {})
        ids = sorted((int(k) for k in bank if str(k).isdigit())) or [1]
        for sid in ids:
            yield None
            mem = bank.setdefault(sid, {})
            locked = self._sequence_is_user_locked(mem) if hasattr(self, '_sequence_is_user_locked') else bool(mem.get('user_owned'))
            panels = self._sequence_panel_slot(name, sid)
            panels.setdefault('blend', 0.5)
            ec = panels.setdefault('engine_contributions', {})
            if not isinstance(ec, dict):
                ec = panels['engine_contributions'] = {}
            state = getattr(self, 'instrument_param_state', {}) or {}
            raw_params = state.get(name, {}) if isinstance(state, dict) else {}
            params = dict(raw_params) if isinstance(raw_params, dict) else {}
            generated = getattr(self, 'instrument_param_generated', {}) or {}
            raw_gen = generated.get(name, {}) if isinstance(generated, dict) else {}
            if isinstance(raw_gen, dict):
                for k, v in raw_gen.items():
                    yield None
                    params.setdefault(k, v)
            gen = dict((getattr(self, 'instrument_param_generated', {}) or {}).get(name, {}) or {})
            for k, v in gen.items():
                yield None
                params.setdefault(k, v)
            engine = getattr(self, 'domain_eq_engine', None)
            domains = [copy.deepcopy(d) for d in engine.domains or [] if isinstance(d, dict) and (name[:6].lower() in str(d.get('name', '')).lower() or str(d.get('source', '')) == source)][:4] if engine is not None else []
            patch = [copy.deepcopy(c) for c in getattr(self, 'patch_connections', []) or [] if isinstance(c, dict) and (c.get('source') == name or c.get('target') == name)][:6]
            ec[str(source)] = {'synth': copy.deepcopy(params), 'script': str((getattr(self, 'instrument_scripts', {}) or {}).get(name, '') or ''), 'domain': {'domains': domains, 'source': str(source)}, 'patch': patch}
            merged_synth = {}
            merged_script = ''
            merged_domains = []
            merged_patch = []
            sources = []
            for src in sorted(ec):
                yield None
                cp = ec[src] or {}
                if cp.get('synth'):
                    merged_synth.update(copy.deepcopy(cp['synth']))
                if cp.get('script') and (not merged_script):
                    merged_script = str(cp['script'])
                dom = cp.get('domain') or {}
                for d in dom.get('domains', []) if isinstance(dom, dict) else []:
                    yield None
                    if d not in merged_domains:
                        merged_domains.append(copy.deepcopy(d))
                for edge in cp.get('patch', []) or []:
                    yield None
                    if edge not in merged_patch:
                        merged_patch.append(copy.deepcopy(edge))
                sources.append(src)
            master_live = {}
            try:
                master_live = copy.deepcopy((getattr(self, 'instrument_param_state', {}) or {}).get(name, {}) or {})
            except Exception:
                master_live = {}
            if not isinstance(master_live, dict):
                master_live = {}
            try:
                gen = (getattr(self, 'instrument_param_generated', {}) or {}).get(name, {}) or {}
                if isinstance(gen, dict):
                    for _k, _v in gen.items():
                        yield None
                        master_live.setdefault(_k, _v)
            except Exception:
                pass
            if locked and panels.get('synth'):
                base = self._blend_param_dicts(panels.get('synth') or {}, master_live, 0.25) if hasattr(self, '_blend_param_dicts') else dict(panels.get('synth') or {})
                merged_synth = self._blend_param_dicts(base, merged_synth, 0.35) if hasattr(self, '_blend_param_dicts') else {**base, **merged_synth}
            elif master_live and hasattr(self, '_blend_param_dicts'):
                merged_synth = self._blend_param_dicts(master_live, merged_synth, 0.55)
            elif master_live:
                merged_synth = {**master_live, **merged_synth}
            if not merged_script:
                merged_script = str((getattr(self, 'instrument_scripts', {}) or {}).get(name, '') or '')
            if not merged_domains and master_live:
                pass
            if not merged_patch:
                try:
                    merged_patch = [copy.deepcopy(c) for c in getattr(self, 'patch_connections', []) or [] if isinstance(c, dict) and (c.get('source') == name or c.get('target') == name)][:6]
                except Exception:
                    pass
            panels.update({'synth': merged_synth, 'script': merged_script if not (locked and panels.get('script')) else panels.get('script'), 'domain': {'domains': merged_domains[:8], 'sources': sources}, 'patch': merged_patch[:12], 'engine_source': '+'.join(sources), 'blend': float(panels.get('blend', 0.5) or 0.5), 'master_blended': True})
            written += 1
    return written

def _cooperative__ensure_perfect_unison(self):
    """
        Perfect unison system: All active engines contribute deterministically.
        Re/write is consistent regardless of activation order or history.

        UNISON DATA-FLOW CONTRACT (modern version):
        • The active engine mask is exactly the live toggle buttons (GOAVA,
          randomizer, phase-lock, euclidean live-lock, seeded live-randomizer,
          and deterministic Fractal Seed).
        • Mask + seed + BPM + base frequency + playlist + per-sequence panels +
          global-algo make up the canonical identity. The document written by
          `_project_snapshot` (save/export) is the SAME map this engine reads,
          and `_apply_project_snapshot` (load) restores every one of those
          inputs, so a loaded project re-derives the identical composition.
        • The three master effects (Fractallizer, EQR, PKP) are STRICTLY
          excluded here — they apply on the final master bus in
          `_render_mixdown_buffer`, after this engine commits, so effect
          sliders can never factor into canonical identity.
        • Step 5 re-refreshes the fingerprint so the HUD label always shows
          the state the export/video-game classifiers will read.
        """
    yield None
    if getattr(self, '_unison_composition_guard', False):
        return
    _opt = getattr(self, '_scode_optimizer', None)
    try:
        _banks_now = getattr(self, 'instrument_sequence_banks', {}) or {}
        _have_canon = any((isinstance(m, dict) and str(m.get('canonical_owner', '')).startswith('canonical:') for b in _banks_now.values() for m in (b or {}).values()))
        _stale_claim = bool(self._active_engine_sources()) and (not _have_canon)
    except Exception:
        _stale_claim = False
    if _opt is not None and _stale_claim:
        try:
            _opt.invalidate_work('canonical')
        except Exception:
            pass
    if _opt is not None and (not bool(getattr(self, '_scode_force_canonical', False))):
        _plan = _opt.request_host_plan(self)
        if not _stale_claim and (not bool(_plan.get('run_canonical', 1))):
            return
        if not _opt.claim_host_work(self, 'canonical', force=_stale_claim):
            return
    active_engines = self._get_active_engine_set()
    _prev_active = frozenset(getattr(self, '_canonical_last_active_set', frozenset()) or ())
    if not active_engines:
        self._reset_to_clean_baseline()
        self._clear_canonical_global_algo_projection()
        self._canonical_last_active_set = frozenset()
        self._canonical_user_rows_snapshot = copy.deepcopy(getattr(self, '_render_playlist_snapshot', None) or getattr(self, 'master_playlist_data', []) or [])
        self._canonical_pattern_user_store = copy.deepcopy(getattr(self, 'instrument_sequencer_memory', {}) or {})
        self._canonical_panels_user_store = copy.deepcopy(getattr(self, 'instrument_sequence_banks', {}) or {})
        self._canonical_macro_user_store = copy.deepcopy(getattr(self, 'instrument_param_state', {}) or {})
        return
    if not _prev_active:
        self._canonical_user_rows_snapshot = copy.deepcopy(getattr(self, '_render_playlist_snapshot', None) or getattr(self, 'master_playlist_data', []) or [])
        self._canonical_pattern_user_store = copy.deepcopy(getattr(self, 'instrument_sequencer_memory', {}) or {})
        self._canonical_panels_user_store = copy.deepcopy(getattr(self, 'instrument_sequence_banks', {}) or {})
        self._canonical_macro_user_store = copy.deepcopy(getattr(self, 'instrument_param_state', {}) or {})
    if getattr(self, '_unison_composition_guard', False):
        return
    self._unison_composition_guard = True
    try:
        self._clear_canonical_global_algo_projection()
        self._reset_canonical_engine_derived_state()
        yield from self._cooperative__establish_clean_baseline()
        if self._meum_engine_simplification_enabled():
            yield from self._cooperative__apply_active_engines_meum_composite(active_engines)
        else:
            for engine in sorted(active_engines):
                yield None
                self._apply_engine_deterministically(engine)
        yield from self._cooperative__final_unison_reconciliation()
        self._canonical_superwrite_global_algo()
        QTimer.singleShot(0, self._refresh_canonical_explain)
        try:
            _ugas = getattr(self, 'global_algo_state', {}) or {}
            if bool(_ugas.get('apply_enabled', False)):
                for _kind in ('script', 'domain', 'wire'):
                    yield None
                    if _ugas.get(_kind):
                        self._apply_global_algo_to_ensemble(_kind)
            if getattr(self, 'local_algo_bays', None):
                self._apply_local_bays()
        except Exception as _ua_exc:
            print(f'[Canonical] user algo overlay re-assert: {_ua_exc}')
        self._sync_ui_to_unison_state()
        self._refresh_canonical_derived_columns()
        try:
            self._refresh_canonical_fingerprint()
        except Exception:
            pass
        self._canonical_last_active_set = frozenset(active_engines)
    finally:
        self._unison_composition_guard = False
        self._canonical_prepared_sequence_plan = None

def _cooperative__establish_clean_baseline(self):
    """Create history-free baseline for perfect unison"""
    yield None
    self._deactivate_all_engine_content()
    self._composition_generation_counter = 0
    self._live_offset_baselines = {}
    self._live_param_baselines = {}
    if hasattr(self, '_unison_engine_signatures'):
        self._unison_engine_signatures.clear()
    self._baseline_user_state = self._capture_user_state()

def _cooperative__final_unison_reconciliation(self):
    """Final reconciliation for perfect unison"""
    yield None
    if hasattr(self, '_rebuild_active_canonical_playlist'):
        yield from self._cooperative__rebuild_active_canonical_playlist('perfect_unison')

def _cooperative__finish_canonical_sequence_projection(self, active_order):
    """GUI-owned panel/UI commits, never run by the numerical worker."""
    yield None
    try:
        yield from self._cooperative__engine_resize_untouched_sequences()
    except Exception as _exc:
        print(f'[Unison] untouched sequence resize: {_exc}')
    try:
        for _src in active_order:
            yield None
            yield from self._cooperative__engine_write_sequence_panels(source=_src)
    except Exception as _exc:
        print(f'[Unison] sequence addon panels: {_exc}')
    self._refresh_sequence_dependent_panels()

def _cooperative__paint_operator_pattern_to_playlist(self, source='randomizer', rng=None):
    """Deterministically paint the complete playlist schema (Script/Domain/Synth/Patch + timeline).

        User cells (``@u:`` instances) are immutable. Engine-owned material is
        regenerated from the seed + source and is fully tagged, so Randomizer /
        Phase-Lock can be removed without leaving stale cells or automation.
        Every generated row receives a value for every playlist column; inactive
        rows are explicit ``none``/zero values rather than undefined cells.
        """
    yield None
    source = 'phase_lock' if str(source) == 'phase-lock' else str(source)
    seed = int(self.get_numeric_seed() or 1)
    if rng is None:
        channel = 81 if 'random' in source else 167 if 'phase' in source else 211
        rng = np.random.default_rng((seed ^ channel) & 2147483647)
    rows = int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else DEFAULT_PLAYLIST_ROWS
    rows = max(1, min(1024, rows))
    if hasattr(self, 'spin_playlist_length'):
        try:
            self.spin_playlist_length.blockSignals(True)
            self.spin_playlist_length.setValue(rows)
        finally:
            self.spin_playlist_length.blockSignals(False)
    if not hasattr(self, 'master_playlist_data') or self.master_playlist_data is None:
        self.master_playlist_data = []
    while len(self.master_playlist_data) < rows:
        yield None
        self.master_playlist_data.append({})
    if not hasattr(self, 'playlist_automation') or self.playlist_automation is None:
        self.playlist_automation = []
    while len(self.playlist_automation) < rows:
        yield None
        self.playlist_automation.append({})
    if not hasattr(self, '_engine_generated_playlist_rows'):
        self._engine_generated_playlist_rows = set()
    names = list(getattr(self, 'instrument_names_48', []) or ['Operator'])
    if hasattr(self, '_ensure_sequence_banks_after_resize'):
        self._ensure_sequence_banks_after_resize()
    table = getattr(self, 'active_paint_table', None)
    painted = 0
    source_code = {'randomizer': 'R', 'phase_lock': 'P', 'midpoint': 'M', 'euclidean': 'E', 'seeded': 'S'}.get(source, 'G')

    def user_tokens(cell):
        return [p.strip() for p in str(cell or '').split(',') if '@u:' in p]

    def table_set(r, c, text):
        if table is None:
            return
        tw = getattr(table, 'table_widget', table)
        try:
            if hasattr(table, 'set_cell_item'):
                table.set_cell_item(r, c, QTableWidgetItem(str(text)))
            elif hasattr(tw, 'setItem'):
                tw.setItem(r, c, QTableWidgetItem(str(text)))
        except Exception:
            pass
    for r in range(rows):
        yield None
        e = self.master_playlist_data[r]
        if not isinstance(e, dict):
            e = {}
            self.master_playlist_data[r] = e
        if '_playlist_time_anchor' not in e:
            try:
                _anchor0 = float(e.get('time_offset'))
                if math.isfinite(_anchor0):
                    e['_playlist_time_anchor'] = _anchor0
            except Exception:
                _tm0 = str(e.get('time_marker') or '').strip()
                if _tm0:
                    try:
                        _anchor0 = float(_tm0.lstrip('e:').rstrip('s'))
                        if math.isfinite(_anchor0):
                            e['_playlist_time_anchor'] = _anchor0
                    except Exception:
                        pass

        def _ui_token(u):
            if isinstance(u, dict):
                return str(u.get('operator') or u.get('name') or '').strip()
            return str(u).strip()
        _raw_users = e.get('user_instances') or []
        users = [t for t in (_ui_token(u) for u in _raw_users) if t]
        old_ops = e.get('operators_csv', e.get('operator', ''))
        if not users and (not _raw_users):
            users = user_tokens(old_ops)
        contribs = e.setdefault('engine_contributions', {})
        if not isinstance(contribs, dict):
            contribs = {}
            e['engine_contributions'] = contribs
        contribs.pop(str(source), None)
        if isinstance(self.playlist_automation[r], dict) and self.playlist_automation[r].get('generated_by_engine'):
            self.playlist_automation[r] = {}
        source_hash = sum(((j + 1) * ord(ch) for j, ch in enumerate(str(source)))) & 2147483647
        row_key = (seed ^ (r + 1) * 2654435761 ^ source_hash) & 2147483647
        rr = np.random.default_rng(row_key)
        active = True
        n_available = len(names)
        if n_available:
            n_inst = min(n_available, max(2, int(round(math.sqrt(n_available) * 1.5))))
            perm = rr.permutation(n_available)
            idxs = [int(x) for x in perm[:n_inst]]
            shift = (r + source_hash + (seed & 65535)) % n_available
            idxs = [int((x + shift) % n_available) for x in idxs]
            idxs = list(dict.fromkeys(idxs))
        else:
            n_inst, idxs = (1, [0])
        eng_ops = [names[i] for i in idxs]
        tag = f'@e:{source[:4]}:{seed & 1048575:05x}:{r:03d}'
        snap = bool(getattr(self, 'chk_snap_grid', None) and self.chk_snap_grid.isChecked())
        if snap:
            t_off = r * (0.125 + 0.031 * MEUM_NORM)
        else:
            t_off = r * (0.125 + 0.031 * MEUM_NORM) + float(rr.uniform(-0.045, 0.045))
        if not active:
            t_off = r * (0.125 + 0.031 * MEUM_NORM)
        velocity = 1.0 if active else 0.0
        target = ('eqr', 'fractalizer', 'pkp_envelope', 'filter', 'drive')[int(rr.integers(0, 5))] if active else 'none'
        amount = float(np.clip(0.22 + 0.62 * rr.random(), 0.0, 0.95)) if active else 0.0
        direction = float(ot_sin_vec_equiv((r + 1) * MEUM_INV + seed % 991 * 0.013)) if active else 0.0
        coverage_map = {op: float(np.clip(0.3 + 0.55 * rr.random(), 0.0, 1.0)) for op in eng_ops}
        coverage = '|'.join((f'{k}:{v:.0%}' for k, v in coverage_map.items())) if active else '0%'
        partner = eng_ops[1] if active and len(eng_ops) > 1 else ''
        primary_op = eng_ops[0] if eng_ops else users[0] if users else 'Operator'
        struct = idealized_operator_struct(self, primary_op, row=r, seed=seed)
        if len(eng_ops) > 1:
            for sec in eng_ops[1:]:
                yield None
                sec_struct = idealized_operator_struct(self, sec, row=r, seed=seed)
                cov_a = float(coverage_map.get(primary_op, 0.5))
                cov_b = float(coverage_map.get(sec, 0.5))
                amt = float(min(cov_a, cov_b)) * 0.5
                for sk in PLAYLIST_STRUCT_COLUMNS:
                    yield None
                    struct[sk] = blend_struct_labels(struct.get(sk, ''), sec_struct.get(sk, ''), amt)
        script = struct.get('script_tag') or ''
        if not script and eng_ops and hasattr(self, 'instrument_scripts'):
            script = str((self.instrument_scripts.get(eng_ops[0]) or '').splitlines()[0]).strip()
        if not script:
            script = f'Meum:{source}:seed={seed}:row={r}'
        domain_tag = struct.get('domain_tag') or f'Dom::{str(primary_op)[:8]}[t]'
        synth_tag = struct.get('synth_tag') or f'Synth::{str(primary_op)[:10]}'
        patch_tag = struct.get('patch_tag') or f'Patch::{str(primary_op)[:8]}'
        engine_csv = ', '.join(eng_ops)
        combined_csv = ', '.join(dict.fromkeys(users + eng_ops))
        sequence_refs = []
        phase_offsets = {}
        for _op in eng_ops:
            yield None
            _bank = (getattr(self, 'instrument_sequence_banks', {}) or {}).get(_op, {})
            _ids = sorted(_bank) or [1]
            _owner = f'canonical:{source}'
            _owned = [sid for sid in _ids if isinstance(_bank.get(sid), dict) and _bank[sid].get('canonical_owner') == _owner]
            pool = _owned or _ids
            _sid = pool[(r + int(seed) + source_hash) % len(pool)]
            _plen = int((_bank.get(_sid, {}) or {}).get('pattern_length', DEFAULT_SEQUENCE_LENGTH))
            _phase = int((r * (1 + _sid % 5) + (seed & 65535)) % max(_plen, 1))
            sequence_refs.append(f'{_op}#S{_sid}')
            phase_offsets[_op] = _phase
        multi_seq = ', '.join(sequence_refs or eng_ops)
        position = f'e:q:{r}' if snap else f'e:{t_off:.4f}s'
        fields = {'time_marker': position, 'operator': users[0] if users else eng_ops[0] if eng_ops else '', 'operators': list(dict.fromkeys(users + eng_ops)), 'operators_csv': combined_csv, 'script_tag': script, 'domain_tag': domain_tag, 'synth_tag': synth_tag, 'patch_tag': patch_tag, 'velocity': velocity, 'effect_target': target, 'auto_amount': f'{amount * 100:.1f}%', 'direction_vector': f'{direction:+.4f}', 'multi_seq': multi_seq, 'sequence_refs': sequence_refs, 'phase_offsets': phase_offsets, 'sequence_index': int((r + int(seed)) % max(1, len(sequence_refs))) if sequence_refs else 1, 'coverage_map': coverage_map, 'coverage': coverage, 'blend_partner': partner, 'time_offset': float(t_off), 'position': position, 'generated_source': source, 'generated_by_engine': True, 'canonical_weight': 1.0 / max(1, self._canonical_active_count()), 'velocity_user_locked': False, 'active': active, 'paint_target': f'{source} → Playlist', 'paint_source': f'Canonical {source} · {primary_op}', 'paint_sequence': ', '.join(sequence_refs or [f'{primary_op}#S1']), 'paint_instrument': ', '.join(dict.fromkeys(eng_ops or users))}
        locked_cols = set()
        if self._canonical_protect_user():
            try:
                locked_cols.update((int(c) for c in e.get('user_locked_columns') or []))
            except Exception:
                pass
            if table is not None:
                touched = getattr(table, 'playlist_user_touched', set()) or set()
                locked_cols.update((c for rr, c in touched if rr == r))
        field_by_col = {0: 'time_marker', 1: 'operators_csv', 2: 'script_tag', 3: 'domain_tag', 4: 'synth_tag', 5: 'patch_tag', 6: 'velocity', 7: 'effect_target', 8: 'auto_amount', 9: 'direction_vector', 10: 'multi_seq', 11: 'coverage', 12: 'blend_partner', 13: 'goava_sequence', 14: 'paint_target', 15: 'paint_source', 16: 'paint_sequence', 17: 'paint_instrument'}
        for c in sorted(locked_cols):
            yield None
            key = field_by_col.get(c)
            if key is None or table is None:
                continue
            item = table.item(r, c)
            if item is None:
                continue
            text = (item.text() or '').strip()
            if c == 6:
                try:
                    text_v = float(text.replace('%', '').strip())
                    fields[key] = text_v / 100.0 if text_v > 1.0 else text_v
                except Exception:
                    continue
            else:
                fields[key] = text
            if c == 1:
                ops_locked = [p.split('@')[0].strip() for p in text.split(',') if p.strip()]
                fields['operator'] = ops_locked[0] if ops_locked else fields.get('operator', '')
                fields['operators'] = ops_locked
                fields['operators_csv'] = text
            elif c == 7:
                fields['modulation'] = text
                fields['effect_target'] = text
            elif c == 9:
                fields['direction'] = 1.0 if text.startswith('+') or text.endswith('+') else -1.0 if text.startswith(('-', '−')) or text.endswith(('-', '−')) else 0.0
        if locked_cols:
            fields['user_locked_columns'] = sorted(locked_cols)
        contribution_keys = ('operators', 'script_tag', 'domain_tag', 'synth_tag', 'patch_tag', 'velocity', 'effect_target', 'auto_amount', 'direction_vector', 'direction', 'multi_seq', 'sequence_refs', 'phase_offsets', 'sequence_index', 'canonical_weight', 'coverage_map', 'coverage', 'blend_partner', 'time_offset', 'active', 'paint_target', 'paint_source', 'paint_sequence', 'paint_instrument')
        e.setdefault('engine_contributions', {})[str(source)] = {k: copy.deepcopy(fields.get(k)) for k in contribution_keys}
        _time_user_locked = 0 in locked_cols
        _time_anchor_before = e.get('_playlist_time_anchor')
        e.update(fields)
        if _time_user_locked:
            try:
                _ta = float(e.get('time_offset'))
                if math.isfinite(_ta):
                    e['_playlist_time_anchor'] = _ta
            except Exception:
                pass
        elif _time_anchor_before is not None:
            try:
                _ta = float(_time_anchor_before)
                if math.isfinite(_ta):
                    e['time_offset'] = _ta
                    e['time_marker'] = f'e:{_ta:.4f}s'
            except Exception:
                pass
        if users:
            e['user_instances'] = users
        self._reconcile_engine_playlist_row(e, users)
        self._engine_generated_playlist_rows.add(r)
        if not (isinstance(self.playlist_automation[r], dict) and self.playlist_automation[r].get('user_owned')):
            self.playlist_automation[r] = {'generated_by_engine': True, 'operator': eng_ops[0] if eng_ops else '', 'operators': list(eng_ops), 'param': target, 'amount': amount, 'direction': 1.0 if direction >= 0 else -1.0, 'coverage': float(np.mean(list(coverage_map.values()))) if coverage_map else 0.0, 'overlap': float(min(coverage_map.values())) if len(coverage_map) > 1 else 0.0, 'blend_percent': float(np.clip(50.0 + 35.0 * ot_sin_vec_equiv((r + 1) * MEUM_NORM + seed * 0.001), 0.0, 100.0)), 'partner': partner, 'mode': f'engine:{source}', 'position': position, 'seed': seed, 'row': r}
        table_set(r, 0, fields['time_marker'])
        table_set(r, 1, fields['operators_csv'])
        table_set(r, 2, fields['script_tag'])
        table_set(r, 3, fields['domain_tag'])
        table_set(r, 4, fields['synth_tag'])
        table_set(r, 5, fields['patch_tag'])
        table_set(r, 6, f'{velocity * 100:.1f}%')
        table_set(r, 7, target)
        table_set(r, 8, fields['auto_amount'])
        table_set(r, 9, fields['direction_vector'])
        table_set(r, 10, multi_seq)
        table_set(r, 11, coverage)
        table_set(r, 12, partner)
        table_set(r, 13, fields.get('goava_sequence', e.get('goava_sequence', '')))
        table_set(r, 14, fields.get('paint_target', e.get('paint_target', '')))
        table_set(r, 15, fields.get('paint_source', e.get('paint_source', '')))
        table_set(r, 16, fields.get('paint_sequence', e.get('paint_sequence', '')))
        table_set(r, 17, fields.get('paint_instrument', e.get('paint_instrument', '')))
        painted += 1
    names = list(getattr(self, 'instrument_names_48', []) or ['Operator'])
    for _ri, _entry in enumerate(self.master_playlist_data):
        yield None
        if not isinstance(_entry, dict):
            continue
        if not _entry.get('generated_by_engine'):
            for _k in ('script_tag', 'domain_tag', 'synth_tag', 'patch_tag', 'direction_vector', 'multi_seq', 'coverage', 'blend_partner'):
                yield None
                _entry.setdefault(_k, '')
            continue
        if not str(_entry.get('time_marker') or '').strip():
            t_off = _ri * (0.125 + 0.031 * MEUM_NORM)
            _entry['time_marker'] = f'e:{t_off:.4f}s'
            _entry['time_offset'] = float(t_off)
        op_name = _entry.get('operator') or (names[_ri % len(names)] if names else 'Operator')
        _ops_for_struct = _entry.get('operators') or [op_name]
        if isinstance(_ops_for_struct, str):
            _ops_for_struct = [x.strip() for x in _ops_for_struct.split(',') if x.strip()]
        _structs = []
        for _oi, _oname in enumerate(_ops_for_struct[:8]):
            yield None
            try:
                _structs.append(idealized_operator_struct(self, _oname, row=_ri + _oi))
            except Exception:
                pass
        for _sk in PLAYLIST_STRUCT_COLUMNS:
            yield None
            _vals = []
            for _st in _structs:
                yield None
                _v = str(_st.get(_sk, '') or '').strip()
                if _v and _v not in _vals:
                    _vals.append(_v)
            if _vals:
                _entry[_sk] = ' | '.join(_vals[:8])
            elif not str(_entry.get(_sk) or '').strip():
                _entry[_sk] = f"{_sk.split('_')[0].title()}::{op_name}"
        _entry['operators'] = list(dict.fromkeys([str(x).strip() for x in _ops_for_struct if str(x).strip()])) or [op_name]
        _entry['operators_csv'] = ', '.join(_entry['operators'])
        if not str(_entry.get('direction_vector') or '').strip():
            signed = 1.0 if _ri % 2 == 0 else -1.0
            _entry['direction_vector'] = f'{signed:+.4f}'
            _entry['direction'] = signed
        if not str(_entry.get('multi_seq') or '').strip():
            ops = _entry.get('operators') or []
            if isinstance(ops, str):
                ops = [p.strip() for p in ops.split(',') if p.strip()]
            _entry['multi_seq'] = ', '.join(ops) if ops else names[_ri % len(names)] if names else ''
        if not str(_entry.get('coverage') or '').strip():
            _entry['coverage'] = '50%' if _entry.get('active', True) else '0%'
        if not str(_entry.get('blend_partner') or '').strip():
            _entry['blend_partner'] = names[(_ri * 3 + 1) % len(names)] if names else ''
        _op_tail = str(_entry.get('operator') or op_name)
        _seq_tail = str(_entry.get('multi_seq') or _op_tail)
        if getattr(self, 'goava_active', False):
            _entry['goava_sequence'] = str(_entry.get('goava_sequence') or f'GOAVA step={_ri + 1}')
        else:
            _entry['goava_sequence'] = str(_entry.get('goava_sequence') or '—')
        _entry['paint_target'] = str(_entry.get('paint_target') or 'Canonical → Playlist')
        _entry['paint_source'] = str(_entry.get('paint_source') or f"Unison: {', '.join(_entry['operators'][:8])}")
        _entry['paint_sequence'] = str(_entry.get('paint_sequence') or _seq_tail)
        _entry['paint_instrument'] = str(_entry.get('paint_instrument') or ', '.join(_entry['operators'][:8]))
    if table is not None:
        try:
            getattr(table, 'table_widget', table).viewport().update()
        except Exception:
            pass
    return painted

def _cooperative__rebuild_active_canonical_playlist(self, reason='toggle'):
    """Authoritative, order-independent canonical rebuild with decisive unity feedback.

        Every active canonical method writes against the identical baseline.  The
        resulting candidate states are then combined by one deterministic consensus
        pass.  Consequently activation order cannot decide playlist content.
        """
    yield None
    if getattr(self, '_canonical_rebuild_guard', False):
        return
    if getattr(self, '_playlist_cleared_hold', False):
        try:
            _active_now = self._get_active_engine_set()
        except Exception:
            _active_now = set()
        if not _active_now:
            return
        self._playlist_cleared_hold = False
    self._canonical_rebuild_guard = True
    try:
        try:
            self._reset_canonical_engine_derived_state()
        except Exception:
            pass
        import copy
        rows = max(1, min(1024, int(self.spin_playlist_length.value()) if hasattr(self, 'spin_playlist_length') else DEFAULT_PLAYLIST_ROWS))
        if not hasattr(self, 'master_playlist_data') or self.master_playlist_data is None:
            self.master_playlist_data = []
        while len(self.master_playlist_data) < rows:
            yield None
            self.master_playlist_data.append({})
        if not hasattr(self, 'playlist_automation') or self.playlist_automation is None:
            self.playlist_automation = []
        while len(self.playlist_automation) < rows:
            yield None
            self.playlist_automation.append({})
        raw_baseline = copy.deepcopy(self.master_playlist_data[:rows])
        generated_fields = {'operator', 'operators', 'operators_csv', 'sequence_refs', 'phase_offsets', 'multi_seq', 'direction', 'direction_vector', 'coverage', 'blend_partner', 'goava_sequence', 'paint_target', 'paint_source', 'paint_sequence', 'paint_instrument', 'time_marker', 'time_offset', 'velocity', 'pitch', 'probability', 'generated_by_engine', 'generated_source', 'canonical_weight'}
        baseline = []
        names_for_baseline = list(getattr(self, 'instrument_names_48', []) or ['Operator'])
        for r, src in enumerate(raw_baseline):
            yield None
            e = copy.deepcopy(src) if isinstance(src, dict) else {}
            users = e.get('user_instances') or []
            for k in generated_fields:
                yield None
                e.pop(k, None)
            e.pop('engine_contributions', None)
            e['user_instances'] = copy.deepcopy(users)
            user_ops = []
            for u in users:
                yield None
                if isinstance(u, dict):
                    uop = str(u.get('operator') or u.get('name') or '').strip()
                else:
                    uop = str(u or '').strip()
                if uop and uop.casefold() != 'goava':
                    user_ops.append(uop)
            if user_ops:
                e['operator'] = sorted(set(user_ops), key=str.casefold)[0]
                e['operators'] = sorted(set(user_ops), key=str.casefold)
                e['operators_csv'] = ', '.join(e['operators'])
            else:
                e['operator'] = names_for_baseline[r % len(names_for_baseline)]
                e['operators'] = [e['operator']]
                e['operators_csv'] = e['operator']
            e['_unison_base_operator'] = str(e.get('operator') or names_for_baseline[r % len(names_for_baseline)])
            baseline.append(e)
        self.master_playlist_data = copy.deepcopy(baseline)
        yield from self._cooperative__canonical_sequence_reconcile(reason)
        baseline = copy.deepcopy(self.master_playlist_data[:rows])
        baseline_sequence_banks = copy.deepcopy(getattr(self, 'instrument_sequence_banks', {}) or {})
        baseline_sequencer_memory = copy.deepcopy(getattr(self, 'instrument_sequencer_memory', {}) or {})
        baseline_selected_sequences = copy.deepcopy(getattr(self, 'instrument_selected_sequence', {}) or {})
        active = []
        pairs = (('seeded', 'btn_seeded_randomize'), ('randomizer', 'btn_local_randomize'), ('phase_lock', 'btn_local_phase_lock'), ('euclidean', 'btn_idealize_rhythm'))
        for source, attr in pairs:
            yield None
            btn = getattr(self, attr, None)
            if btn is not None and btn.isChecked() and (self._canonical_level(source) > 0.0):
                active.append(source)
        if getattr(self, 'goava_active', False) and self._canonical_level('goava') > 0.0:
            if not getattr(self, 'goava_note_events', None):
                self.goava_note_events = self._build_goava_composition()
            active.append('goava')
        canonical_input_ctx = self._canonical_input_context()
        self._canonical_render_input_context = dict(canonical_input_ctx)
        _carrier_salt = int(canonical_input_ctx.get('carrier_rms', 0.0) * 1000003) ^ int(canonical_input_ctx.get('carrier_peak', 0.0) * 1000033)
        _unison_salt = int(canonical_input_ctx.get('canonical_mask', 0))
        candidates = []
        for source in active:
            yield None
            self.master_playlist_data = copy.deepcopy(baseline)
            self.instrument_sequence_banks = copy.deepcopy(baseline_sequence_banks)
            self.instrument_sequencer_memory = copy.deepcopy(baseline_sequencer_memory)
            self.instrument_selected_sequence = copy.deepcopy(baseline_selected_sequences)
            if source == 'goava':
                self._apply_goava_to_canonical_playlist()
            else:
                source_seed = self._canonical_seed_for_source(source)
                rng = np.random.default_rng((_safe_int_seed(source_seed) ^ sum(map(ord, source)) ^ rows ^ _carrier_salt ^ _unison_salt) & 2147483647)
                yield from self._cooperative__canonical_playlist_paint(rng=rng, mode=source, strength=0.55 * self._canonical_level(source))
            candidates.append((source, copy.deepcopy(self.master_playlist_data[:rows])))
        self._canonical_unity_consensus(baseline, candidates, rows)
        self.instrument_sequence_banks = copy.deepcopy(baseline_sequence_banks)
        self.instrument_sequencer_memory = copy.deepcopy(baseline_sequencer_memory)
        self.instrument_selected_sequence = copy.deepcopy(baseline_selected_sequences)
        yield from self._cooperative__canonical_sequence_reconcile('unity_consensus')
        self._canonical_unison_step_lattice(rows, self.instrument_sequence_banks)
        self._canonical_finalize_playlist_field_lattice(rows)
        try:
            self._canonical_assign_row_write_modes(rows)
        except Exception as _wm_exc:
            print(f'[Canonical] row write modes: {_wm_exc}')
        for _r, _e in enumerate(self.master_playlist_data[:rows]):
            yield None
            if not isinstance(_e, dict):
                continue
            _op = str(_e.get('operator') or 'Operator').strip()
            _seq = str(_e.get('paint_sequence') or _e.get('multi_seq') or f'{_op}#S1')
            _e['paint_target'] = str(_e.get('paint_target') or 'Canonical → Playlist')
            _e['paint_source'] = str(_e.get('paint_source') or f'Canonical unison · {_op}')
            _e['paint_sequence'] = _seq
            _e['paint_instrument'] = str(_e.get('paint_instrument') or _op)
            if getattr(self, 'goava_active', False) and (not str(_e.get('goava_sequence') or '').strip()):
                _evs = list(getattr(self, 'goava_note_events', []) or [])
                if _evs:
                    _ev = _evs[_r % len(_evs)]
                    _e['goava_sequence'] = f"GOAVA step={_r + 1} seed={_ev['seed']:.9g} raw={_ev['raw']:.9g} hz={_ev['frequency']:.6f} pitch={_ev['pitch']:.6f} on={int(_ev['enabled'])}"
        for _r, _e in enumerate(self.master_playlist_data[:rows]):
            yield None
            if not isinstance(_e, dict):
                continue
            refs = _e.get('sequence_refs') or []
            if isinstance(refs, str):
                refs = [x.strip() for x in refs.split(',') if x.strip()]
            ops = _e.get('operators') or []
            if isinstance(ops, str):
                ops = [x.strip() for x in ops.split(',') if x.strip()]
            ops = list(dict.fromkeys([str(x).strip() for x in ops if str(x).strip()]))
            ref_ops = []
            for _ref in refs:
                yield None
                _name = str(_ref).split('#S', 1)[0].strip()
                if _name and _name not in ref_ops:
                    ref_ops.append(_name)
            roster = [str(x).strip() for x in getattr(self, 'instrument_names_48', []) or [] if str(x).strip()]
            final_ops = list(dict.fromkeys(ref_ops + ops + roster))
            if final_ops:
                _e['operators'] = final_ops
                _e['operators_csv'] = ', '.join(final_ops)
            _op = str(_e.get('operator') or (final_ops[0] if final_ops else 'Operator')).strip()
            _seq = ', '.join((str(x) for x in refs if str(x).strip())) or str(_e.get('multi_seq') or f'{_op}#S1')
            _e['multi_seq'] = _seq
            _e['blend_partner'] = str(_e.get('blend_partner') or (final_ops[1] if len(final_ops) > 1 else final_ops[0] if final_ops else _op))
            _e['goava_sequence'] = str(_e.get('goava_sequence') or (f'GOAVA step={_r + 1}' if getattr(self, 'goava_active', False) else '—'))
            _e['paint_target'] = str(_e.get('paint_target') or 'Canonical → Playlist')
            _e['paint_source'] = str(_e.get('paint_source') or 'Canonical unison · ' + ', '.join(final_ops or [_op]))
            _e['paint_sequence'] = str(_e.get('paint_sequence') or _seq)
            _e['paint_instrument'] = str(_e.get('paint_instrument') or ', '.join(final_ops or [_op]))
            _defaults = {'script_tag': f'Script::{_op[:8].upper()}-X{_r}', 'domain_tag': 'Canonical Unity', 'synth_tag': f'Synth::{_op[:8]}', 'patch_tag': f'Patch::{_op[:8]}', 'effect_target': 'Canonical Unison', 'auto_amount': '0.000', 'time_marker': _e.get('time_marker') or f'T + {_r * 3.5:.1f}s', 'time_offset': _e.get('time_offset', _r), 'velocity': _e.get('velocity', 1.0), 'coverage': _e.get('coverage') or '100%', 'direction_vector': _e.get('direction_vector') or '+1.0000'}
            for _k, _v in _defaults.items():
                yield None
                if _e.get(_k) in (None, '', []):
                    _e[_k] = _v
            try:
                apply_live_parametrics_to_entry(self, _e, row_idx=_r)
            except Exception:
                if not _e.get('live_parametrics'):
                    _e['live_parametrics'] = f'# placeholder row={_r} until live composition'
            _tail_defaults = {'blend_partner': _e.get('blend_partner') or (final_ops[1] if len(final_ops) > 1 else _op or 'Operator'), 'goava_sequence': _e.get('goava_sequence') or (f'GOAVA step={_r + 1}' if getattr(self, 'goava_active', False) else '—'), 'paint_target': _e.get('paint_target') or 'Canonical → Playlist', 'paint_source': _e.get('paint_source') or 'Canonical unison · ' + ', '.join(final_ops or [_op]), 'paint_sequence': _e.get('paint_sequence') or _seq, 'paint_instrument': _e.get('paint_instrument') or ', '.join(final_ops or [_op])}
            for _k, _v in _tail_defaults.items():
                yield None
                if _e.get(_k) in (None, '', []):
                    _e[_k] = str(_v)
        self._sync_playlist_paint_table_from_memory()
    finally:
        self._canonical_rebuild_guard = False

def _cooperative_apply_euclidean_and_idealized_rhythms(self):
    """
        Additive Euclidean Phase-Lock (non-destructive where possible).

        - Never turns OFF a user-specified step.
        - Never lowers a user-specified amplitude.
        - Fills empty slots with Euclidean structure + spectral 'opposites'
          (low-amp complement hits) so the grid phase-locks without erasing
          the carrier (user) pattern.
        - Sporadic spectrum commutation via probability only on non-user slots.
        """
    yield None
    seed = self.bootstrap_seed_and_program_parameters()
    self.simplify_redundant_user_definitions()
    count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else DEFAULT_SEQUENCE_LENGTH
    rng = np.random.default_rng(_safe_int_seed(seed))
    filled = 0
    preserved = 0
    for i, name in enumerate(self.instrument_names_48):
        yield None
        seq_iter = list(self._iter_sequence_mems(name)) if hasattr(self, '_iter_sequence_mems') else [(1, self._current_sequence_mem(name) if hasattr(self, '_current_sequence_mem') else self.instrument_sequencer_memory[name])]
        for sid, mem in seq_iter:
            yield None
            pcount = int(mem.get('pattern_length', count))
            self._ensure_seq_mem_length(mem, pcount)
            user_mask = self._user_pattern_mask(mem, pcount, instrument_name=name)
            try:
                inst_seed = float(self._instrument_seed_float(i, sequence_id=sid))
            except Exception:
                inst_seed = float(seed)
            pulses = max(2, int((i * MEUM_CONSTANT + abs(inst_seed) % 5 + 3 + int(sid)) % 7) + 2)
            pulses = min(pulses, pcount)
            euclidean = _native_euclidean_legacy(pulses, pcount, 0)
            if euclidean is None:
                euclidean = [s * pulses % pcount < pulses for s in range(pcount)]
            user_density = sum(user_mask) / max(pcount, 1)
            for s in range(pcount):
                yield None
                if user_mask[s]:
                    preserved += 1
                    lock_env = 0.5 + 0.5 * abs(ot_sin_vec_equiv(s * np.pi / count))
                    mem['amplitudes'][s] = float(max(mem['amplitudes'][s], lock_env * 1.0))
                    mem['probabilities'][s] = max(int(mem['probabilities'][s]), 100)
                    continue
                is_eucl = euclidean[s]
                complement = not is_eucl and user_density > 0.35 and (rng.random() < 0.18)
                if is_eucl or complement:
                    mem['steps'][s] = True
                    mem.setdefault('engine_step_sources', {}).setdefault(int(s), set()).add(getattr(self, '_active_engine_write_source', 'euclidean'))
                    base_amp = 0.55 + 0.35 * abs(ot_sin_vec_equiv(s * np.pi / count + i * 0.1))
                    if complement:
                        base_amp *= 0.45
                    mem['amplitudes'][s] = float(np.clip(base_amp, 0.15, 1.0))
                    mem['probabilities'][s] = 100 if is_eucl else int(rng.integers(55, 85))
                    mem['offsets'][s] = float(np.clip(0.18 * series_sin((s + 1) * MEUM_INV + i * MEUM_NORM) + (float(rng.uniform(-0.5, 0.5)) if complement else 0.0), -0.5, 0.5))
                    filled += 1
    self._engines_write_automation_lanes(source='euclidean')
    if hasattr(self, '_canonical_playlist_paint'):
        yield from self._cooperative__canonical_playlist_paint(rng=rng, mode='euclidean', strength=0.55 * self._canonical_level('euclidean'))
    elif hasattr(self, '_paint_operator_pattern_to_playlist'):
        yield from self._cooperative__paint_operator_pattern_to_playlist(source='euclidean', rng=rng)
    if hasattr(self, '_sync_playlist_paint_table_from_memory'):
        try:
            self._sync_playlist_paint_table_from_memory()
        except Exception:
            pass
    self._record_engine_step_ownership('euclidean')
    if hasattr(self, '_sync_selected_sequence_mirrors'):
        self._sync_selected_sequence_mirrors()
    self.reload_active_instrument_sequencer_ui()
    print(f"[Euclidean Phase-Lock] Additive fill complete. Preserved user steps≈{preserved}, filled empty slots={filled}. Seed={(self._seed_text() if hasattr(self, 'input_seed_val') else seed)}")

def _cooperative_apply_seeded_harmonic_randomization(self):
    """
        Additive Seeded Harmonic Randomizer (non-destructive where possible).

        - Treats user ON steps + non-default amps as a carrier pattern.
        - Never turns OFF user steps; never overwrites user scripts that look customized.
        - Fractally echoes the user pattern into empty slots (self-similar repetition
          at seed-derived scales).
        - Only writes parameters the user has not specified.
        """
    yield None
    numeric_seed = self.bootstrap_seed_and_program_parameters()
    self.instrument_param_state = _coerce_instrument_param_state(getattr(self, 'instrument_param_state', {}))
    seed_bits = _safe_int_seed(numeric_seed)
    self.simplify_redundant_user_definitions()
    rng = np.random.default_rng(_safe_int_seed(numeric_seed))
    count = int(self.spin_seq_length.value()) if hasattr(self, 'spin_seq_length') else DEFAULT_SEQUENCE_LENGTH
    filled_steps = 0
    preserved_steps = 0
    scripts_written = 0
    wf_engine = getattr(self, 'wavefield_engine', None)
    if wf_engine is not None:
        if not getattr(wf_engine, 'wavefield', None):
            wf_engine.compute_wavefield()
        else:
            wf_engine.compute_wavefield()
    for i, name in enumerate(self.instrument_names_48):
        yield None
        seq_iter = list(self._iter_sequence_mems(name)) if hasattr(self, '_iter_sequence_mems') else [(1, self._current_sequence_mem(name) if hasattr(self, '_current_sequence_mem') else self.instrument_sequencer_memory[name])]
        for sid, mem in seq_iter:
            yield None
            pcount = int(mem.get('pattern_length', count))
            self._ensure_seq_mem_length(mem, pcount)
            user_mask = self._user_pattern_mask(mem, pcount, instrument_name=name)
            try:
                inst_seed = float(self._instrument_seed_float(i, sequence_id=sid))
                seed_bits = int(self._instrument_seed_int(i, name=name, sequence_id=sid))
            except Exception:
                inst_seed = float(numeric_seed)
                seed_bits = _safe_int_seed(numeric_seed)
            user_hits = [s for s in range(pcount) if user_mask[s] and mem['steps'][s]]
            user_amps = [mem['amplitudes'][s] for s in user_hits] if user_hits else [0.7]
            scales = [1]
            for k in range(1, 4):
                yield None
                sc = int(round(pcount / 2 ** k * (1.0 + (seed_bits >> k) % 5 * 0.05))) or 1
                if sc not in scales and sc < pcount:
                    scales.append(sc)
            for s in range(pcount):
                yield None
                if user_mask[s]:
                    preserved_steps += 1
                    continue
                echo_on = False
                echo_amp = 0.0
                if user_hits:
                    for sc in scales:
                        yield None
                        src = user_hits[(s * sc + int(abs(inst_seed)) % max(pcount, 1)) % len(user_hits)]
                        gate_p = 0.22 + 0.15 * ((int(abs(inst_seed)) + i + sc) % 5) / 5.0
                        if wf_engine is not None:
                            hints = wf_engine.get_hints(name, s)
                            if hints:
                                context = self._contextual_numerology(name, s, s) if hasattr(self, '_contextual_numerology') else 0.5
                                gate_p *= 0.75 + 0.5 * context
                                if hints['euclidean']:
                                    gate_p = min(0.85, gate_p + 0.2 * hints['seed_harmonic'])
                                else:
                                    gate_p *= 0.55
                        if rng.random() < gate_p:
                            echo_on = True
                            src_amp = mem['amplitudes'][src] if src < len(mem['amplitudes']) else 0.7
                            echo_amp = max(echo_amp, float(src_amp) * (0.55 / sc))
                            if wf_engine is not None:
                                hints = wf_engine.get_hints(name, s)
                                if hints:
                                    echo_amp = max(echo_amp, float(hints['envelope']) * 0.5)
                else:
                    base_p = 0.12
                    context = self._contextual_numerology(name, s, s) if hasattr(self, '_contextual_numerology') else 0.5
                    base_p *= 0.65 + 0.7 * context
                    if wf_engine is not None:
                        hints = wf_engine.get_hints(name, s)
                        if hints and hints['euclidean']:
                            base_p = 0.28 * hints['seed_harmonic']
                    if rng.random() < base_p:
                        echo_on = True
                        echo_amp = 0.35 + 0.25 * rng.random()
                        if wf_engine is not None:
                            hints = wf_engine.get_hints(name, s)
                            if hints:
                                echo_amp = max(echo_amp, float(hints['envelope']) * 0.55)
                if echo_on:
                    mem['steps'][s] = True
                    mem.setdefault('engine_step_sources', {}).setdefault(int(s), set()).add(getattr(self, '_active_engine_write_source', 'seeded'))
                    mem['amplitudes'][s] = float(np.clip(float(echo_amp), 1e-06, 1.0))
                    mem['probabilities'][s] = int(np.clip(round(50.0 + 50.0 * float(rng.random())), 1, 100))
                    if s < len(mem.get('pitches', [])):
                        ctx = self._contextual_numerology(name, s, s) if hasattr(self, '_contextual_numerology') else 0.5
                        mem['pitches'][s] = float(np.clip(_seed_to_pitch_ratio(self.get_numeric_seed() if hasattr(self, 'get_numeric_seed') else 1, i, s) * (0.9 + 0.2 * float(rng.random())), 1.0 / 32.0, 32.0))
                    mem['offsets'][s] = float(np.clip(0.24 * series_sin((s + 1) * MEUM + i * PHI) + rng.uniform(-1.0, 1.0), -0.5, 0.5))
                    filled_steps += 1
            if hasattr(self, 'instrument_scripts'):
                existing = self.instrument_scripts.get(name, '')
                is_stock = instrument_script_is_stock(existing)
                if is_stock:
                    harmonic_multiplier = float(i % 7 + 1) * MEUM_OVER_1_5
                    self.instrument_scripts[name] = f"# Seeded Geometric Resonance Script [{self._seed_text()}] for {name}\n# Canonical full-graph writer; additive user carrier remains protected.\ndef evaluate_wave(x, y, z, t=0.0, t_norm=0.0, graph=None):\n    m = {harmonic_multiplier}\n    spatial = ot_sin_vec_equiv((x + 0.25*graph_z) * m) * ot_cos_vec_equiv((y + 0.25*graph_x) / m) - isn(z * 0.5)\n    longitudinal = 0.5 + 0.5 * ics(graph_phase + t_norm * MEUM)\n    return {{'wave': spatial * (0.65 + 0.35*longitudinal), 'amp': 0.70 + 0.30*graph_u, 'pitch': 1.0 + 0.125*graph_curvature, 'pan': 2.0*graph_v-1.0}}"
                    scripts_written += 1
    self.generate_ideal_patch_bay_routing()
    self._engines_write_automation_lanes(source='seeded')
    try:
        seed_i = _safe_int_seed(self.get_numeric_seed())
        rng_pl = np.random.default_rng(seed_i ^ 24301)
        if hasattr(self, '_canonical_playlist_paint'):
            yield from self._cooperative__canonical_playlist_paint(rng=rng_pl, mode='seeded', strength=0.55)
        elif hasattr(self, '_paint_operator_pattern_to_playlist'):
            yield from self._cooperative__paint_operator_pattern_to_playlist(source='seeded', rng=rng_pl)
        if hasattr(self, '_sync_playlist_paint_table_from_memory'):
            self._sync_playlist_paint_table_from_memory()
    except Exception as _pl_exc:
        print(f'[Seeded Harmonic Randomizer] playlist paint skipped: {_pl_exc}')
    self._record_engine_step_ownership('seeded')
    if hasattr(self, '_sync_selected_sequence_mirrors'):
        self._sync_selected_sequence_mirrors()
    self.reload_active_instrument_sequencer_ui()
    if hasattr(self, '_engine_write_sequence_panels'):
        try:
            yield from self._cooperative__engine_write_sequence_panels(source='seeded')
        except Exception as _pe:
            print(f'[Seeded] sequence panel write skipped: {_pe}')
    print(f"[Seeded Harmonic Randomizer] Additive fractal fill. Preserved≈{preserved_steps}, filled={filled_steps}, scripts_updated={scripts_written}. Seed='{self._seed_text()}'")
