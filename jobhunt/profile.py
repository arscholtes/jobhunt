"""Load and validate profile.toml."""
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "profile.toml"
EXAMPLE = ROOT / "profile.example.toml"

REQUIRED = ("me", "search", "skills")


class ProfileError(RuntimeError):
    pass


def load(path=None):
    p = pathlib.Path(path) if path else PATH
    if not p.exists():
        raise ProfileError(
            f"No profile at {p}. Copy {EXAMPLE.name} to {p.name} and edit it."
        )
    with p.open("rb") as fh:
        data = tomllib.load(fh)

    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ProfileError(f"{p.name} is missing required section(s): {', '.join(missing)}")

    data.setdefault("interests", {})
    data.setdefault("culture", {})
    data.setdefault("dealbreakers", [])
    data.setdefault("boards", [])
    data["search"].setdefault("titles", [])
    data["search"].setdefault("exclude_titles", [])
    data["search"].setdefault("locations", [])
    data["search"].setdefault("remote_only", False)
    data["search"].setdefault("min_score", 0)
    return data
