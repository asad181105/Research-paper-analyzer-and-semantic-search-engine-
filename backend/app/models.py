from datetime import datetime

from app.extensions import db


class Paper(db.Model):
    __tablename__ = "papers"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(1024), nullable=False, default="Untitled")
    authors = db.Column(db.Text, default="")
    abstract = db.Column(db.Text, default="")
    year = db.Column(db.Integer, nullable=True)
    arxiv_id = db.Column(db.String(64), unique=True, nullable=True, index=True)
    doi = db.Column(db.String(256), nullable=True)
    venue = db.Column(db.String(512), nullable=True)
    citation_count = db.Column(db.Integer, default=0)
    file_hash = db.Column(db.String(64), unique=True, nullable=True, index=True)
    file_path = db.Column(db.String(1024), nullable=True)
    source = db.Column(db.String(32), default="upload")
    status = db.Column(db.String(32), default="queued", index=True)
    status_message = db.Column(db.Text, default="")
    progress = db.Column(db.Integer, default=0)
    summary_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sections = db.relationship(
        "Section", backref="paper", cascade="all, delete-orphan", lazy="dynamic"
    )
    chunks = db.relationship("Chunk", backref="paper", cascade="all, delete-orphan", lazy="dynamic")
    keywords = db.relationship(
        "Keyword", backref="paper", cascade="all, delete-orphan", lazy="dynamic"
    )
    qa_history = db.relationship(
        "QAHistory", backref="paper", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, include_summary: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "arxiv_id": self.arxiv_id,
            "doi": self.doi,
            "venue": self.venue,
            "citation_count": self.citation_count or 0,
            "source": self.source,
            "status": self.status,
            "status_message": self.status_message,
            "progress": self.progress or 0,
            "file_hash": self.file_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_summary:
            data["summary"] = self.summary_json
        return data


class Section(db.Model):
    __tablename__ = "sections"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    title_raw = db.Column(db.String(512), default="")
    text = db.Column(db.Text, default="")
    page_start = db.Column(db.Integer, default=1)
    page_end = db.Column(db.Integer, default=1)
    order = db.Column(db.Integer, default=0)

    chunks = db.relationship("Chunk", backref="section", lazy="dynamic")

    def to_dict(self, include_text: bool = True) -> dict:
        data = {
            "id": self.id,
            "paper_id": self.paper_id,
            "name": self.name,
            "title_raw": self.title_raw,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "order": self.order,
        }
        if include_text:
            data["text"] = self.text
        return data


class Chunk(db.Model):
    __tablename__ = "chunks"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False, index=True)
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"), nullable=True, index=True)
    text = db.Column(db.Text, nullable=False)
    page = db.Column(db.Integer, default=1)
    section_name = db.Column(db.String(64), default="other")
    chunk_index = db.Column(db.Integer, default=0)
    token_count = db.Column(db.Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "section_id": self.section_id,
            "text": self.text,
            "page": self.page,
            "section_name": self.section_name,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
        }


class Keyword(db.Model):
    __tablename__ = "keywords"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=False, index=True)
    keyword = db.Column(db.String(256), nullable=False)
    score = db.Column(db.Float, default=0.0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "keyword": self.keyword,
            "score": self.score,
        }


class QAHistory(db.Model):
    __tablename__ = "qa_history"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("papers.id"), nullable=True, index=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, default="")
    sources_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json

        try:
            sources = json.loads(self.sources_json or "[]")
        except json.JSONDecodeError:
            sources = []
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "question": self.question,
            "answer": self.answer,
            "sources": sources,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
