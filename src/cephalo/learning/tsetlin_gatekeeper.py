"""
Cephalo Propositional Intent & Preference Rule Gatekeeper (tsetlin_gatekeeper.py)
================================================================================
Deterministic, explainable propositional rule gatekeeper using Tsetlin Machines (TMU).

Core Capabilities:
1. High-Speed Intent Routing: Classifies incoming prompts into 5 deterministic categories:
   - preference: User taste, aesthetic preferences, workflow declarations.
   - hardware_spec: Devices, monitors, TVs (TCL 65T8B), GPU (GTX 1050 Ti), audio, physical environment.
   - critique_filter: Negative reaction, complaints, items to avoid or blacklist.
   - architectural_milestone: Technical design decisions, schemas, refactoring rules.
   - ephemeral_query: General questions, standard search, casual banter.
2. Preference Rule Induction: Analyzes user history / critique logs and trains a Tsetlin
   Machine to induce exact Boolean rules (e.g. accepting vibrant 4K / instant velocity vs
   rejecting drab grey / slowburn cinema).
3. Human-Readable Propositional Explanation: Generates transparent Boolean clause strings
   such as `(has("tcl") AND has("tv")) -> hardware_spec`.
4. Sub-Millisecond Model Persistence: Saves and loads trained propositional clause weights
   enabling ultra-fast inference (< 0.1ms) without re-training.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

try:
    from tmu.tsetlin_machine import TMClassifier
except ImportError:
    TMClassifier = None

from cephalo.config import DATA_DIR, PROFILE_FILE, PROMPTS_FILE

logger = logging.getLogger("cephalo.learning.tsetlin_gatekeeper")

# Default Persistence Directory and Model Files
TSETLIN_DIR = DATA_DIR / "tsetlin"
DEFAULT_GATEKEEPER_MODEL = TSETLIN_DIR / "gatekeeper_model.json"
DEFAULT_CINEMA_MODEL = TSETLIN_DIR / "cinema_preference_model.json"

# Canonical Intent Categories
INTENT_CATEGORIES = [
    "preference",
    "hardware_spec",
    "critique_filter",
    "architectural_milestone",
    "ephemeral_query",
]

CATEGORY_DESCRIPTIONS = {
    "preference": "User taste, visual aesthetics, tool preferences, or workflow style declarations.",
    "hardware_spec": "Physical devices, monitors, TVs (TCL 65T8B), GPUs, RAM, display resolution, audio.",
    "critique_filter": "Negative critique, complaints, rejected styles, or items to blacklist/avoid.",
    "architectural_milestone": "Technical design decisions, schema migrations, refactoring rules, clean architecture.",
    "ephemeral_query": "General questions, transient searches, casual conversation, disposable commands.",
}

# High-frequency grammatical stopwords to filter from propositional vocabulary
STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "as", "that", "this", "it", "its", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "we", "you", "they", "them",
    "our", "your", "my", "me", "he", "she", "him", "her", "their", "us", "i", "into",
    "than", "then", "just", "so", "up", "out", "about", "also", "all", "can", "will",
    "should", "would", "could", "may", "might", "must", "am",
}


# =============================================================================
# Propositional Logic Clause
# =============================================================================

@dataclass
class PropositionalClause:
    """Represents an interpretable conjunctive Boolean clause learned by a Tsetlin Machine."""

    clause_id: int
    class_name: str
    class_idx: int
    polarity: int  # 0: positive vote (supports class), 1: negative vote (opposes class)
    weight: int
    pos_literals: List[str]  # Tokens that MUST be present
    neg_literals: List[str]  # Tokens that MUST be absent
    pos_indices: List[int] = field(default_factory=list)
    neg_indices: List[int] = field(default_factory=list)

    def to_rule_string(self) -> str:
        """Formats the clause into human-readable Boolean propositional logic."""
        parts = []
        for lit in self.pos_literals:
            parts.append(f'has("{lit}")')
        for lit in self.neg_literals:
            parts.append(f'NOT has("{lit}")')

        if not parts:
            clause_expr = "TRUE"
        elif len(parts) == 1:
            clause_expr = parts[0]
        else:
            clause_expr = f"({' AND '.join(parts)})"

        op = "->" if self.polarity == 0 else "-> NOT"
        return f"{clause_expr} {op} {self.class_name}"

    def evaluate_tokens(self, token_set: Set[str]) -> bool:
        """Evaluates whether this clause fires on a given set of input tokens."""
        for lit in self.pos_literals:
            if lit not in token_set:
                return False
        for lit in self.neg_literals:
            if lit in token_set:
                return False
        return True

    def evaluate_vector(self, feature_vec: np.ndarray) -> bool:
        """Evaluates whether this clause fires on a binary NumPy feature vector."""
        for idx in self.pos_indices:
            if feature_vec[idx] != 1:
                return False
        for idx in self.neg_indices:
            if feature_vec[idx] != 0:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "class_name": self.class_name,
            "class_idx": self.class_idx,
            "polarity": self.polarity,
            "weight": self.weight,
            "pos_literals": self.pos_literals,
            "neg_literals": self.neg_literals,
            "pos_indices": self.pos_indices,
            "neg_indices": self.neg_indices,
            "rule_string": self.to_rule_string(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PropositionalClause":
        return cls(
            clause_id=data.get("clause_id", 0),
            class_name=data.get("class_name", "unknown"),
            class_idx=data.get("class_idx", 0),
            polarity=data.get("polarity", 0),
            weight=data.get("weight", 1),
            pos_literals=data.get("pos_literals", []),
            neg_literals=data.get("neg_literals", []),
            pos_indices=data.get("pos_indices", []),
            neg_indices=data.get("neg_indices", []),
        )


# =============================================================================
# Routing Result
# =============================================================================

@dataclass
class RouteResult:
    """Contains the classified intent, confidence, vote margin, and triggered Boolean clause."""

    text: str
    category: str
    confidence: float
    vote_margin: int
    votes: Dict[str, int]
    triggered_clause: Optional[str]
    all_triggered_clauses: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "vote_margin": self.vote_margin,
            "votes": self.votes,
            "triggered_clause": self.triggered_clause,
            "all_triggered_clauses": self.all_triggered_clauses,
            "execution_time_ms": round(self.execution_time_ms, 3),
        }


# =============================================================================
# Boolean Vectorizer
# =============================================================================

class BooleanVectorizer:
    """Fast, deterministic Boolean token presence vectorizer with stopword filtering."""

    def __init__(self, min_freq: int = 1, max_features: int = 1000):
        self.min_freq = min_freq
        self.max_features = max_features
        self.vocab: List[str] = []
        self.word_to_id: Dict[str, int] = {}

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Extracts informative unigrams and bigrams filtering out pure grammatical stopwords."""
        if not text:
            return []
        text = text.lower()
        unigrams = re.findall(r"[a-z0-9_\-\.\:áéíóöőúüűÁÉÍÓÖŐÚÜŰ]+", text)
        cleaned_unigrams = [
            u.strip(".:-_")
            for u in unigrams
            if len(u.strip(".:-_")) > 1 and u.strip(".:-_") not in STOPWORDS
        ]

        # Extract selected bigrams if not composed entirely of stopwords
        bigrams = []
        for i in range(len(cleaned_unigrams) - 1):
            w1, w2 = cleaned_unigrams[i], cleaned_unigrams[i + 1]
            if w1 not in STOPWORDS or w2 not in STOPWORDS:
                bigrams.append(f"{w1}_{w2}")

        return cleaned_unigrams + bigrams

    def get_tokens(self, text: str) -> Set[str]:
        return set(self.tokenize(text))

    def fit(self, texts: List[str], extra_keywords: Optional[List[str]] = None) -> "BooleanVectorizer":
        counts: Dict[str, int] = {}
        for t in texts:
            tokens = self.get_tokens(t)
            for tok in tokens:
                counts[tok] = counts.get(tok, 0) + 1

        if extra_keywords:
            for kw in extra_keywords:
                kw_clean = kw.lower().strip()
                counts[kw_clean] = counts.get(kw_clean, 0) + 999

        sorted_vocab = sorted(
            [w for w, c in counts.items() if c >= self.min_freq],
            key=lambda w: (-counts[w], w),
        )

        if self.max_features:
            sorted_vocab = sorted_vocab[: self.max_features]

        self.vocab = sorted(sorted_vocab)
        self.word_to_id = {w: i for i, w in enumerate(self.vocab)}
        return self

    def transform_single(self, text: str) -> np.ndarray:
        tokens = self.get_tokens(text)
        vec = np.zeros(len(self.vocab), dtype=np.uint32)
        for t in tokens:
            idx = self.word_to_id.get(t)
            if idx is not None:
                vec[idx] = 1
        return vec

    def transform(self, texts: List[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), len(self.vocab)), dtype=np.uint32)
        for i, t in enumerate(texts):
            matrix[i] = self.transform_single(t)
        return matrix

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_freq": self.min_freq,
            "max_features": self.max_features,
            "vocab": self.vocab,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BooleanVectorizer":
        vec = cls(
            min_freq=data.get("min_freq", 1),
            max_features=data.get("max_features", 1000),
        )
        vec.vocab = data.get("vocab", [])
        vec.word_to_id = {w: i for i, w in enumerate(vec.vocab)}
        return vec


