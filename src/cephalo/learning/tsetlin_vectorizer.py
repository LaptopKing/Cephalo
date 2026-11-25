"""
Cephalo Propositional Intent & Preference Rule Gatekeeper (tsetlin_gatekeeper.py)
================================================================================
Deterministic, explainable propositional rule gatekeeper using Tsetlin Machines (TMU).

Core Capabilities:
1. High-Speed Intent Routing: Classifies incoming prompts into 5 deterministic categories:
   - preference: User taste, aesthetic preferences, workflow declarations.
   - hardware_spec: Devices, monitors, TVs, GPUs, audio, physical environment.
   - critique_filter: Negative reaction, complaints, items to avoid or blacklist.
   - architectural_milestone: Technical design decisions, schemas, refactoring rules.
   - ephemeral_query: General questions, standard search, casual banter.
2. Preference Rule Induction: Analyzes user history / critique logs and trains a Tsetlin
   Machine to induce exact Boolean rules (e.g. accepting vibrant 4K / instant velocity vs
   rejecting drab grey / slowburn cinema).
3. Human-Readable Propositional Explanation: Generates transparent Boolean clause strings
   such as `(has("oled") AND has("tv")) -> hardware_spec`.
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
    "hardware_spec": "Physical devices, monitors, TVs, GPUs, RAM, display resolution, audio.",
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
    ("Living room TV is a 65-inch 4K OLED Google TV display", "hardware_spec"),
    ("Workstation monitor is a 27-inch 1440p IPS LCD screen", "hardware_spec"),
    ("GPU is a dedicated graphics card with 8GB VRAM and CUDA", "hardware_spec"),
    ("PC specs are Linux workstation with 32 GB RAM and NVMe SSD", "hardware_spec"),
    ("Audio setup has HDMI eARC Dolby Atmos soundbar and satellite speakers", "hardware_spec"),
    ("Display resolution is 3840x2160 4K UHD 60Hz HDR panel", "hardware_spec"),
    ("The laptop has 16GB memory and x86_64 CPU running Linux hardware", "hardware_spec"),
    ("Connected a secondary 24 inch 1080p display monitor via DisplayPort", "hardware_spec"),
    ("TV HDMI 2.1 port connected to console device", "hardware_spec"),
    ("Hardware profile: 4K television and dual monitor workstation", "hardware_spec"),
    ("Hardware constraint: power brownout when battery is discharging under 20 percent", "hardware_spec"),
    ("Display target: 65 inch 4K QLED panel with high dynamic range", "hardware_spec"),
    ("System memory has 16 GB free RAM with dedicated GPU", "hardware_spec"),
    ("Audio setup configured for eARC passthrough and subwoofer", "hardware_spec"),
    ("My workstation has an external 24 inch LCD monitor", "hardware_spec"),
    ("Living room TV setup: 4K OLED panel with HDMI 2.1", "hardware_spec"),
    ("We have a 4K TV connected via HDMI to soundbar", "hardware_spec"),
    ("External monitor screen display connected via HDMI", "hardware_spec"),
    ("The machine has a dedicated GPU with 8GB VRAM", "hardware_spec"),
    ("Dolby Atmos soundbar audio setup connected via HDMI eARC", "hardware_spec"),

    # critique_filter (Negative reaction, complaints, items to avoid or blacklist)
    ("Found it boring and way too slow, avoid this completely", "critique_filter"),
    ("Film rejected for drab overcast grey palette and dull tones", "critique_filter"),
    ("I hate slow-burn movies that take 45 minutes to get started at home", "critique_filter"),
    ("Stop recommending slow indie dramas with muted drab colors", "critique_filter"),
    ("Do not use fake dummy mock sponsored ads or placeholder auctions", "critique_filter"),
    ("Never use generic cliché livery patterns on the car", "critique_filter"),
    ("This library is terrible and broken, blacklist and avoid it", "critique_filter"),
    ("This advice does not work, avoid this approach completely", "critique_filter"),
    ("Too verbose and full of AI slop, do not generate repetitive fluff", "critique_filter"),
    ("Reject slow pacing and drab grey muted cinematography", "critique_filter"),
    ("Do not recommend slowburn cinema, it is boring and depressing", "critique_filter"),
    ("That package has security vulnerabilities and broken dependencies, blacklist it", "critique_filter"),
    ("I dislike drab washed out visuals and overcast dreary lighting", "critique_filter"),
    ("Never suggest dummy placeholder data when real data is unavailable", "critique_filter"),
    ("I hated the movie, it was so drab and slowburn, avoid it", "critique_filter"),
    ("Movie rejected because of ugly drab overcast grey palette", "critique_filter"),
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

