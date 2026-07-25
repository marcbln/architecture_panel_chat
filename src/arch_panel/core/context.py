from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodebaseContext:
    root_path: Path
