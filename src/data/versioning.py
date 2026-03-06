"""
Processed dataset version resolution.

Single source of truth for resolve_processed_version(); used by train, eval, and feature_importance.
"""

from pathlib import Path


def resolve_processed_version(processed_root: Path, version_hint: str = "latest") -> str:
    """Resolve processed dataset version. 'latest' -> lexicographically last dir with features.csv."""
    if not processed_root.exists():
        raise FileNotFoundError(
            f"Processed root not found: {processed_root}. "
            "Run: python run.py build-features (or set paths in config)."
        )

    if version_hint != "latest":
        features_path = processed_root / version_hint / "features.csv"
        if features_path.exists():
            return version_hint
        raise FileNotFoundError(
            f"Processed version '{version_hint}' not found under {processed_root}. "
            "Run build-features or use a version that exists."
        )

    subdirs = [
        d.name
        for d in processed_root.iterdir()
        if d.is_dir() and (d / "features.csv").exists()
    ]
    if not subdirs:
        raise FileNotFoundError(
            f"No processed datasets (features.csv) in {processed_root}. "
            "Run: python run.py build-features."
        )
    return sorted(subdirs)[-1]
