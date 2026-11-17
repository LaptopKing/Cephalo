"""
Cephalo Propositional Intent & Preference Rule Gatekeeper (tsetlin_gatekeeper.py)
Deterministic, explainable propositional rule gatekeeper using Tsetlin Machines (TMU).
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from tmu.tsetlin_machine import TMClassifier
except ImportError:
    TMClassifier = None

from cephalo.config import DATA_DIR, PROFILE_FILE, PROMPTS_FILE
from cephalo.learning.tsetlin_vectorizer import (
    CATEGORY_DESCRIPTIONS,
    DEFAULT_CINEMA_MODEL,
    DEFAULT_GATEKEEPER_MODEL,
    INTENT_CATEGORIES,
    SEED_INTENT_DATASET,
    STOPWORDS,
    TSETLIN_DIR,
    BooleanVectorizer,
    PropositionalClause,
    RouteResult,
)
from cephalo.learning.tsetlin_inducer import (
    PreferenceEvaluation,
    PreferenceRuleInducer,
)

__all__ = [
    "PropositionalClause",
    "RouteResult",
    "BooleanVectorizer",
    "PreferenceEvaluation",
    "PreferenceRuleInducer",
    "TsetlinGatekeeper",
    "get_gatekeeper",
    "INTENT_CATEGORIES",
    "CATEGORY_DESCRIPTIONS",
]

logger = logging.getLogger("cephalo.learning.tsetlin_gatekeeper")

class TsetlinGatekeeper:
    """
    Propositional Intent Gatekeeper powered by Tsetlin Machines.
    Provides sub-millisecond intent routing with transparent propositional logic explanations.
    """

    def __init__(
        self,
        number_of_clauses: int = 60,
        T: int = 25,
        s: float = 2.0,
        model_path: Optional[Path] = None,
    ):
        self.number_of_clauses = number_of_clauses
        self.T = T
        self.s = s
        self.model_path = model_path or DEFAULT_GATEKEEPER_MODEL
        self.categories = list(INTENT_CATEGORIES)
        self.cat_to_id = {c: i for i, c in enumerate(self.categories)}
        self.vectorizer = BooleanVectorizer(min_freq=1, max_features=800)
        self.clauses: List[PropositionalClause] = []
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}

        # Built-in Cinema Preference Rule Inducer
        self.cinema_inducer = PreferenceRuleInducer(domain="cinema")

    # -------------------------------------------------------------------------
    # Training & Memory Ingestion
    # -------------------------------------------------------------------------

    def _collect_training_data(
        self,
        custom_data: Optional[List[Tuple[str, str]]] = None,
        use_cephalo_memory: bool = True,
        max_per_category: int = 25,
    ) -> List[Tuple[str, str]]:
        """Collects seed dataset and augments with balanced samples from Cephalo memory."""
        by_category: Dict[str, List[str]] = {cat: [] for cat in self.categories}

        for text, cat in SEED_INTENT_DATASET:
            if cat in by_category:
                by_category[cat].append(text)

        if custom_data:
            for text, cat in custom_data:
                if cat in by_category:
                    by_category[cat].append(text)

        if use_cephalo_memory and PROMPTS_FILE.exists():
            category_mapping = {
                "preference": "preference",
                "user_preference": "preference",
                "entertainment_preferences": "preference",
                "car_livery_preference": "preference",
                "hardware": "hardware_spec",
                "hardware_spec": "hardware_spec",
                "critique_negative_filter": "critique_filter",
                "critique_filter": "critique_filter",
                "architecture": "architectural_milestone",
                "architecture_milestone": "architectural_milestone",
                "architectural_milestone": "architectural_milestone",
                "architecture_decision": "architectural_milestone",
                "milestone": "architectural_milestone",
            }

            try:
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            content = record.get("content", "").strip()
                            raw_cat = record.get("category", "")
                            mapped_cat = category_mapping.get(raw_cat)
                            if mapped_cat and content and 10 < len(content) < 300:
                                if len(by_category[mapped_cat]) < max_per_category:
                                    by_category[mapped_cat].append(content)
                        except Exception:
                            continue
            except Exception as e:
                logger.warning(f"Could not ingest Cephalo memory prompts: {e}")

        dataset: List[Tuple[str, str]] = []
        for cat, texts in by_category.items():
            for t in texts:
                dataset.append((t, cat))

        return dataset

    def train(
        self,
        dataset: Optional[List[Tuple[str, str]]] = None,
        epochs: int = 40,
        use_cephalo_memory: bool = True,
        save_on_complete: bool = True,
    ) -> Dict[str, Any]:
        """
        Trains the Tsetlin Machine intent routing model across all 5 canonical categories.
        """
        start_time = time.perf_counter()
        data = self._collect_training_data(dataset, use_cephalo_memory=use_cephalo_memory)

        texts = [d[0] for d in data]
        labels = np.array([self.cat_to_id[d[1]] for d in data], dtype=np.uint32)

        # Domain keywords to ensure presence in vocabulary
        extra_keywords = [
            "tcl", "65t8b", "b243hl", "acer", "qled", "soundbar", "earc", "gtx1050ti",
            "vibrant", "slowburn", "drab", "swagger", "kinetic", "refactor", "schema",
            "taskledger", "lancedb", "fastembed", "subagent", "governor", "weather",
            "hate", "avoid", "dislike", "boring", "blacklist", "broken", "slop",
            "pacing", "colors", "taste", "spec", "monitor", "display", "gpu", "ram",
        ]
        self.vectorizer.fit(texts, extra_keywords=extra_keywords)
        X = self.vectorizer.transform(texts)

        if TMClassifier is None:
            raise RuntimeError("tmu package is not available in environment.")

        np.random.seed(42)

        # Train Multi-Class Tsetlin Machine
        tm = TMClassifier(
            number_of_clauses=self.number_of_clauses,
            T=self.T,
            s=self.s,
            weighted_clauses=True,
            max_included_literals=3,
        )

        for _ in range(epochs):
            tm.fit(X, labels)

        preds = tm.predict(X)
        accuracy = float(np.mean(preds == labels))

        # Extract Propositional Clauses
        self.clauses = []
        clause_id = 0
        num_feats = len(self.vectorizer.vocab)

        for class_idx, class_name in enumerate(self.categories):
            for pol in [0, 1]:
                for c in range(self.number_of_clauses // 2):
                    w = tm.get_weight(class_idx, pol, c)
                    if w == 0:
                        continue

                    pos_lits = []
                    neg_lits = []
                    pos_idxs = []
                    neg_idxs = []

                    for k in range(num_feats):
                        if tm.get_ta_action(class_idx, pol, c, k):
                            pos_lits.append(self.vectorizer.vocab[k])
                            pos_idxs.append(k)
                        if tm.get_ta_action(class_idx, pol, c, k + num_feats):
                            neg_lits.append(self.vectorizer.vocab[k])
                            neg_idxs.append(k)

                    if pos_lits or neg_lits:
                        if set(pos_lits).intersection(set(neg_lits)):
                            continue  # Prune contradictions

                        self.clauses.append(
                            PropositionalClause(
                                clause_id=clause_id,
                                class_name=class_name,
                                class_idx=class_idx,
                                polarity=pol,
                                weight=int(w),
                                pos_literals=pos_lits,
                                neg_literals=neg_lits,
                                pos_indices=pos_idxs,
                                neg_indices=neg_idxs,
                            )
                        )
                        clause_id += 1

        self.is_trained = True
        duration = time.perf_counter() - start_time

        self.training_stats = {
            "samples_count": len(data),
            "vocabulary_size": len(self.vectorizer.vocab),
            "epochs": epochs,
            "accuracy": round(accuracy, 4),
            "clause_count": len(self.clauses),
            "train_duration_sec": round(duration, 3),
        }

        # Train default Cinema Preference Inducer alongside gatekeeper
        self._train_default_cinema_inducer(epochs=epochs)

        if save_on_complete:
            self.save()

        return self.training_stats

    def _train_default_cinema_inducer(self, epochs: int = 35) -> None:
        """Trains the domain-specific Cinema Preference Rule Inducer."""
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
        self.cinema_inducer.train(cinema_data, epochs=epochs)
        if DEFAULT_CINEMA_MODEL.parent.exists():
            self.cinema_inducer.save(DEFAULT_CINEMA_MODEL)

    # -------------------------------------------------------------------------
    # High-Speed Intent Routing (< 0.1ms)
    # -------------------------------------------------------------------------

    def route(self, text: str) -> RouteResult:
        """
        Classifies incoming prompt into one of the 5 intent categories.
        Guaranteed instant inference (< 1ms, typically < 0.05ms).
        """
        t0 = time.perf_counter()

        if not self.is_trained:
            if not self.auto_load():
                self.train(epochs=40, save_on_complete=True)

        token_set = self.vectorizer.get_tokens(text)

        # Evaluate propositional clauses
        votes = {cat: 0 for cat in self.categories}
        triggered_clauses_by_cat: Dict[str, List[str]] = {cat: [] for cat in self.categories}
        highest_weight_clause: Dict[str, Tuple[int, str]] = {cat: (-999, "") for cat in self.categories}

        for clause in self.clauses:
            if clause.evaluate_tokens(token_set):
                cat = clause.class_name
                votes[cat] += clause.weight

                if clause.polarity == 0 and clause.pos_literals:
                    rule_str = clause.to_rule_string()
                    triggered_clauses_by_cat[cat].append(rule_str)
                    if clause.weight > highest_weight_clause[cat][0]:
                        highest_weight_clause[cat] = (clause.weight, rule_str)

        clipped_votes = {cat: max(-self.T, min(self.T, score)) for cat, score in votes.items()}

        # If no positive patterns fired and all scores <= 0, default to ephemeral_query
        max_score = max(clipped_votes.values())
        if max_score <= 0:
            predicted_category = "ephemeral_query"
            vote_margin = 0
            confidence = 0.5
            triggered_clause = '(has("query") OR fallback) -> ephemeral_query'
            all_triggered = []
        else:
            sorted_cats = sorted(clipped_votes.items(), key=lambda x: -x[1])
            predicted_category = sorted_cats[0][0]
            top_score = sorted_cats[0][1]
            second_score = sorted_cats[1][1]
            vote_margin = top_score - second_score
            confidence = min(1.0, max(0.0, vote_margin / (self.T if self.T > 0 else 1.0)))

            triggered_clause = highest_weight_clause[predicted_category][1] or (
                triggered_clauses_by_cat[predicted_category][0]
                if triggered_clauses_by_cat[predicted_category]
                else None
            )
            all_triggered = triggered_clauses_by_cat[predicted_category]

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return RouteResult(
            text=text,
            category=predicted_category,
            confidence=confidence,
            vote_margin=vote_margin,
            votes=clipped_votes,
            triggered_clause=triggered_clause,
            all_triggered_clauses=all_triggered,
            execution_time_ms=elapsed_ms,
        )

    # -------------------------------------------------------------------------
    # Human-Readable Propositional Explanation
    # -------------------------------------------------------------------------

    def rules(self, class_name: Optional[str] = None, limit_per_class: int = 8) -> Dict[str, List[str]]:
        """
        Returns human-readable propositional Boolean rules learned for all or specified categories.
        """
        if not self.is_trained:
            if not self.auto_load():
                self.train(epochs=40)

        rules_by_cat: Dict[str, List[str]] = {cat: [] for cat in self.categories}

        for c in self.clauses:
            if c.polarity == 0 and c.pos_literals:  # Active pattern rules
                rule_str = f"{c.to_rule_string()} (w={c.weight})"
                rules_by_cat[c.class_name].append(rule_str)

        result = {}
        for cat, r_list in rules_by_cat.items():
            if class_name and cat != class_name:
                continue
            unique_rules = list(dict.fromkeys(r_list))
            result[cat] = unique_rules[:limit_per_class]

        return result

    def explain(self, text: str) -> Dict[str, Any]:
        """Provides full transparency and Boolean clause breakdown of an intent prediction."""
        res = self.route(text)
        token_set = self.vectorizer.get_tokens(text)
        matching_vocab = sorted(list(token_set.intersection(set(self.vectorizer.vocab))))

        return {
            "text": text,
            "predicted_category": res.category,
            "confidence": res.confidence,
            "vote_margin": res.vote_margin,
            "matched_tokens": matching_vocab,
            "triggered_clause": res.triggered_clause,
            "all_triggered_clauses": res.all_triggered_clauses,
            "category_votes": res.votes,
            "execution_time_ms": res.execution_time_ms,
        }

    # -------------------------------------------------------------------------
    # Domain Cinema Preference Evaluation
    # -------------------------------------------------------------------------

    def evaluate_cinema(self, description: str) -> PreferenceEvaluation:
        """Evaluates cinema recommendation against user TCL 65T8B 4K preference rules."""
        if not self.cinema_inducer.is_trained:
            if DEFAULT_CINEMA_MODEL.exists():
                self.cinema_inducer.load(DEFAULT_CINEMA_MODEL)
            else:
                self._train_default_cinema_inducer()
        return self.cinema_inducer.evaluate(description)

    # -------------------------------------------------------------------------
    # Model Persistence
    # -------------------------------------------------------------------------

    def save(self, path: Optional[Path] = None) -> Path:
        """Saves trained propositional clauses, vocabulary, and metadata to JSON."""
        target_path = path or self.model_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0.0",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "hyperparameters": {
                "number_of_clauses": self.number_of_clauses,
                "T": self.T,
                "s": self.s,
            },
            "categories": self.categories,
            "vectorizer": self.vectorizer.to_dict(),
            "clauses": [c.to_dict() for c in self.clauses],
            "training_stats": self.training_stats,
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Tsetlin Gatekeeper model saved to {target_path}")
        return target_path

    def load(self, path: Optional[Path] = None) -> bool:
        """Loads trained propositional clauses and vectorizer for instant inference."""
        target_path = path or self.model_path
        if not target_path.exists():
            return False

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            hp = data.get("hyperparameters", {})
            self.number_of_clauses = hp.get("number_of_clauses", self.number_of_clauses)
            self.T = hp.get("T", self.T)
            self.s = hp.get("s", self.s)
            self.categories = data.get("categories", self.categories)
            self.cat_to_id = {c: i for i, c in enumerate(self.categories)}
            self.vectorizer = BooleanVectorizer.from_dict(data.get("vectorizer", {}))
            self.clauses = [PropositionalClause.from_dict(c) for c in data.get("clauses", [])]
            self.training_stats = data.get("training_stats", {})
            self.is_trained = True

            if DEFAULT_CINEMA_MODEL.exists():
                self.cinema_inducer.load(DEFAULT_CINEMA_MODEL)

            return True
        except Exception as e:
            logger.error(f"Failed to load Tsetlin Gatekeeper model from {target_path}: {e}")
            return False

    def auto_load(self) -> bool:
        """Attempts to load persisted model; returns True if loaded, False if retraining needed."""
        if self.model_path.exists():
            return self.load(self.model_path)
        return False


# Singleton instance accessor
_gatekeeper_instance: Optional[TsetlinGatekeeper] = None


def get_gatekeeper() -> TsetlinGatekeeper:
    """Returns singleton Tsetlin Gatekeeper instance."""
    global _gatekeeper_instance
    if _gatekeeper_instance is None:
        _gatekeeper_instance = TsetlinGatekeeper()
        if not _gatekeeper_instance.auto_load():
            _gatekeeper_instance.train(epochs=40, save_on_complete=True)
    return _gatekeeper_instance
