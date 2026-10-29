import importlib.util
from pathlib import Path


def test_no_hardcoded_sample_data_in_app():
    spec = importlib.util.spec_from_file_location("gate", Path(__file__).resolve().parents[1] / "scripts" / "gate.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    assert gate.scan() == []
