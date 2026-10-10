import logging
import os
from pathlib import Path

from flask import Flask, jsonify

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import cors, db, limiter


def create_app(config_object: type[Config] | None = None, testing: bool = False) -> Flask:
    app = Flask(__name__)
    cfg = config_object or Config
    if testing:
        os.environ.setdefault("USE_HASH_EMBEDDINGS", "1")
        os.environ.setdefault("SKIP_EMBEDDING_WARMUP", "1")
        data = Path(os.environ.get("TEST_DATA_DIR", str(Path.cwd() / "data_test"))).resolve()
        data.mkdir(parents=True, exist_ok=True)
        app.config.from_object(cfg)
        app.config["TESTING"] = True
        app.config["DATA_DIR"] = data
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{(data / 'test.db').as_posix()}"
        app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_CONTENT_LENGTH
    else:
        cfg.ensure_dirs()
        app.config.from_object(cfg)
        app.config["DATA_DIR"] = cfg.DATA_DIR

    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    (Path(app.config["DATA_DIR"]) / "uploads").mkdir(parents=True, exist_ok=True)
    (Path(app.config["DATA_DIR"]) / "indexes").mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    limiter.init_app(app)
    register_error_handlers(app)

    from app.models import Chunk, Keyword, Paper, QAHistory, Section  # noqa: F401
    from app.routes.analyze import bp as analyze_bp
    from app.routes.health import bp as health_bp
    from app.routes.papers import bp as papers_bp
    from app.routes.qa import bp as qa_bp
    from app.routes.search import bp as search_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(papers_bp, url_prefix="/api/papers")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(analyze_bp, url_prefix="/api")
    app.register_blueprint(qa_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()
        if not testing:
            from app.services.embeddings import warmup
            from app.services.vector_store import get_vector_store
            from app.services.bm25_index import get_bm25

            warmup()
            get_vector_store()
            get_bm25()

    @app.get("/")
    def root():
        return jsonify(name="Research Paper Analyzer", status="ok")

    return app
