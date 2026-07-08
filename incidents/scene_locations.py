"""Predefined scene locations for incident reports."""

SCENE_LOCATION_OTHER = "__OTHER__"

SCENE_LOCATION_PRESETS = [
    ("QIT Building", "QIT Building"),
    ("Trim Building", "Trim Building"),
    ("Body Shop", "Body Shop"),
    ("Machine Shop", "Machine Shop"),
    ("Paint Shop", "Paint Shop"),
    ("Warehouse", "Warehouse"),
    ("Chassis Line", "Chassis Line"),
]

SCENE_LOCATION_PRESET_VALUES = {value for value, _ in SCENE_LOCATION_PRESETS}

SCENE_LOCATION_CHOICES = [
    ("", "Select location"),
    *SCENE_LOCATION_PRESETS,
    (SCENE_LOCATION_OTHER, "Other"),
]
