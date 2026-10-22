from __future__ import annotations

import json
import os
import time


def log_event(path: str, **event) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **event}, default=str) + "\n")
    except OSError:
        pass  # auditing must never break a request