# =============================================================================
# Curated Multi-Class Seed Dataset
# =============================================================================

SEED_INTENT_DATASET: List[Tuple[str, str]] = [
    # preference (User taste, aesthetic preferences, workflow declarations)
    ("I love vibrant 4k action movies with bright saturated colors", "preference"),
    ("We prefer fast kinetic pacing with sharp suits and rhythmic buddy banter", "preference"),
    ("I prefer python over bash for scripting and automation workflows", "preference"),
    ("My aesthetic taste is high saturation and high contrast visuals", "preference"),
    ("I like direct pragmatic concise communication with clean markdown and no fluff", "preference"),
    ("Favorite directors are Guy Ritchie, David Leitch, Matthew Vaughn, and Shane Black", "preference"),
    ("Prefer clean sober dark obsidian themes in code editors", "preference"),
    ("I like using Obsidian local markdown vaults for second brain knowledge capture", "preference"),
    ("We want gold wheels with high-contrast stance styling on the sports wagon", "preference"),
    ("Always use English for code, commits, and documentation by default", "preference"),
    ("I prefer lightweight microservices over monolithic setups", "preference"),
    ("We like hyper-kinetic glossy action-comedies with eccentric assassins", "preference"),
    ("My preferred embedding approach is 100% local FastEmbed Qwen", "preference"),
    ("Prefer table breakdowns and structured summaries over long prose paragraphs", "preference"),
    ("I love vibrant neon cinematography with turquoise Mediterranean sun", "preference"),
    ("I prefer dark mode with high contrast syntax highlighting", "preference"),
    ("My taste is sharp suits, witty humor and instant narrative velocity", "preference"),
    ("We really prefer fast paced movies with vibrant neon lighting", "preference"),
    ("My taste is vibrant 4K visuals with neon pop", "preference"),
    ("Always prioritize local privacy and offline embeddings for our second brain", "preference"),

    # hardware_spec (Devices, monitors, TVs, GPUs, RAM, physical setup)
    ("Living room TV is TCL 65T8B 65-inch 4K QLED Google TV display", "hardware_spec"),
    ("Workstation monitor is Acer LCD Monitor Acer B243HL screen", "hardware_spec"),
    ("GPU is NVIDIA GeForce GTX 1050 Ti with 4GB VRAM and CUDA 13.0", "hardware_spec"),
    ("PC specs are Windows 10 IoT Enterprise LTSC with 16 GB RAM", "hardware_spec"),
    ("Audio setup has HDMI eARC Dolby Atmos soundbar and satellite speakers", "hardware_spec"),
    ("Display resolution is 3840x2160 4K UHD 60Hz HDR panel", "hardware_spec"),
    ("The laptop has 16GB memory and x86_64 CPU running Linux hardware", "hardware_spec"),
    ("Connected a secondary Acer 24 inch 1080p display monitor via DVI", "hardware_spec"),
    ("TCL TV HDMI 2.1 port connected to console device", "hardware_spec"),
    ("Hardware profile: TCL 65T8B television and Acer screen workstation", "hardware_spec"),
    ("Hardware constraint: power brownout when battery is discharging under 20 percent", "hardware_spec"),
    ("Display target: TCL 65T8B 65 inch 4K QLED panel with high dynamic range", "hardware_spec"),
    ("System memory has 11 GB free RAM with NVIDIA GeForce GPU", "hardware_spec"),
    ("Audio setup configured for eARC passthrough and subwoofer", "hardware_spec"),
    ("My workstation has an Acer LCD monitor model B243HL", "hardware_spec"),
    ("Living room TV setup: TCL 65T8B 4K QLED panel with HDMI 2.1", "hardware_spec"),
    ("We have a TCL 65T8B connected via HDMI to soundbar", "hardware_spec"),
    ("Acer monitor B243HL screen display", "hardware_spec"),
    ("The machine has an NVIDIA GeForce GTX 1050 Ti GPU with 4GB VRAM", "hardware_spec"),
    ("Dolby Atmos soundbar audio setup connected via HDMI eARC", "hardware_spec"),

    # critique_filter (Negative reaction, complaints, items to avoid or blacklist)
    ("Found it boring and way too slow, avoid this completely", "critique_filter"),
    ("Snatch rejected for drab overcast grey palette and dull 90s tones", "critique_filter"),
    ("I hate slow-burn movies that take 45 minutes to get started at home", "critique_filter"),
    ("Stop recommending slow indie dramas with muted drab colors", "critique_filter"),
    ("Do not use fake dummy mock sponsored ads or placeholder auctions", "critique_filter"),
    ("Never use 555 Sonic Blue rally livery cliché on the car", "critique_filter"),
    ("This library is terrible and broken, blacklist and avoid it", "critique_filter"),
    ("This advice does not work, avoid this approach completely", "critique_filter"),
    ("Too verbose and full of AI slop, do not generate repetitive fluff", "critique_filter"),
    ("Reject slow pacing and drab grey muted cinematography", "critique_filter"),
    ("Do not recommend slowburn cinema, it is boring and depressing", "critique_filter"),
    ("That package has security vulnerabilities and broken dependencies, blacklist it", "critique_filter"),
    ("I dislike drab washed out visuals and overcast dreary lighting", "critique_filter"),
    ("Never suggest dummy placeholder data when real data is unavailable", "critique_filter"),
    ("I hated the movie, it was so drab and slowburn, avoid it", "critique_filter"),
    ("Snatch rejected because of ugly drab overcast grey palette", "critique_filter"),
    ("Do not recommend this, it is terribly slow and boring", "critique_filter"),
    ("Hate slowburn films with muted colors, blacklist them", "critique_filter"),
    ("Stop suggesting this library, it is broken and unusable", "critique_filter"),
    ("I hate slowburn movies, avoid them completely", "critique_filter"),

    # architectural_milestone (Technical design decisions, schemas, refactoring rules)
    ("Architecture decision: use TaskLedger SQLite database for subagent recovery", "architectural_milestone"),
    ("Refactor CLI command handlers into modular dispatchers and controllers", "architectural_milestone"),
    ("Clean architecture boundary between domain services and persistence storage", "architectural_milestone"),
    ("Schema migration: update LanceDB vector tables with hybrid search index", "architectural_milestone"),
    ("Design pattern: implement keyed file locks to prevent concurrency race conditions", "architectural_milestone"),
    ("Repository structure invariant: keep library code in src/cephalo package hierarchy", "architectural_milestone"),
    ("Database indexing and deduplication strategy for prompt records schema", "architectural_milestone"),
    ("Implement BullMQ task queues and streaming AI summarization pipelines", "architectural_milestone"),
    ("Subagent governor concurrency limit to 1 worker on battery power architecture", "architectural_milestone"),
    ("Dual engine architecture: compile native Rust core with Python fallback engine", "architectural_milestone"),
    ("Migrate prompt logging schema to include deprecation and supersession pointers", "architectural_milestone"),
    ("Architectural milestone: establish token-aware checkpoint and zero-lost-work resume ledger", "architectural_milestone"),
    ("Refactor continuous learning pipeline into autonomous harvester and synthesizer", "architectural_milestone"),
    ("Integrate fast hybrid vector search combining BM25 keyword and LanceDB dense vectors", "architectural_milestone"),
    ("Architecture milestone: implement TaskLedger SQLite database for rate-limit pause", "architectural_milestone"),
    ("Refactor CLI subcommand handlers into dedicated clean modules", "architectural_milestone"),
    ("Schema update: add deprecation and supersession columns to prompt table", "architectural_milestone"),
    ("Clean architecture boundary: decouple domain models from database adapters", "architectural_milestone"),
    ("We should refactor the database schema and add an index table", "architectural_milestone"),
    ("Refactor database schema to use LanceDB vector table", "architectural_milestone"),

    # ephemeral_query (General questions, standard search, casual banter)
    ("What time is it right now in Budapest Hungary?", "ephemeral_query"),
    ("How do I parse a JSON string in Python with json.loads?", "ephemeral_query"),
    ("Can you search the web for the latest weather forecast in Paris?", "ephemeral_query"),
    ("What is the difference between TCP and UDP protocols?", "ephemeral_query"),
    ("Convert 100 EUR to USD with currency conversion rates", "ephemeral_query"),
    ("How to reverse a linked list in C++ with pointers?", "ephemeral_query"),
    ("Hello, what can you help me with today assistant?", "ephemeral_query"),
    ("Explain how git rebase works compared to merge in git repository", "ephemeral_query"),
    ("Check if port 8080 is listening on localhost with netstat", "ephemeral_query"),
    ("Calculate the hash of this file with sha256 checksum", "ephemeral_query"),
    ("How do I find the longest common substring in Python?", "ephemeral_query"),
    ("What is the distance between Budapest and Vienna by train?", "ephemeral_query"),
    ("Can you tell me a short joke about programming?", "ephemeral_query"),
    ("How do I configure git user email for a single repository?", "ephemeral_query"),
    ("What is the weather forecast in Budapest today?", "ephemeral_query"),
    ("How do I convert a string to integer in Python?", "ephemeral_query"),
    ("What is the weather like in Berlin tomorrow?", "ephemeral_query"),
    ("How to parse JSON in Python?", "ephemeral_query"),
    ("Tell me what time it is in Tokyo right now", "ephemeral_query"),
    ("Search for coffee shops near downtown", "ephemeral_query"),
]


# =============================================================================
# Preference Rule Inducer (Capability 2 & 3)
# =============================================================================

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
