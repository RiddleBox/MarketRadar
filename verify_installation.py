#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证依赖安装"""
import sys

print("=== Dependency Check ===\n")

critical_deps = [
    ("rich", "Terminal output"),
    ("yfinance", "US stock data"),
    ("pandas", "Data processing"),
    ("numpy", "Numerical computing"),
    ("pydantic", "Data validation"),
]

all_ok = True
for module, desc in critical_deps:
    try:
        __import__(module)
        print(f"[OK] {module:15s} - {desc}")
    except ImportError as e:
        print(f"[FAIL] {module:15s} - {desc} (MISSING)")
        all_ok = False

print()
if all_ok:
    print("[SUCCESS] All critical dependencies installed!")
    print("\nReady to start simulation:")
    print("  python run_continuous_simulation.py")
    sys.exit(0)
else:
    print("[ERROR] Some dependencies missing")
    sys.exit(1)
