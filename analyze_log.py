#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze scheduler log tail"""

with open('data/logs/scheduler.log', 'rb') as f:
    f.seek(-10000, 2)
    data = f.read()

with open('log_tail_analysis.txt', 'w', encoding='utf-8') as out:
    out.write(data.decode('utf-8', errors='replace'))

print("Analysis written to log_tail_analysis.txt")
