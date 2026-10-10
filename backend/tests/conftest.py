import os
import sys
from pathlib import Path

import pytest

os.environ["USE_HASH_EMBEDDINGS"] = "1"
os.environ["SKIP_EMBEDDING_WARMUP"] = "1"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def app(tmp_path):
    os.environ["TEST_DATA_DIR"] = str(tmp_path / "data")
    from app import create_app
    from app.services.bm25_index import reset_bm25
    from app.services.embeddings import reset_model
    from app.services.vector_store import reset_vector_store

    reset_bm25()
    reset_vector_store()
    reset_model()
    application = create_app(testing=True)
    yield application
    reset_bm25()
    reset_vector_store()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield app
