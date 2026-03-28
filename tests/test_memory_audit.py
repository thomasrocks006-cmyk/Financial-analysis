"""Tests for research memory and audit exporter services."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from research_pipeline.services.research_memory import ResearchMemory
from research_pipeline.services.audit_exporter import AuditExporter
from research_pipeline.schemas.governance import (
    AuditTrail,
    CommitteeMember,
    CommitteeRecord,
    CommitteeVote,
    CommitteeVoteRecord,
    MandateCheckResult,
)


# ── Research Memory ────────────────────────────────────────────────────────


class TestResearchMemory:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db_path = self.tmpdir / "test_memory.db"
        self.memory = ResearchMemory(db_path=self.db_path)

    def teardown_method(self):
        self.memory.close()

    def test_store_and_retrieve_document(self):
        self.memory.store_document(
            doc_id="DOC-001",
            run_id="RUN-001",
            doc_type="sector_report",
            content="NVIDIA dominates the GPU market with 80% share",
            ticker="NVDA",
            title="NVDA Sector Analysis",
        )
        doc = self.memory.get_document("DOC-001")
        assert doc is not None
        assert doc["ticker"] == "NVDA"

    def test_search_returns_results(self):
        self.memory.store_document(
            doc_id="DOC-001",
            run_id="RUN-001",
            doc_type="sector_report",
            content="NVIDIA dominates the GPU market with 80% data center share",
            ticker="NVDA",
        )
        results = self.memory.search("GPU market")
        assert len(results) >= 1

    def test_search_by_ticker(self):
        self.memory.store_document(
            doc_id="DOC-001", run_id="RUN-001", doc_type="report",
            content="NVDA analysis content", ticker="NVDA",
        )
        self.memory.store_document(
            doc_id="DOC-002", run_id="RUN-001", doc_type="report",
            content="AVGO analysis content", ticker="AVGO",
        )
        results = self.memory.search("analysis", ticker="NVDA")
        assert all(r.get("ticker") == "NVDA" for r in results)

    def test_get_run_documents(self):
        self.memory.store_document(
            doc_id="DOC-001", run_id="RUN-001", doc_type="report",
            content="Report content",
        )
        self.memory.store_document(
            doc_id="DOC-002", run_id="RUN-001", doc_type="claims",
            content="Claims content",
        )
        docs = self.memory.get_run_documents("RUN-001")
        assert len(docs) == 2

    def test_store_run_output(self):
        self.memory.store_run_output(
            run_id="RUN-001",
            stage=3,
            agent_name="sector_compute",
            output={"analysis": "compute sector is strong"},
            ticker="NVDA",
        )
        doc = self.memory.get_document("RUN-001-stage3-sector_compute")
        assert doc is not None

    def test_thesis_history(self):
        self.memory.store_thesis(
            thesis_id="TH-001",
            run_id="RUN-001",
            ticker="NVDA",
            thesis_text="Data center growth thesis",
        )
        self.memory.store_thesis(
            thesis_id="TH-001",
            run_id="RUN-002",
            ticker="NVDA",
            thesis_text="Data center growth thesis - confirmed by Q4 earnings",
            status="confirmed",
        )
        history = self.memory.get_thesis_evolution("TH-001")
        assert len(history) == 2
        assert history[0]["status"] == "active"
        assert history[1]["status"] == "confirmed"

    def test_ticker_theses(self):
        self.memory.store_thesis("TH-001", "RUN-001", "NVDA", "Thesis A")
        self.memory.store_thesis("TH-002", "RUN-001", "NVDA", "Thesis B")
        theses = self.memory.get_ticker_theses("NVDA")
        assert len(theses) == 2

    def test_stats(self):
        self.memory.store_document("D1", "R1", "report", "content1")
        self.memory.store_document("D2", "R1", "claims", "content2")
        self.memory.store_thesis("TH-1", "R1", "NVDA", "thesis")
        stats = self.memory.stats
        assert stats["total_documents"] == 2
        assert stats["total_theses"] == 1


# ── Audit Exporter ─────────────────────────────────────────────────────────


class TestAuditExporter:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.exporter = AuditExporter(output_dir=self.tmpdir)

    def test_export_minimal_audit(self):
        path = self.exporter.export_full_audit(run_id="RUN-001")
        assert path.exists()
        assert path.suffix == ".json"

        import json
        data = json.loads(path.read_text())
        assert data["run_id"] == "RUN-001"
        assert "sections" in data

    def test_export_full_audit(self):
        # Create committee record
        member = CommitteeMember(member_id="IC-1", role="chair", name="Chair")
        vote = CommitteeVoteRecord(
            member=member, vote=CommitteeVote.APPROVE, rationale="Good"
        )
        committee = CommitteeRecord(
            record_id="IC-RUN-001",
            run_id="RUN-001",
            votes=[vote],
            outcome=CommitteeVote.APPROVE,
            quorum_met=True,
        )

        # Create audit trail
        trail = AuditTrail(run_id="RUN-001")
        trail.add_entry(action="gate_check", stage=5, outcome="pass")

        # Create mandate check
        mandate = MandateCheckResult(
            run_id="RUN-001", mandate_id="M-001", is_compliant=True
        )

        path = self.exporter.export_full_audit(
            run_id="RUN-001",
            audit_trail=trail,
            committee_record=committee,
            mandate_check=mandate,
            gate_results={"total_stages": 15, "completed_stages": 15, "failed_gates": []},
            risk_summary={"concentration_hhi": 1200},
        )

        import json
        data = json.loads(path.read_text())
        assert data["sections"]["committee_record"]["outcome"] == "approve"
        assert data["sections"]["mandate_compliance"]["is_compliant"] is True
        assert data["sections"]["compliance_summary"]["overall_status"] == "compliant"

    def test_export_non_compliant(self):
        committee = CommitteeRecord(
            record_id="IC-002",
            run_id="RUN-002",
            outcome=CommitteeVote.REJECT,
            quorum_met=True,
        )
        path = self.exporter.export_full_audit(
            run_id="RUN-002",
            committee_record=committee,
            gate_results={"total_stages": 15, "completed_stages": 10, "failed_gates": ["stage_5"]},
        )

        import json
        data = json.loads(path.read_text())
        assert data["sections"]["compliance_summary"]["overall_status"] == "non_compliant"

    def test_list_audits(self):
        self.exporter.export_full_audit("RUN-001")
        self.exporter.export_full_audit("RUN-002")
        audits = self.exporter.list_audits()
        assert len(audits) == 2

    def test_list_audits_filtered(self):
        self.exporter.export_full_audit("RUN-001")
        self.exporter.export_full_audit("RUN-002")
        audits = self.exporter.list_audits(run_id="RUN-001")
        assert len(audits) == 1
