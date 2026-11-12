"""Seed pattern tools for Groovebox.

Stubs for:
- find_common_seed(files) -> seed that captures shared structure
- diff_to_seed(a, b) -> seed + location of the difference
- file_to_seed(path) -> seed for any file
- plan_render(seed_or_files, options) -> ready export job

These are designed to reuse the existing spectral / pixel seed paths
so results stay deterministic. Full implementation can call the same
analysis already used by Export ▸ Spectral & Pixel Seeds.
"""

def find_common_seed(paths):
    """Return a seed string that regenerates the common structure across files."""
    # TODO: extract features, intersect, encode via existing seed path
    return "COMMON_SEED_PLACEHOLDER"

def diff_to_seed(path_a, path_b):
    """Return (seed, location_description) for the structural difference."""
    return ("DIFF_SEED_PLACEHOLDER", "time/frame range TBD")

def file_to_seed(path):
    """Inverse: any supported file -> deterministic seed."""
    return "FILE_SEED_PLACEHOLDER"

def plan_render(seed, duration_s=30, resolution="1080p", audio_rate=48000, engines=None):
    """Return a dict describing a ready-to-queue export job."""
    return {
        "seed": seed,
        "duration_s": duration_s,
        "resolution": resolution,
        "audio_rate": audio_rate,
        "engines": engines or ["SEEDED", "LOCK"],
        "format": "mp4",
    }
