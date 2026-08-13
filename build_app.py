#!/usr/bin/env python3
"""Waynis AI — build: bashkon modulet në një app.py të vetëm."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["config", "turso", "providers", "brain", "mr_pipeline", "strategies",
         "learning", "backtest", "agents", "engine", "main"]

def main():
    parts = []
    for name in ORDER:
        path = os.path.join(BASE, f"{name}.py")
        with open(path, encoding="utf-8") as f:
            src = f.read().rstrip()
        parts.append(f"# ============ {name}.py ============\n{src}")
    merged = "\n".join(parts) + "\n"
    out = os.path.join(BASE, "app.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"OK: {out} ({len(merged)} bytes)")

if __name__ == "__main__":
    main()
