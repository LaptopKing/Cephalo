"""
Tests for Cephalo Tsetlin Machine Propositional Intent & Preference Rule Gatekeeper
==================================================================================
Verifies:
1. BooleanVectorizer tokenization, stopword filtering, and binary matrix transformations.
2. TsetlinGatekeeper model training and high accuracy across 5 canonical intent classes.
3. High-speed intent routing (<1ms) across preference, hardware, critique, architecture, and query.
4. Human-readable propositional rule explanations and triggered Boolean clauses.
5. Model persistence (save/load) for zero-training instant inference.
6. Preference Rule Induction (Capability 2 & 3) for cinema recommendations (TCL 65T8B 4K).
7. Cephalo CLI gatekeeper & tsetlin subcommands.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

from cephalo.config import ROOT_DIR
from cephalo.learning.tsetlin_gatekeeper import (
    INTENT_CATEGORIES,
    BooleanVectorizer,
    PreferenceRuleInducer,
    PropositionalClause,
    RouteResult,
    TsetlinGatekeeper,
    get_gatekeeper,
)


# =============================================================================
# 1. Boolean Vectorizer Tests
# =============================================================================

class TestBooleanVectorizer:
    def test_tokenization_and_stopwords(self):
        text = "The quick brown fox jumps over the lazy dog and a slowburn movie"
        tokens = BooleanVectorizer.tokenize(text)
        # Verify grammatical stopwords ('the', 'and', 'a', 'over') are removed
        assert "the" not in tokens
        assert "and" not in tokens
        assert "a" not in tokens
        assert "slowburn" in tokens
        assert "movie" in tokens

    def test_domain_alphanumerics_preserved(self):
        text = "Living room TV TCL 65T8B 4K QLED Acer B243HL GTX 1050 Ti"
        tokens = BooleanVectorizer.tokenize(text)
        assert "tcl" in tokens
        assert "65t8b" in tokens
        assert "4k" in tokens
        assert "qled" in tokens
        assert "acer" in tokens
        assert "b243hl" in tokens

    def test_fit_transform_matrix(self):
        texts = [
            "TCL 65T8B 4K QLED television display",
            "Slowburn indie movie drab grey palette",
            "Refactor SQLite database schema ledger",
        ]
        vec = BooleanVectorizer(min_freq=1, max_features=100)
        vec.fit(texts)

        assert len(vec.vocab) > 5
        assert "tcl" in vec.vocab
        assert "slowburn" in vec.vocab
        assert "refactor" in vec.vocab

        matrix = vec.transform(texts)
        assert isinstance(matrix, np.ndarray)
        assert matrix.shape == (3, len(vec.vocab))
        assert matrix.dtype == np.uint32

        # Check binary presence
        tcl_idx = vec.word_to_id["tcl"]
        assert matrix[0, tcl_idx] == 1
        assert matrix[1, tcl_idx] == 0

    def test_vectorizer_serialization(self):
        vec = BooleanVectorizer(min_freq=1, max_features=50)
        vec.fit(["hello world python", "machine learning tsetlin"])
        d = vec.to_dict()

        restored = BooleanVectorizer.from_dict(d)
        assert restored.vocab == vec.vocab
        assert restored.word_to_id == vec.word_to_id


# =============================================================================
# 2. Gatekeeper Intent Routing & Explanations
# =============================================================================

class TestTsetlinGatekeeper:
    @pytest.fixture(scope="class")
    @classmethod
    def gatekeeper(cls):
        np.random.seed(42)
        gk = TsetlinGatekeeper(number_of_clauses=60, T=25, s=1.8)
        gk.train(epochs=50, save_on_complete=True)
        return gk

    def test_gatekeeper_is_trained(self, gatekeeper):
        assert gatekeeper.is_trained
        assert len(gatekeeper.clauses) > 50
        assert gatekeeper.training_stats.get("accuracy", 0) >= 0.80

    def test_routing_hardware_spec(self, gatekeeper):
        text = "Living room TV is TCL 65T8B 65-inch 4K QLED display"
        res = gatekeeper.route(text)
        assert res.category == "hardware_spec"
        assert res.confidence >= 0.50
        assert res.vote_margin > 0
        assert res.triggered_clause is not None
        assert "hardware_spec" in res.triggered_clause
        assert res.execution_time_ms < 1.0  # Must be sub-millisecond

    def test_routing_critique_filter(self, gatekeeper):
        text = "Snatch rejected for drab overcast grey palette and dull tones"
        res = gatekeeper.route(text)
        assert res.category == "critique_filter"
        assert res.confidence >= 0.50
        assert res.vote_margin > 0
        assert res.triggered_clause is not None
        assert "critique_filter" in res.triggered_clause
        assert res.execution_time_ms < 1.0

    def test_routing_preference(self, gatekeeper):
        text = "We prefer fast kinetic pacing with sharp suits and rhythmic banter"
        res = gatekeeper.route(text)
        assert res.category == "preference"
        assert res.triggered_clause is not None
        assert "preference" in res.triggered_clause
        assert res.execution_time_ms < 1.0

    def test_routing_architectural_milestone(self, gatekeeper):
        text = "Architecture decision: use TaskLedger SQLite database for subagent recovery"
        res = gatekeeper.route(text)
        assert res.category == "architectural_milestone"
        assert res.confidence >= 0.50
        assert res.vote_margin > 0
        assert res.triggered_clause is not None
        assert "architectural_milestone" in res.triggered_clause
        assert res.execution_time_ms < 1.0

    def test_routing_ephemeral_query(self, gatekeeper):
        text = "What time is it right now in Budapest Hungary?"
        res = gatekeeper.route(text)
        assert res.category == "ephemeral_query"
        assert res.vote_margin >= 0
        assert res.execution_time_ms < 1.0

    def test_sub_millisecond_inference_benchmark(self, gatekeeper):
        prompts = [
            "TCL 65T8B TV display",
            "I hate slowburn drab cinema, avoid it",
            "I prefer dark obsidian themes with python",
            "Refactor schema migration in LanceDB",
            "What is the weather in Berlin?",
        ]
        times = []
        for p in prompts:
            t0 = time.perf_counter()
            gatekeeper.route(p)
            times.append((time.perf_counter() - t0) * 1000.0)

        avg_time = sum(times) / len(times)
        # Verify average execution time is well under the 1.0ms requirement (< 0.5ms)
        assert avg_time < 0.5, f"Expected < 0.5ms, got {avg_time:.3f}ms"

    def test_propositional_rule_extraction(self, gatekeeper):
        all_rules = gatekeeper.rules()
        for cat in INTENT_CATEGORIES:
            assert cat in all_rules
            assert len(all_rules[cat]) > 0
            for r in all_rules[cat]:
                assert "->" in r
                assert f"-> {cat}" in r

    def test_explain_diagnostics(self, gatekeeper):
        diag = gatekeeper.explain("TCL 65T8B display connected via HDMI")
        assert diag["predicted_category"] == "hardware_spec"
        assert "tcl" in diag["matched_tokens"] or "display" in diag["matched_tokens"]
        assert diag["category_votes"]["hardware_spec"] > 0
        assert diag["triggered_clause"] is not None


# =============================================================================
# 3. Model Persistence Tests
# =============================================================================

class TestModelPersistence:
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_path = Path(tmp_dir) / "test_model.json"

            gk1 = TsetlinGatekeeper(model_path=model_path)
            stats1 = gk1.train(epochs=35, save_on_complete=True)
            assert model_path.exists()

            # Load into brand new instance
            gk2 = TsetlinGatekeeper(model_path=model_path)
            loaded = gk2.load(model_path)
            assert loaded
            assert gk2.is_trained
            assert len(gk2.clauses) == len(gk1.clauses)
            assert gk2.vectorizer.vocab == gk1.vectorizer.vocab

            # Test predictions match exactly
            test_prompt = "Living room TV is TCL 65T8B"
            res1 = gk1.route(test_prompt)
            res2 = gk2.route(test_prompt)

            assert res1.category == res2.category
            assert res1.confidence == res2.confidence
            assert res1.votes == res2.votes
            assert res1.triggered_clause == res2.triggered_clause


# =============================================================================
# 4. Preference Rule Induction (Capability 2 & 3)
# =============================================================================

class TestPreferenceRuleInduction:
    @pytest.fixture(scope="class")
    @classmethod
    def cinema_inducer(cls):
        inducer = PreferenceRuleInducer(domain="cinema", number_of_clauses=20, T=15, s=2.0)
        cinema_data = [
            # ACCEPT (1) - Vibrant 4K, instant narrative velocity, Guy Ritchie / David Leitch action-comedies
            ("vibrant 4k instant_velocity high_contrast action_comedy", 1),
            ("instant velocity 4k qled turquoise mediterranean sun", 1),
            ("guy ritchie the gentlemen sharp suits rhythmic banter action", 1),
            ("bullet train david leitch hyper-kinetic assassins neon nightscapes", 1),
            ("kingsman matthew vaughn high tempo glossy British swagger", 1),
            ("the ministry of ungentlemanly warfare vibrant 4k action", 1),
            ("the fall guy rapid tempo vibrant cinematography", 1),
            ("fast pacing instant cold open momentum vibrant saturation", 1),

            # REJECT (0) - Drab grey overcast, slow-burn 90s indie dramas, Snatch grey palette
            ("snatch drab overcast grey palette dull tones", 0),
            ("slowburn indie drama 45 minutes to start boring", 0),
            ("drab grey washed out colors muted indie", 0),
            ("slow pacing slowburn depressing overcast lighting", 0),
            ("boring slow narrative take 40 minutes unbundle", 0),
            ("drab 90s aesthetic grey dull cinematography", 0),
            ("slowburn contemplative arthouse drama quiet boring", 0),
            ("muted drab overcast palette slow pacing", 0),
        ]
        inducer.train(cinema_data, epochs=40)
        return inducer

    def test_accept_vibrant_4k_action(self, cinema_inducer):
        item = "A hyper-kinetic glossy action-comedy in vibrant 4K with sharp suits and instant velocity"
        res = cinema_inducer.evaluate(item)
        assert res.verdict == "ACCEPT"
        assert res.score > 0
        assert res.confidence > 0.5
        assert res.triggered_rule is not None
        assert "ACCEPT" in res.triggered_rule

    def test_reject_drab_slowburn_indie(self, cinema_inducer):
        item = "A slowburn indie drama with drab grey overcast tones and boring quiet dialogue"
        res = cinema_inducer.evaluate(item)
        assert res.verdict == "REJECT"
        assert res.score > 0
        assert res.confidence > 0.5
        assert res.triggered_rule is not None
        assert "REJECT" in res.triggered_rule

    def test_gatekeeper_cinema_evaluation_integration(self):
        gk = get_gatekeeper()
        res_accept = gk.evaluate_cinema("David Leitch directed vibrant 4K neon assassin movie with instant momentum")
        assert res_accept.verdict == "ACCEPT"
        assert res_accept.triggered_rule is not None

        res_reject = gk.evaluate_cinema("Snatch drab grey overcast indie film with slow pacing")
        assert res_reject.verdict == "REJECT"
        assert res_reject.triggered_rule is not None


# =============================================================================
# 5. CLI Commands Integration Tests
# =============================================================================

class TestCephaloCLIGatekeeper:
    def _run_cli(self, args_list: list[str]) -> subprocess.CompletedProcess:
        venv_python = ROOT_DIR / ".venv" / "bin" / "python"
        cmd = [str(venv_python), "-m", "cephalo.cli"] + args_list
        return subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def test_cli_gatekeeper_help(self):
        proc = self._run_cli(["gatekeeper", "--help"])
        assert proc.returncode == 0
        assert "route" in proc.stdout
        assert "rules" in proc.stdout
        assert "train" in proc.stdout
        assert "cinema" in proc.stdout

    def test_cli_gatekeeper_route_text(self):
        proc = self._run_cli(["gatekeeper", "route", "Living room TV is TCL 65T8B 65-inch 4K QLED"])
        assert proc.returncode == 0
        assert "hardware_spec" in proc.stdout
        assert "Triggered Rule:" in proc.stdout

    def test_cli_gatekeeper_route_json(self):
        proc = self._run_cli(["gatekeeper", "route", "Snatch rejected for drab overcast grey palette", "--json"])
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["category"] == "critique_filter"
        assert data["confidence"] > 0.5
        assert data["triggered_clause"] is not None
        assert data["execution_time_ms"] < 2.0

    def test_cli_gatekeeper_rules(self):
        proc = self._run_cli(["gatekeeper", "rules"])
        assert proc.returncode == 0
        assert "HARDWARE_SPEC" in proc.stdout
        assert "CRITIQUE_FILTER" in proc.stdout
        assert "PREFERENCE" in proc.stdout

    def test_cli_gatekeeper_cinema(self):
        proc = self._run_cli(["gatekeeper", "cinema", "Vibrant 4K action-comedy with sharp suits and instant velocity"])
        assert proc.returncode == 0
        assert "ACCEPT" in proc.stdout
        assert "Triggered Rule:" in proc.stdout

    def test_cli_tsetlin_alias(self):
        proc = self._run_cli(["tsetlin", "route", "Refactor SQLite database schema and task ledger"])
        assert proc.returncode == 0
        assert "architectural_milestone" in proc.stdout
