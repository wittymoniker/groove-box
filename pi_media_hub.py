#!/usr/bin/env python3
"""Compatibility shim: Media Hub was renamed to Performance in 2026."""
from performance import Performance, Performance as PiMediaHub, open_performance

def open_pi_media_hub(host):
    return open_performance(host)
