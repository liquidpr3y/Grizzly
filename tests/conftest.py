import pytest

from grizzly.config import load_profile
from grizzly.pipeline import Pipeline
from grizzly.store import ProjectStore


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "projects")


@pytest.fixture
def pipeline(store):
    return Pipeline(load_profile("mock"), store)
