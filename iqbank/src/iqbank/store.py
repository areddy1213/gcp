"""SQLite store. Reruns are incremental: known URLs aren't refetched, unchanged docs aren't re-extracted."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from iqbank.models import ClusterRecord, Doc, LoopInfo, Question, QuestionRow, RawDoc

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id           INTEGER PRIMARY KEY,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    fetched_at   TEXT NOT NULL,
    raw_text     TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    meta_json    TEXT NOT NULL DEFAULT '{}'
);

-- URLs we looked at and chose not to keep (robots.txt, 404, irrelevant, no text).
CREATE TABLE IF NOT EXISTS skipped (
    url     TEXT PRIMARY KEY,
    source  TEXT NOT NULL,
    reason  TEXT NOT NULL,
    seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extractions (
    doc_id       INTEGER PRIMARY KEY REFERENCES docs(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    model        TEXT NOT NULL,
    status       TEXT NOT NULL,          -- ok | irrelevant | refused | error
    error        TEXT,
    loop_json    TEXT,
    extracted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id                      INTEGER PRIMARY KEY,
    doc_id                  INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
    question                TEXT NOT NULL,
    round_type              TEXT NOT NULL,
    category                TEXT NOT NULL,
    date_if_known           TEXT,
    source_url              TEXT NOT NULL,
    verbatim_or_paraphrased TEXT NOT NULL,
    role_if_known           TEXT,
    cluster_id              INTEGER REFERENCES clusters(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS questions_doc ON questions(doc_id);
CREATE INDEX IF NOT EXISTS questions_cluster ON questions(cluster_id);

CREATE TABLE IF NOT EXISTS clusters (
    id                 INTEGER PRIMARY KEY,
    canonical_question TEXT NOT NULL,
    round_type         TEXT NOT NULL,
    category           TEXT NOT NULL,
    source_count       INTEGER NOT NULL,
    mention_count      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: Path | str, *, readonly: bool = False):
        self.path = Path(path) if str(path) != ":memory:" else None
        self.readonly = readonly
        if readonly and (self.path is None or not self.path.exists()):
            # Dry run with no database yet: behave like an empty store, write nothing to disk.
            self.conn = sqlite3.connect(":memory:")
            self._init_schema()
        elif readonly:
            self.conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        else:
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(path))
            self._init_schema()
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    # ---- docs -------------------------------------------------------------

    @staticmethod
    def _row_to_doc(row: sqlite3.Row) -> Doc:
        return Doc(
            id=row["id"],
            url=row["url"],
            source=row["source"],
            title=row["title"],
            fetched_at=row["fetched_at"],
            raw_text=row["raw_text"],
            content_hash=row["content_hash"],
            meta=json.loads(row["meta_json"] or "{}"),
        )

    def has_doc(self, url: str) -> bool:
        return self.conn.execute("SELECT 1 FROM docs WHERE url = ?", (url,)).fetchone() is not None

    def get_doc(self, url: str) -> Doc | None:
        row = self.conn.execute("SELECT * FROM docs WHERE url = ?", (url,)).fetchone()
        return self._row_to_doc(row) if row else None

    def docs(self, source: str | None = None) -> list[Doc]:
        if source:
            rows = self.conn.execute("SELECT * FROM docs WHERE source = ? ORDER BY id", (source,))
        else:
            rows = self.conn.execute("SELECT * FROM docs ORDER BY id")
        return [self._row_to_doc(r) for r in rows]

    def upsert_doc(self, doc: RawDoc) -> str:
        """Insert or update a document. Returns "new", "updated" or "unchanged"."""
        digest = content_hash(doc.raw_text)
        existing = self.conn.execute(
            "SELECT id, content_hash FROM docs WHERE url = ?", (doc.url,)
        ).fetchone()
        meta_json = json.dumps(doc.meta, sort_keys=True, default=str)
        with self.tx() as c:
            if existing is None:
                c.execute(
                    "INSERT INTO docs (url, source, title, fetched_at, raw_text, content_hash, meta_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (doc.url, doc.source, doc.title, utcnow(), doc.raw_text, digest, meta_json),
                )
                c.execute("DELETE FROM skipped WHERE url = ?", (doc.url,))
                return "new"
            if existing["content_hash"] == digest:
                return "unchanged"
            c.execute(
                "UPDATE docs SET source = ?, title = ?, fetched_at = ?, raw_text = ?, content_hash = ?,"
                " meta_json = ? WHERE id = ?",
                (doc.source, doc.title, utcnow(), doc.raw_text, digest, meta_json, existing["id"]),
            )
            return "updated"

    def mark_skipped(self, url: str, source: str, reason: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO skipped (url, source, reason, seen_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(url) DO UPDATE SET reason = excluded.reason, seen_at = excluded.seen_at",
                (url, source, reason, utcnow()),
            )

    def is_skipped(self, url: str, ttl_days: int = 30) -> bool:
        row = self.conn.execute("SELECT seen_at FROM skipped WHERE url = ?", (url,)).fetchone()
        if row is None:
            return False
        seen = datetime.fromisoformat(row["seen_at"])
        return datetime.now(timezone.utc) - seen < timedelta(days=ttl_days)

    # ---- extraction -------------------------------------------------------

    def docs_pending_extraction(self, *, reextract: bool = False) -> list[Doc]:
        """Docs never extracted, changed since extraction, or whose last attempt errored."""
        if reextract:
            rows = self.conn.execute("SELECT * FROM docs ORDER BY id")
        else:
            rows = self.conn.execute(
                """
                SELECT d.* FROM docs d
                LEFT JOIN extractions e ON e.doc_id = d.id
                WHERE e.doc_id IS NULL OR e.content_hash != d.content_hash OR e.status = 'error'
                ORDER BY d.id
                """
            )
        return [self._row_to_doc(r) for r in rows]

    def save_extraction(
        self,
        doc: Doc,
        *,
        model: str,
        status: str,
        questions: Iterable[Question] = (),
        loop: LoopInfo | None = None,
        error: str | None = None,
    ) -> None:
        """Replace everything previously extracted from `doc` with this result."""
        with self.tx() as c:
            c.execute("DELETE FROM questions WHERE doc_id = ?", (doc.id,))
            c.executemany(
                "INSERT INTO questions (doc_id, question, round_type, category, date_if_known,"
                " source_url, verbatim_or_paraphrased, role_if_known) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        doc.id,
                        q.question,
                        q.round_type,
                        q.category,
                        q.date_if_known,
                        q.source_url,
                        q.verbatim_or_paraphrased,
                        q.role_if_known,
                    )
                    for q in questions
                ],
            )
            c.execute(
                "INSERT INTO extractions (doc_id, content_hash, model, status, error, loop_json, extracted_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(doc_id) DO UPDATE SET content_hash = excluded.content_hash,"
                " model = excluded.model, status = excluded.status, error = excluded.error,"
                " loop_json = excluded.loop_json, extracted_at = excluded.extracted_at",
                (
                    doc.id,
                    doc.content_hash,
                    model,
                    status,
                    error,
                    json.dumps(loop.to_dict()) if loop else None,
                    utcnow(),
                ),
            )

    def loops(self) -> list[tuple[Doc, LoopInfo]]:
        rows = self.conn.execute(
            "SELECT d.*, e.loop_json FROM extractions e JOIN docs d ON d.id = e.doc_id"
            " WHERE e.loop_json IS NOT NULL AND e.status = 'ok' ORDER BY d.id"
        )
        out = []
        for row in rows:
            loop = LoopInfo.from_dict(json.loads(row["loop_json"]))
            if loop.reported:
                out.append((self._row_to_doc(row), loop))
        return out

    # ---- questions & clusters -------------------------------------------------

    def questions(self) -> list[QuestionRow]:
        rows = self.conn.execute(
            """
            SELECT q.*, d.url AS doc_url, d.source AS doc_source, d.content_hash AS doc_content_hash,
                   d.meta_json AS doc_meta_json
            FROM questions q JOIN docs d ON d.id = q.doc_id
            ORDER BY q.id
            """
        )
        return [
            QuestionRow(
                id=r["id"],
                doc_id=r["doc_id"],
                question=r["question"],
                round_type=r["round_type"],
                category=r["category"],
                date_if_known=r["date_if_known"],
                source_url=r["source_url"],
                verbatim_or_paraphrased=r["verbatim_or_paraphrased"],
                role_if_known=r["role_if_known"],
                cluster_id=r["cluster_id"],
                doc_url=r["doc_url"],
                doc_source=r["doc_source"],
                doc_content_hash=r["doc_content_hash"],
                doc_meta=json.loads(r["doc_meta_json"] or "{}"),
            )
            for r in rows
        ]

    def replace_clusters(self, clusters: list[ClusterRecord]) -> None:
        with self.tx() as c:
            c.execute("UPDATE questions SET cluster_id = NULL")
            c.execute("DELETE FROM clusters")
            for cl in clusters:
                cur = c.execute(
                    "INSERT INTO clusters (canonical_question, round_type, category, source_count,"
                    " mention_count) VALUES (?, ?, ?, ?, ?)",
                    (cl.canonical_question, cl.round_type, cl.category, cl.source_count, cl.mention_count),
                )
                c.executemany(
                    "UPDATE questions SET cluster_id = ? WHERE id = ?",
                    [(cur.lastrowid, qid) for qid in cl.member_ids],
                )

    def clusters(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM clusters ORDER BY id")]

    # ---- meta & stats -----------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def stats(self) -> dict[str, Any]:
        def scalar(sql: str) -> int:
            return self.conn.execute(sql).fetchone()[0]

        return {
            "docs_by_source": {
                r["source"]: r["n"]
                for r in self.conn.execute("SELECT source, COUNT(*) AS n FROM docs GROUP BY source")
            },
            "extractions_by_status": {
                r["status"]: r["n"]
                for r in self.conn.execute("SELECT status, COUNT(*) AS n FROM extractions GROUP BY status")
            },
            "pending_extraction": len(self.docs_pending_extraction()),
            "skipped_urls": scalar("SELECT COUNT(*) FROM skipped"),
            "questions": scalar("SELECT COUNT(*) FROM questions"),
            "unclustered_questions": scalar("SELECT COUNT(*) FROM questions WHERE cluster_id IS NULL"),
            "clusters": scalar("SELECT COUNT(*) FROM clusters"),
        }
