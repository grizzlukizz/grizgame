import json
from dataclasses import asdict, dataclass
from pathlib import Path

WINDOW_SIZES = ((960, 600), (1200, 760), (1600, 900))


@dataclass
class Preferences:
    fullscreen: bool = False
    window_size_index: int = 1
    volume: int = 60
    minimap: bool = True
    effects: bool = True
    difficulty: int = 1

    @classmethod
    def load(cls, path: Path, legacy_path: Path):
        defaults = cls()
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            try:
                defaults.fullscreen = legacy_path.read_text(encoding="utf-8").strip() == "fullscreen"
            except (OSError, UnicodeError):
                pass
            return defaults
        if not isinstance(values, dict):
            return defaults
        for key in ("fullscreen", "minimap", "effects"):
            value = values.get(key)
            if isinstance(value, bool):
                setattr(defaults, key, value)
        size = values.get("window_size_index")
        if type(size) is int and 0 <= size < len(WINDOW_SIZES):
            defaults.window_size_index = size
        difficulty = values.get("difficulty")
        if type(difficulty) is int and 0 <= difficulty <= 2:
            defaults.difficulty = difficulty
        volume = values.get("volume")
        if type(volume) is int:
            defaults.volume = max(0, min(100, volume))
        return defaults

    def save(self, path: Path):
        try:
            pending = path.with_suffix(".tmp")
            pending.write_text(json.dumps(asdict(self)), encoding="utf-8")
            pending.replace(path)
        except OSError:
            pass
