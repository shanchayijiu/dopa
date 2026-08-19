# -*- coding: utf-8 -*-
"""Pytest bootstrap: put the project root on sys.path explicitly.

The suite imports modules by bare name (`import core`, `from infer_function
import nms_v8`). That worked only because pytest happened to prepend rootdir to
sys.path via rootdir/inserted-path heuristics. Making it explicit keeps the
tests working regardless of invocation directory, and stays correct once modules
move into packages.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
