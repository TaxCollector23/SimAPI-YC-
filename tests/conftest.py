"""Shared pytest fixtures."""
import os
import sys

import pytest

# Ensure the package root is importable regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.testclient import TestClient  # noqa: E402

from api import server  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(server.app)


@pytest.fixture()
def sample_payload():
    return {
        "data": [
            {"cd": 0.31 + i * 0.001, "cl": 0.8 + i * 0.002, "re": 4.0e5, "ma": 0.04}
            for i in range(30)
        ],
        "simulation_type": "aerodynamics",
        "conditions": {"velocity": 15.0},
    }
