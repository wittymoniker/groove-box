"""User-specified background priorities; UI/audio callbacks never enter this queue."""
import math

WINDOW = 0.048
ACTIVITY = 0.19758
TEDIOUS = 1.0
TOTAL = WINDOW + ACTIVITY + TEDIOUS


def _unit(value):
    value = float(value)
    return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0


def work_score(window_selected=0.0, activity=0.0, tedious=0.0):
    return WINDOW * _unit(window_selected) + ACTIVITY * _unit(activity) + TEDIOUS * _unit(tedious)


def predictive_fraction(window_selected=0.0, activity=0.0, tedious=1.0):
    """At most one third of the available CPU budget, weighted by relevance."""
    return work_score(window_selected, activity, tedious) / TOTAL / 3.0
