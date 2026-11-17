"""
Cephalo Preference Rule Inducer using Tsetlin Machines.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from tmu.tsetlin_machine import TMClassifier
except ImportError:
    TMClassifier = None

from cephalo.config import DATA_DIR, PROFILE_FILE, PROMPTS_FILE
from cephalo.learning.tsetlin_vectorizer import (
    DEFAULT_CINEMA_MODEL,
    BooleanVectorizer,
    PropositionalClause,
)

logger = logging.getLogger("cephalo.learning.tsetlin_inducer")

@dataclass
class PreferenceEvaluation:
    """Evaluation result for preference acceptance or rejection."""

    item: str
    verdict: str  # "ACCEPT" or "REJECT"
    confidence: float
    score: int
    triggered_rule: Optional[str]
    all_rules: List[str]
    domain: str = "cinema"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "score": self.score,
            "triggered_rule": self.triggered_rule,
            "all_rules": self.all_rules,
            "domain": self.domain,
        }


class PreferenceRuleInducer:
    """
    Induces Boolean Propositional Rules from user preference and critique history
    using a binary Tsetlin Machine.
    """

    def __init__(
        self,
        domain: str = "cinema",
        number_of_clauses: int = 16,
        T: int = 12,
        s: float = 2.0,
    ):
        self.domain = domain
        self.number_of_clauses = number_of_clauses
        self.T = T
        self.s = s
        self.vectorizer = BooleanVectorizer(min_freq=1, max_features=300)
        self.clauses: List[PropositionalClause] = []
        self.is_trained = False

    def train(
        self,
        examples: List[Tuple[str, int]],
        epochs: int = 35,
    ) -> Dict[str, Any]:
        """
        Trains Tsetlin Machine on binary preference labels (1 = ACCEPT, 0 = REJECT).
        """
        texts = [ex[0] for ex in examples]
        labels = np.array([ex[1] for ex in examples], dtype=np.uint32)

        self.vectorizer.fit(texts)
        X = self.vectorizer.transform(texts)

        if TMClassifier is None:
            raise RuntimeError("tmu is not installed in the environment.")

        np.random.seed(42)

        tm = TMClassifier(
            number_of_clauses=self.number_of_clauses,
            T=self.T,
            s=self.s,
            weighted_clauses=True,
            max_included_literals=4,
        )

        for _ in range(epochs):
            tm.fit(X, labels)

        preds = tm.predict(X)
        accuracy = float(np.mean(preds == labels))

        # Extract propositional clauses
        self.clauses = []
        clause_id = 0
        classes = ["REJECT", "ACCEPT"]

        for class_idx, class_name in enumerate(classes):
            for pol in [0, 1]:
                for c in range(self.number_of_clauses // 2):
                    w = tm.get_weight(class_idx, pol, c)
                    if w == 0:
                        continue

                    pos_lits = []
                    neg_lits = []
                    pos_idxs = []
                    neg_idxs = []

                    num_feats = len(self.vectorizer.vocab)
                    for k in range(num_feats):
                        if tm.get_ta_action(class_idx, pol, c, k):
                            pos_lits.append(self.vectorizer.vocab[k])
                            pos_idxs.append(k)
                        if tm.get_ta_action(class_idx, pol, c, k + num_feats):
                            neg_lits.append(self.vectorizer.vocab[k])
                            neg_idxs.append(k)

                    if pos_lits or neg_lits:
                        if set(pos_lits).intersection(set(neg_lits)):
                            continue

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
        return {
            "domain": self.domain,
            "sample_count": len(examples),
            "accuracy": accuracy,
            "clause_count": len(self.clauses),
        }

    def evaluate(self, item: str) -> PreferenceEvaluation:
        """Evaluates an item against learned Boolean preference clauses."""
        if not self.is_trained:
            raise RuntimeError("PreferenceRuleInducer is not trained or loaded.")

        token_set = self.vectorizer.get_tokens(item)

        scores = {"REJECT": 0, "ACCEPT": 0}
        triggered_rules: Dict[str, List[str]] = {"REJECT": [], "ACCEPT": []}
        highest_weight_rule: Dict[str, Tuple[int, str]] = {"REJECT": (-999, ""), "ACCEPT": (-999, "")}

        for clause in self.clauses:
            if clause.evaluate_tokens(token_set):
                rule_str = clause.to_rule_string()
                target = clause.class_name
                scores[target] += clause.weight

                if clause.polarity == 0:
                    triggered_rules[target].append(rule_str)
                    if clause.weight > highest_weight_rule[target][0]:
                        highest_weight_rule[target] = (clause.weight, rule_str)
                elif clause.polarity == 1:
                    # In 2-class setup, negative vote against target (pol=1) reinforces the opposite verdict
                    opposing = "ACCEPT" if target == "REJECT" else "REJECT"
                    opposing_rule_str = rule_str.replace(f"-> NOT {target}", f"-> {opposing}")
                    triggered_rules[opposing].append(opposing_rule_str)
                    abs_w = abs(clause.weight)
                    if abs_w > highest_weight_rule[opposing][0]:
                        highest_weight_rule[opposing] = (abs_w, opposing_rule_str)

        score_accept = max(-self.T, min(self.T, scores["ACCEPT"]))
        score_reject = max(-self.T, min(self.T, scores["REJECT"]))

        verdict = "ACCEPT" if score_accept >= score_reject else "REJECT"
        winning_score = score_accept if verdict == "ACCEPT" else score_reject
        losing_score = score_reject if verdict == "ACCEPT" else score_accept
        margin = winning_score - losing_score
        confidence = min(1.0, max(0.0, margin / (self.T if self.T > 0 else 1.0)))

        triggered_rule = highest_weight_rule[verdict][1] or (
            triggered_rules[verdict][0] if triggered_rules[verdict] else None
        )

        return PreferenceEvaluation(
            item=item,
            verdict=verdict,
            confidence=round(confidence, 4),
            score=winning_score,
            triggered_rule=triggered_rule,
            all_rules=triggered_rules[verdict],
            domain=self.domain,
        )

    def get_rules(self) -> Dict[str, List[str]]:
        """Returns all induced propositional rules grouped by ACCEPT / REJECT."""
        rules: Dict[str, List[str]] = {"ACCEPT": [], "REJECT": []}
        for c in self.clauses:
            if c.polarity == 0 and c.pos_literals:
                rules[c.class_name].append(c.to_rule_string())
        return rules

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "domain": self.domain,
            "number_of_clauses": self.number_of_clauses,
            "T": self.T,
            "s": self.s,
            "vectorizer": self.vectorizer.to_dict(),
            "clauses": [c.to_dict() for c in self.clauses],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: Path) -> bool:
        if not path.exists():
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.domain = data.get("domain", self.domain)
        self.number_of_clauses = data.get("number_of_clauses", self.number_of_clauses)
        self.T = data.get("T", self.T)
        self.s = data.get("s", self.s)
        self.vectorizer = BooleanVectorizer.from_dict(data.get("vectorizer", {}))
        self.clauses = [PropositionalClause.from_dict(c) for c in data.get("clauses", [])]
        self.is_trained = True
        return True


# =============================================================================
# Tsetlin Machine Intent Gatekeeper
# =============================================================================

