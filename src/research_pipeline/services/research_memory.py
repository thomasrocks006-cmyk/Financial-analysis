"""Research Memory — simple FTS-based research corpus for institutional memory."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ResearchMemory:
    """SQLite FTS5-backed research memory store — no LLM, no vector DB.

    Stores past reports, claim ledgers, thesis records, and agent outputs
    in a searchable corpus. Uses SQLite full-text search as a lightweight
    alternative to a proper vector database.
    """

    def __init__(self, db_path: Path | str = "data/research_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database with FTS5 tables."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                ticker TEXT DEFAULT '',
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                doc_id, run_id, doc_type, ticker, title, content,
                content=documents, content_rowid=rowid
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(doc_id, run_id, doc_type, ticker, title, content)
                VALUES (new.doc_id, new.run_id, new.doc_type, new.ticker, new.title, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, doc_id, run_id, doc_type, ticker, title, content)
                VALUES ('delete', old.doc_id, old.run_id, old.doc_type, old.ticker, old.title, old.content);
            END;

            CREATE TABLE IF NOT EXISTS thesis_history (
                thesis_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                thesis_text TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                score REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                PRIMARY KEY (thesis_id, run_id)
            );
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Document Storage ──────────────────────────────────────────────
    def store_document(
        self,
        doc_id: str,
        run_id: str,
        doc_type: str,
        content: str,
        ticker: str = "",
        title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a document in the research memory."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT OR REPLACE INTO documents
               (doc_id, run_id, doc_type, ticker, title, content, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc_id, run_id, doc_type, ticker, title, content,
             json.dumps(metadata or {}), now),
        )
        conn.commit()
        logger.debug("Stored document %s (type=%s, ticker=%s)", doc_id, doc_type, ticker)

    def store_run_output(
        self,
        run_id: str,
        stage: int,
        agent_name: str,
        output: dict[str, Any],
        ticker: str = "",
    ) -> None:
        """Store a pipeline stage output as a searchable document."""
        doc_id = f"{run_id}-stage{stage}-{agent_name}"
        content = json.dumps(output, indent=2, default=str)
        self.store_document(
            doc_id=doc_id,
            run_id=run_id,
            doc_type=f"stage_{stage}_{agent_name}",
            content=content,
            ticker=ticker,
            title=f"Stage {stage} — {agent_name}",
            metadata={"stage": stage, "agent": agent_name},
        )

    def store_report(self, run_id: str, report_text: str, title: str = "") -> None:
        """Store a final report."""
        doc_id = f"{run_id}-report"
        self.store_document(
            doc_id=doc_id,
            run_id=run_id,
            doc_type="final_report",
            content=report_text,
            title=title or f"Report {run_id}",
        )

    def store_claim_ledger(
        self, run_id: str, claims: list[dict[str, Any]]
    ) -> None:
        """Store a claim ledger for future reference."""
        doc_id = f"{run_id}-claims"
        content = json.dumps(claims, indent=2, default=str)
        self.store_document(
            doc_id=doc_id,
            run_id=run_id,
            doc_type="claim_ledger",
            content=content,
            title=f"Claims {run_id}",
        )

    # ── Search ────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        doc_type: str | None = None,
        ticker: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search across the research corpus.

        Args:
            query: Search query (FTS5 syntax supported)
            doc_type: Filter by document type
            ticker: Filter by ticker
            limit: Max results
        """
        conn = self._get_conn()

        # Build FTS query
        where_clauses = ["documents_fts MATCH ?"]
        params: list[Any] = [query]

        if doc_type:
            where_clauses.append("doc_type = ?")
            params.append(doc_type)
        if ticker:
            where_clauses.append("ticker = ?")
            params.append(ticker)

        params.append(limit)
        where = " AND ".join(where_clauses)

        sql = f"""
            SELECT doc_id, run_id, doc_type, ticker, title,
                   snippet(documents_fts, 5, '<b>', '</b>', '...', 64) as snippet,
                   rank
            FROM documents_fts
            WHERE {where}
            ORDER BY rank
            LIMIT ?
        """

        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError as e:
            logger.warning("FTS search failed: %s", e)
            return []

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a specific document by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_run_documents(self, run_id: str) -> list[dict[str, Any]]:
        """Get all documents for a specific run."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT doc_id, doc_type, ticker, title, created_at FROM documents WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_ticker_history(self, ticker: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get all documents mentioning a specific ticker."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT doc_id, run_id, doc_type, title, created_at
               FROM documents WHERE ticker = ? ORDER BY created_at DESC LIMIT ?""",
            (ticker, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── Thesis History ────────────────────────────────────────────────
    def store_thesis(
        self,
        thesis_id: str,
        run_id: str,
        ticker: str,
        thesis_text: str,
        status: str = "active",
        score: float = 0.0,
    ) -> None:
        """Store a thesis snapshot."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT OR REPLACE INTO thesis_history
               (thesis_id, run_id, ticker, thesis_text, status, score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (thesis_id, run_id, ticker, thesis_text, status, score, now),
        )
        conn.commit()

    def get_thesis_evolution(self, thesis_id: str) -> list[dict[str, Any]]:
        """Get the history of a thesis across runs."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM thesis_history
               WHERE thesis_id = ? ORDER BY created_at""",
            (thesis_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_ticker_theses(self, ticker: str) -> list[dict[str, Any]]:
        """Get all theses for a ticker across all runs."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM thesis_history
               WHERE ticker = ? ORDER BY created_at DESC""",
            (ticker,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── E-9: Cross-run trend detection ────────────────────────────────
    def store_run_metrics(
        self,
        run_id: str,
        metrics: dict[str, Any],
    ) -> None:
        """Store numeric metrics for cross-run comparison.

        Args:
            run_id: Pipeline run ID
            metrics: dict of {metric_key: value} e.g. {"NVDA_dcf_fair_value": 950.0, "var_95_pct": 1.23}
        """
        content = json.dumps(metrics, default=str)
        self.store_document(
            doc_id=f"{run_id}-metrics",
            run_id=run_id,
            doc_type="run_metrics",
            content=content,
            title=f"Metrics {run_id}",
            metadata={"metric_count": len(metrics)},
        )

    def detect_trends(
        self,
        current_run_id: str,
        current_metrics: dict[str, float],
        alert_threshold_pct: float = 10.0,
        n_prior_runs: int = 3,
    ) -> list[dict[str, Any]]:
        """E-9: Compare current run metrics against prior run averages.

        Flags when DCF fair value, VaR, or ESG scores change >threshold%.

        Returns list of ResearchTrend dicts.
        """
        # Fetch prior run metrics
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT run_id, content FROM documents
               WHERE doc_type = 'run_metrics' AND run_id != ?
               ORDER BY created_at DESC LIMIT ?""",
            (current_run_id, n_prior_runs),
        ).fetchall()

        if not rows:
            return []

        # Average prior metrics
        prior_metrics: dict[str, list[float]] = {}
        for row in rows:
            try:
                m = json.loads(row["content"])
                for k, v in m.items():
                    if isinstance(v, (int, float)):
                        prior_metrics.setdefault(k, []).append(float(v))
            except (json.JSONDecodeError, TypeError):
                continue

        if not prior_metrics:
            return []

        trends: list[dict[str, Any]] = []
        for metric, current_val in current_metrics.items():
            if metric not in prior_metrics:
                continue
            prior_vals = prior_metrics[metric]
            prior_avg = sum(prior_vals) / len(prior_vals)
            if prior_avg == 0:
                continue
            delta_pct = (current_val - prior_avg) / abs(prior_avg) * 100

            if abs(delta_pct) >= alert_threshold_pct:
                # Parse ticker from metric key e.g. "NVDA_dcf_fair_value"
                parts = metric.split("_", 1)
                ticker = parts[0] if len(parts) > 1 else ""
                metric_name = parts[1] if len(parts) > 1 else metric

                alert_level = "high" if abs(delta_pct) >= alert_threshold_pct * 2 else "medium"
                trends.append({
                    "ticker": ticker,
                    "metric": metric_name,
                    "current_value": round(current_val, 4),
                    "prior_value": round(prior_avg, 4),
                    "delta_pct": round(delta_pct, 2),
                    "alert_level": alert_level,
                    "n_prior_runs": len(prior_vals),
                })

        return sorted(trends, key=lambda x: abs(x["delta_pct"]), reverse=True)

    # ── Statistics ────────────────────────────────────────────────────
    @property
    def stats(self) -> dict[str, int]:
        """Corpus statistics."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        types = conn.execute(
            "SELECT doc_type, COUNT(*) as cnt FROM documents GROUP BY doc_type"
        ).fetchall()
        theses = conn.execute("SELECT COUNT(*) FROM thesis_history").fetchone()[0]
        return {
            "total_documents": total,
            "total_theses": theses,
            "by_type": {row["doc_type"]: row["cnt"] for row in types},
        }
