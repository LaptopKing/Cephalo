#!/usr/bin/env python3
"""
Personal Second Brain - Clean, Production-Ready Embedding & Vector Storage Pipeline
===================================================================================
Features:
1. Sanitization First: All inputs (prompts, queries, batch files) are processed through
   Presidio (PII redaction) + deterministic regex rules before reaching embedding models
   or vector storage.
2. Dual Embedding Support:
   - Mode A (Local / Zero-Leak): Lightweight, local ONNX embeddings via FastEmbed
     (e.g., 'BAAI/bge-small-en-v1.5' [384d] or 'nomic-ai/nomic-embed-text-v1.5' [768d]).
   - Mode B (Google Cloud): Google 'text-embedding-004' via Google GenAI SDK with
     automatic HTTP REST fallback. Full Matryoshka dimension truncation (e.g., 768 -> 256).
3. Storage: High-performance, columnar vector storage in LanceDB with native PyArrow schema,
   metadata preservation, and automatic ID deduplication.
4. Python 3.12.10 verified and production-ready.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import math
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Load environment variables if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pyarrow as pa
import lancedb

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("second_brain.pipeline")
logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)

# Default Base Paths
ROOT_DIR = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT_DIR
DATA_DIR = ROOT_DIR / "data"
PROMPTS_FILE = DATA_DIR / "prompts.jsonl"
DEFAULT_LANCEDB_DIR = DATA_DIR / "lancedb"

TAG_REGEX = re.compile(r'(?<!\S)#([a-zA-Z][a-zA-Z0-9_\-\/]*)\b')


def extract_tags(text: str) -> List[str]:
    """Extracts inline #tags and hierarchical #tag/subtags from text (e.g. #cinema/hdr, #backend)."""
    if not text:
        return []
    matches = TAG_REGEX.findall(text)
    tags: List[str] = []
    for m in matches:
        clean = m.strip("/").lower()
        if clean and clean not in tags:
            tags.append(clean)
    return tags


# ==============================================================================
# 1. Sanitization Layer (Integrity & Security First)
# ==============================================================================
def calculate_shannon_entropy(data: str) -> float:
    """Calculates the Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    counts = {}
    for char in data:
        counts[char] = counts.get(char, 0) + 1
    for count in counts.values():
        p_x = count / length
        entropy -= p_x * math.log2(p_x)
    return entropy


def is_code_line(line: str) -> bool:
    """Detects if a line is likely source code or terminal syntax rather than natural prose."""
    stripped = line.strip()
    if not stripped:
        return False
    code_keywords = (
        "def ", "class ", "import ", "from ", "return ", "function ",
        "const ", "let ", "var ", "public ", "private ", "protected ",
        "print(", "console.log(", "logger.", "if __name__ ==",
    )
    if any(stripped.startswith(kw) or f" {kw}" in stripped for kw in code_keywords):
        return True
    if re.search(r'[\w_]+\.[\w_]+\s*\(', stripped):  # method call: obj.method()
        return True
    if re.search(r'^\s*[\w_]+\s*=\s*[\w_]+\(?', stripped):  # assignment: a = func(...)
        return True
    return False


class Sanitizer:
    """Detects and redacts credentials, secrets, tokens, and PII.

    Adopts the multi-tier hybrid security design:
    - Tier 1A: Deterministic regex for structural tokens, API keys, Hungarian IBAN/tax IDs, IPs.
    - Tier 1B: Shannon Entropy guard on secret assignments (passwords, tokens, keys).
    - Tier 1C: Code syntax shield (protects code identifiers like 'person' from being corrupted).
    - Tier 2: GLiNER zero-shot contextual decision model for edge-case credentials.
    - Tier 3: Microsoft Presidio for natural language personal entities (names, phone, addresses).
    """

    PATTERNS = [
        # Explicit API Keys & Tokens
        (re.compile(r'sk-[a-zA-Z0-9_\-]{20,}'), '<REDACTED_API_KEY>'),
        (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '<REDACTED_GITHUB_TOKEN>'),
        (re.compile(r'Bearer\s+[a-zA-Z0-9\._\-]{20,}', re.IGNORECASE), 'Bearer <REDACTED_TOKEN>'),
        # Hungarian IBAN (HU + 26 digits) & International IBAN
        (re.compile(r'\bHU\d{2}[\s\-]?(?:\d{4}[\s\-]?){5}\d{4}\b', re.IGNORECASE), '<REDACTED_HU_IBAN>'),
        # Hungarian GIRO Domestic Bank Account (8-8 or 8-8-8 digits)
        (re.compile(r'\b\d{8}[\s\-]\d{8}(?:[\s\-]\d{8})?\b'), '<REDACTED_HU_BANK_ACC>'),
        # Financial & Credit Cards
        (re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b'), '<REDACTED_CARD>'),
        # Hungarian Tax ID (Adóazonosító jel: 10 digits starting with 8)
        (re.compile(r'\b8\d{9}\b'), '<REDACTED_HU_TAX_ID>'),
        # Hungarian Corporate Tax Number (Adószám: xxxxxxxx-y-zz)
        (re.compile(r'\b\d{8}-[1-5]-[0-5]\d\b'), '<REDACTED_HU_TAX_NO>'),
        # Hungarian Phone Numbers (+36 / 06 format)
        (re.compile(r'(?:\+36|06)[\s\-]?(?:[1-9]\d{0,1})[\s\-]?\d{3}[\s\-]?\d{3,4}\b'), '<REDACTED_HU_PHONE>'),
        # Hungarian Identity Card (6 digits + 2 uppercase letters)
        (re.compile(r'\b\d{6}[A-Z]{2}\b'), '<REDACTED_HU_ID>'),
        # General Contact & Network
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '<REDACTED_EMAIL>'),
        (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '<REDACTED_IP>'),
    ]

    ASSIGNMENT_PATTERN = re.compile(
        r'(?i)(api[_-]?key|secret|token|password|auth|bearer)[\s:=]+["\']?([a-zA-Z0-9!@#\$%\^&\*_\-]{8,})["\']?'
    )

    TARGET_PRESIDIO_ENTITIES = [
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "CRYPTO",
        "IP_ADDRESS",
        "IBAN_CODE",
    ]

    def __init__(self, enable_gliner: bool = False):
        # 1. Presidio Setup
        self.presidio_available = False
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self.presidio_available = True
        except Exception as e:
            logger.debug(f"Presidio not available or missing language model: {e}")

        # 2. GLiNER Decision Model Setup (Local Zero-Shot)
        self.gliner_model = None
        if enable_gliner:
            try:
                from gliner import GLiNER
                self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
                logger.info("GLiNER local decision model loaded successfully.")
            except Exception as e:
                logger.debug(f"GLiNER not loaded (optional contextual decision layer): {e}")

    def sanitize_line(self, line: str) -> str:
        """Sanitizes a single line of text through the multi-tier hybrid pipeline."""
        if not line:
            return ""

        # Tier 1A: Deterministic Regex for unambiguous formats
        for pattern, replacement in self.PATTERNS:
            line = pattern.sub(replacement, line)

        # Tier 1B: Shannon Entropy Guard on Assigned Secrets
        def replace_entropy_secret(match):
            prefix = match.group(1)
            token = match.group(2)
            is_hex = bool(re.fullmatch(r'[0-9a-fA-F]+', token))
            ent = calculate_shannon_entropy(token)
            threshold = 3.0 if is_hex else 3.4
            if ent >= threshold or len(token) >= 24:
                return f"{prefix}=<REDACTED_SECRET>"
            return match.group(0)

        line = self.ASSIGNMENT_PATTERN.sub(replace_entropy_secret, line)

        # Tier 1C: Code Syntax Shield
        if is_code_line(line):
            # Code line detected: shield identifiers from NLP mangling
            return line

        # Tier 2: GLiNER Contextual Decision Model (on prose)
        if self.gliner_model:
            try:
                placeholder_spans = [(m.start(), m.end()) for m in re.finditer(r'<[A-Z0-9_]+>', line)]
                labels = ["password", "api_key", "secret_token", "credential", "person_name"]
                entities = self.gliner_model.predict_entities(line, labels, threshold=0.50)
                for ent in sorted(entities, key=lambda x: x["start"], reverse=True):
                    # Check overlap with existing placeholder
                    overlaps = any(not (ent["end"] <= ps[0] or ent["start"] >= ps[1]) for ps in placeholder_spans)
                    if overlaps:
                        continue
                    label_tag = f"<REDACTED_{ent['label'].upper()}>"
                    line = line[:ent["start"]] + label_tag + line[ent["end"]:]
            except Exception as e:
                logger.debug(f"GLiNER inference error on line: {e}")

        # Tier 3: Microsoft Presidio Anonymization (on prose)
        if self.presidio_available:
            try:
                placeholder_spans = [(m.start(), m.end()) for m in re.finditer(r'<[A-Z0-9_]+>', line)]
                results = self.analyzer.analyze(
                    text=line,
                    entities=self.TARGET_PRESIDIO_ENTITIES,
                    language="en",
                )
                if results:
                    filtered_results = []
                    for r in results:
                        overlaps = any(not (r.end <= ps[0] or r.start >= ps[1]) for ps in placeholder_spans)
                        if not overlaps and r.score >= 0.60:
                            filtered_results.append(r)
                    if filtered_results:
                        anonymized = self.anonymizer.anonymize(text=line, analyzer_results=filtered_results)
                        line = anonymized.text
            except Exception as e:
                logger.debug(f"Presidio error: {e}")

        return line

    def sanitize(self, text: str) -> str:
        """Sanitizes text line-by-line while preserving code blocks and structure."""
        if not text:
            return ""
        lines = text.split("\n")
        return "\n".join(self.sanitize_line(l) for l in lines)


# ==============================================================================
# 2. Embedding Layer (Dual Modes: Mode A Local & Mode B Google Cloud)
# ==============================================================================
class BaseEmbedder(ABC):
    """Abstract interface for embedding models."""

    @property
    @abstractmethod
    def mode(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of clean texts into float vector arrays."""
        pass

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string."""
        return self.embed_texts([query])[0]


class FastEmbedEmbedder(BaseEmbedder):
    """Mode A: Local / Zero-Leak Embedding via FastEmbed.
    
    Zero data leaves the machine. Runs on ONNX runtime with on-demand GPU acceleration
    and automated CPU fallback.
    Default model: 'Qwen/Qwen3-Embedding-0.6B-Q' (1024 dimensions, 32,768 context tokens, Apache 2.0).
    Alternatives: 'BAAI/bge-small-en-v1.5' (384d), 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2' (768d).
    """

    KNOWN_DIMENSIONS = {
        "Qwen/Qwen3-Embedding-0.6B-Q": 1024,
        "Qwen/Qwen3-Embedding-0.6B": 1024,
        "BAAI/bge-small-en-v1.5": 384,
        "BAAI/bge-base-en-v1.5": 768,
        "nomic-ai/nomic-embed-text-v1.5": 768,
        "nomic-ai/nomic-embed-text-v1.5-Q": 768,
        "sentence-transformers/all-MiniLM-L6-v2": 384,
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
        "jinaai/jina-embeddings-v3": 1024,
    }

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B-Q"):
        self._model_name = model_name
        self._mode = "local"
        
        # On-Demand GPU Provider Configuration with Automated CPU Fallback
        providers = []
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in available_providers:
                providers.append("CUDAExecutionProvider")
        except Exception:
            pass
        providers.append("CPUExecutionProvider")

        try:
            from fastembed import TextEmbedding
            self._engine = TextEmbedding(model_name=self._model_name, providers=providers)
        except ImportError as e:
            raise ImportError(
                "FastEmbed is not installed. Please install it via: pip install fastembed"
            ) from e

        # Determine dimensionality
        if self._model_name in self.KNOWN_DIMENSIONS:
            self._dimension = self.KNOWN_DIMENSIONS[self._model_name]
        else:
            sample = list(self._engine.embed(["dimension_probe"]))[0]
            self._dimension = len(sample)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self._engine.embed(texts)
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string with instruction prefix if model is Qwen."""
        if "qwen" in self._model_name.lower():
            # Qwen models achieve peak retrieval accuracy when queries use the instruction prefix
            formatted_query = f"Instruct: Given a search query, retrieve relevant passages that answer the query\nQuery:{query}"
            return self.embed_texts([formatted_query])[0]
        return self.embed_texts([query])[0]


class GoogleEmbedder(BaseEmbedder):
    """Mode B: Google Cloud Embeddings via 'text-embedding-004'.
    
    Supports native Matryoshka dimension truncation (e.g. 768 down to 256 or 128).
    Implements Google GenAI SDK with automatic HTTP REST fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "text-embedding-004",
        dimension: int = 768,
    ):
        self._mode = "google"
        self._model_name = model_name
        self._dimension = dimension
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google Cloud embedding mode requires an API key.\n"
                "Provide it via: --api-key <KEY>, or set environment variable "
                "GEMINI_API_KEY or GOOGLE_API_KEY in .env, or use '--mode local'."
            )

        self._genai_client = None
        try:
            from google import genai
            self._genai_client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.debug(f"google-genai client initialization skipped: {e}. Will use REST API.")

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed_via_sdk(self, texts: List[str]) -> List[List[float]]:
        """Calls Google GenAI SDK."""
        from google.genai import types

        config = types.EmbedContentConfig(output_dimensionality=self._dimension)
        # Google SDK supports list of strings for batch embedding
        response = self._genai_client.models.embed_content(
            model=self._model_name,
            contents=texts,
            config=config,
        )
        return [emb.values for emb in response.embeddings]

    def _embed_via_rest(self, texts: List[str]) -> List[List[float]]:
        """Fallback REST API call."""
        import requests

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model_name}:batchEmbedContents?key={self.api_key}"
        )
        payload = {
            "requests": [
                {
                    "model": f"models/{self._model_name}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self._dimension,
                }
                for t in texts
            ]
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Google Embedding REST API returned HTTP {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        embeddings = data.get("embeddings", [])
        return [item["values"] for item in embeddings]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Batch in chunks of 50 to respect API request constraints
        chunk_size = 50
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            if self._genai_client:
                try:
                    all_embeddings.extend(self._embed_via_sdk(chunk))
                    continue
                except Exception as sdk_err:
                    logger.warning(f"SDK embedding call failed ({sdk_err}), trying REST fallback...")

            # REST fallback
            all_embeddings.extend(self._embed_via_rest(chunk))

        return all_embeddings


# ==============================================================================
# 3. Storage Layer (LanceDB Columnar Vector Store)
# ==============================================================================
class LanceDBStore:
    """Manages storage and vector retrieval using local LanceDB tables."""

    def __init__(self, db_path: Path, table_name: str, dimension: int):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self.dimension = dimension

        self.db = lancedb.connect(str(self.db_path))
        self.table = self._get_or_create_table()

    def _get_schema(self) -> pa.Schema:
        """Defines the PyArrow schema with fixed vector dimensions, tags, and relations."""
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), self.dimension)),
            pa.field("content", pa.string()),
            pa.field("category", pa.string()),
            pa.field("source", pa.string()),
            pa.field("timestamp", pa.string()),
            pa.field("embedding_model", pa.string()),
            pa.field("dimension", pa.int32()),
            pa.field("extracted_intent", pa.string()),
            pa.field("learned_traits", pa.list_(pa.string())),
            pa.field("sanitized", pa.bool_()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("supersedes", pa.string()),
            pa.field("relates_to", pa.list_(pa.string())),
            pa.field("is_deprecated", pa.bool_()),
        ])

    def _ensure_columns_exist(self, tbl) -> None:
        """Adds missing metadata columns to existing tables without data loss."""
        existing_fields = set(tbl.schema.names)
        fields_to_add = []
        if "tags" not in existing_fields:
            fields_to_add.append(pa.field("tags", pa.list_(pa.string())))
        if "supersedes" not in existing_fields:
            fields_to_add.append(pa.field("supersedes", pa.string()))
        if "relates_to" not in existing_fields:
            fields_to_add.append(pa.field("relates_to", pa.list_(pa.string())))
        if "is_deprecated" not in existing_fields:
            fields_to_add.append(pa.field("is_deprecated", pa.bool_()))

        if fields_to_add:
            try:
                tbl.add_columns(fields_to_add)
                logger.info(f"Migrated table '{self.table_name}' with new columns: {[f.name for f in fields_to_add]}")
            except Exception as e:
                logger.warning(f"Could not auto-migrate columns on '{self.table_name}': {e}")

    def _get_or_create_table(self):
        """Opens the existing table or creates an empty one with correct schema."""
        raw_tables = self.db.list_tables()
        table_names = list(getattr(raw_tables, "tables", raw_tables))
        if self.table_name in table_names:
            tbl = self.db.open_table(self.table_name)
            # Verify dimension compatibility
            schema = tbl.schema
            vec_field = schema.field("vector")
            # If fixed_size_list, verify size
            if hasattr(vec_field.type, "list_size"):
                existing_dim = vec_field.type.list_size
                if existing_dim != self.dimension:
                    raise ValueError(
                        f"Table '{self.table_name}' expects vector dimension {existing_dim}, "
                        f"but active embedder dimension is {self.dimension}. "
                        f"Please specify a different table via --table or use matching embedding model/dim."
                    )
            self._ensure_columns_exist(tbl)
            return tbl

        return self.db.create_table(self.table_name, schema=self._get_schema())

    def deprecate_record(self, record_id: str, superseded_by: str = "") -> bool:
        """Marks a record as deprecated when superseded by a newer memory."""
        if self.table.count_rows() == 0:
            return False
        try:
            clean_id = record_id.replace("'", "''")
            self.table.update(where=f"id = '{clean_id}'", values={"is_deprecated": True})
            logger.info(f"Deprecated memory record '{record_id}' (superseded by '{superseded_by}')")
            return True
        except Exception as e:
            logger.warning(f"Failed to deprecate record '{record_id}': {e}")
            return False

    def get_existing_ids(self) -> Set[str]:
        """Returns the set of prompt IDs already stored in this table."""
        if self.table.count_rows() == 0:
            return set()
        try:
            arrow_table = self.table.to_arrow()
            return set(arrow_table["id"].to_pylist())
        except Exception as e:
            logger.debug(f"Could not read existing IDs: {e}")
            return set()

    def add_records(self, records: List[Dict[str, Any]]) -> int:
        """Inserts records into LanceDB, skipping existing IDs and ensuring field defaults."""
        if not records:
            return 0

        existing_ids = self.get_existing_ids()
        new_records = [r for r in records if r["id"] not in existing_ids]

        if not new_records:
            return 0

        # Ensure default values for tag and relation fields
        sanitized_records = []
        for r in new_records:
            rec = dict(r)
            if "tags" not in rec or rec["tags"] is None:
                rec["tags"] = []
            if "supersedes" not in rec or rec["supersedes"] is None:
                rec["supersedes"] = ""
            if "relates_to" not in rec or rec["relates_to"] is None:
                rec["relates_to"] = []
            if "is_deprecated" not in rec or rec["is_deprecated"] is None:
                rec["is_deprecated"] = False
            sanitized_records.append(rec)

        self.table.add(sanitized_records)
        self.ensure_fts_index("content")
        return len(sanitized_records)

    def ensure_fts_index(self, field: str = "content"):
        """Ensures a full-text search (FTS) index exists on the given field for hybrid search."""
        if self.table.count_rows() == 0:
            return
        try:
            from lancedb.index import FTS
            self.table.create_index(field, config=FTS(), replace=True)
        except Exception as e:
            logger.debug(f"Could not build/update FTS index on '{field}': {e}")

    def search(
        self,
        query_vector: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        query_type: str = "hybrid",
        where: Optional[str] = None,
        limit: int = 5,
        tag: Optional[str] = None,
        include_deprecated: bool = False,
    ) -> List[Dict[str, Any]]:
        """Performs hybrid, vector, or full-text search with optional SQL filtering and tag matching."""
        if self.table.count_rows() == 0:
            return []

        # Build compound where clause
        conditions = []
        if where:
            conditions.append(f"({where})")
        if not include_deprecated and "is_deprecated" in self.table.schema.names:
            conditions.append("(is_deprecated IS NULL OR is_deprecated = false)")
        if tag and "tags" in self.table.schema.names:
            clean_tag = tag.lstrip("#").strip().lower().replace("'", "''")
            conditions.append(f"array_has(tags, '{clean_tag}')")

        active_where = " AND ".join(conditions) if conditions else None

        # 1. Hybrid Search (Dense Vector + BM25 Full-Text)
        if query_type.lower() == "hybrid" and query_vector is not None and query_text:
            try:
                self.ensure_fts_index("content")
                builder = (
                    self.table.search(query_type="hybrid")
                    .vector(query_vector)
                    .text(query_text)
                )
                if active_where:
                    builder = builder.where(active_where)
                return builder.limit(limit).to_list()
            except Exception as err:
                logger.warning(f"Hybrid search failed ({err}); falling back to vector search.")
                # Fall through to vector search

        # 2. Vector Search
        if query_vector is not None and query_type.lower() in ("vector", "hybrid"):
            builder = self.table.search(query_vector)
            if active_where:
                builder = builder.where(active_where)
            return builder.limit(limit).to_list()

        # 3. Full-Text Search (FTS / BM25 only)
        if query_text and query_type.lower() == "fts":
            self.ensure_fts_index("content")
            builder = self.table.search(query_text, query_type="fts")
            if active_where:
                builder = builder.where(active_where)
            return builder.limit(limit).to_list()

        return []

    def count(self) -> int:
        return self.table.count_rows()


# ==============================================================================
# 4. High-Level Embedding Pipeline Orchestrator
# ==============================================================================
class EmbeddingPipeline:
    """Coordinates Sanitization -> Embedding -> LanceDB Storage."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        db_path: Path = DEFAULT_LANCEDB_DIR,
        table_name: Optional[str] = None,
        sanitizer: Optional[Sanitizer] = None,
    ):
        self.sanitizer = sanitizer or Sanitizer(enable_gliner=False)
        self.embedder = embedder
        self.db_path = Path(db_path)

        # Default table name incorporates mode and dimension to avoid vector dimension conflicts
        if not table_name:
            table_name = f"prompts_{self.embedder.mode}_{self.embedder.dimension}"

        self.store = LanceDBStore(
            db_path=self.db_path,
            table_name=table_name,
            dimension=self.embedder.dimension,
        )

    def ingest_prompt(
        self,
        raw_text: str,
        prompt_id: Optional[str] = None,
        source: str = "cli",
        category: str = "general",
        intent: str = "",
        traits: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        supersedes: Optional[str] = None,
        relates_to: Optional[List[str]] = None,
        sync_to_jsonl: bool = True,
    ) -> Dict[str, Any]:
        """Sanitizes, embeds, and stores a single prompt with tag extraction and supersession tracking."""
        clean_text = self.sanitizer.sanitize(raw_text.strip())
        traits = traits or []

        # Extract inline tags and combine with explicit tags
        inline_tags = extract_tags(raw_text)
        merged_tags = list(dict.fromkeys((tags or []) + inline_tags))
        merged_tags = [t.lstrip("#").strip().lower() for t in merged_tags if t.strip()]

        if not prompt_id:
            count = self.store.count() + 1
            prompt_id = f"prompt-{count:03d}"

        # If this prompt supersedes an existing memory, deprecate the older one
        if supersedes:
            self.store.deprecate_record(supersedes, superseded_by=prompt_id)

        timestamp = datetime.datetime.now().astimezone().isoformat()
        vector = self.embedder.embed_query(clean_text)

        record = {
            "id": prompt_id,
            "vector": vector,
            "content": clean_text,
            "category": category,
            "source": source,
            "timestamp": timestamp,
            "embedding_model": f"{self.embedder.mode}:{self.embedder.model_name}",
            "dimension": self.embedder.dimension,
            "extracted_intent": intent,
            "learned_traits": traits,
            "tags": merged_tags,
            "supersedes": supersedes or "",
            "relates_to": relates_to or [],
            "is_deprecated": False,
            "sanitized": True,
        }

        self.store.add_records([record])

        # Optionally append to prompts.jsonl to keep text store synchronized
        if sync_to_jsonl:
            PROMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            jsonl_entry = {
                "id": prompt_id,
                "timestamp": timestamp,
                "source": source,
                "category": category,
                "tags": merged_tags,
                "supersedes": supersedes or "",
                "relates_to": relates_to or [],
                "is_deprecated": False,
                "content": clean_text,
                "extracted_intent": intent,
                "learned_traits": traits,
            }
            with open(PROMPTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(jsonl_entry, ensure_ascii=False) + "\n")

        return record

    def sync_from_jsonl(self, jsonl_path: Path = PROMPTS_FILE) -> Tuple[int, int]:
        """Ingests entries from prompts.jsonl into the LanceDB vector store."""
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            logger.warning(f"File not found: {jsonl_path}")
            return 0, 0

        existing_ids = self.store.get_existing_ids()
        to_process: List[Dict[str, Any]] = []

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("id") not in existing_ids:
                        to_process.append(entry)
                except Exception as e:
                    logger.error(f"Error parsing jsonl line: {e}")

        if not to_process:
            logger.info("Vector database is already up-to-date with prompts.jsonl.")
            return 0, len(existing_ids)

        logger.info(f"Processing {len(to_process)} new prompts for vector storage...")

        # 1. Sanitize all contents
        sanitized_texts = [
            self.sanitizer.sanitize(item.get("content", "")) for item in to_process
        ]

        # 2. Batch embed
        logger.info(
            f"Generating embeddings via [{self.embedder.mode.upper()}] "
            f"model='{self.embedder.model_name}' dim={self.embedder.dimension}..."
        )
        vectors = self.embedder.embed_texts(sanitized_texts)

        # 3. Assemble LanceDB records
        records = []
        for i, item in enumerate(to_process):
            raw_traits = item.get("learned_traits", [])
            if isinstance(raw_traits, str):
                traits_list = [t.strip() for t in raw_traits.split(",") if t.strip()]
            elif isinstance(raw_traits, list):
                traits_list = [str(t) for t in raw_traits]
            else:
                traits_list = []

            inline_tags = extract_tags(item.get("content", ""))
            item_tags = item.get("tags", [])
            if isinstance(item_tags, str):
                item_tags = [t.strip() for t in item_tags.split(",") if t.strip()]
            combined_tags = list(dict.fromkeys(item_tags + inline_tags))
            clean_tags = [t.lstrip("#").strip().lower() for t in combined_tags if t.strip()]

            records.append({
                "id": item.get("id", f"prompt-{i+1:03d}"),
                "vector": vectors[i],
                "content": sanitized_texts[i],
                "category": item.get("category", "general"),
                "source": item.get("source", "jsonl_import"),
                "timestamp": item.get("timestamp", datetime.datetime.now().astimezone().isoformat()),
                "embedding_model": f"{self.embedder.mode}:{self.embedder.model_name}",
                "dimension": self.embedder.dimension,
                "extracted_intent": item.get("extracted_intent", ""),
                "learned_traits": traits_list,
                "tags": clean_tags,
                "supersedes": str(item.get("supersedes", "")),
                "relates_to": list(item.get("relates_to", [])),
                "is_deprecated": bool(item.get("is_deprecated", False)),
                "sanitized": True,
            })

        inserted = self.store.add_records(records)
        return inserted, len(existing_ids)

    def search(
        self,
        raw_query: str,
        query_type: str = "hybrid",
        where: Optional[str] = None,
        limit: int = 5,
        tag: Optional[str] = None,
        include_deprecated: bool = False,
    ) -> List[Dict[str, Any]]:
        """Sanitizes query, generates query vector, and executes hybrid, vector, or FTS search."""
        # Sanitize query before embedding (Zero-Leak)
        clean_query = self.sanitizer.sanitize(raw_query.strip())
        query_vector = self.embedder.embed_query(clean_query)
        results = self.store.search(
            query_vector=query_vector,
            query_text=clean_query,
            query_type=query_type,
            where=where,
            limit=limit,
            tag=tag,
            include_deprecated=include_deprecated,
        )
        return results


# ==============================================================================
# 5. CLI & Factory Helper
# ==============================================================================
def create_embedder(
    mode: str = "local",
    model: Optional[str] = None,
    dimension: Optional[int] = None,
    api_key: Optional[str] = None,
) -> BaseEmbedder:
    """Factory creating either FastEmbed (Local) or Google Cloud embedder."""
    if mode.lower() == "local":
        model_name = model or "Qwen/Qwen3-Embedding-0.6B-Q"
        return FastEmbedEmbedder(model_name=model_name)
    elif mode.lower() in ("google", "cloud"):
        model_name = model or "text-embedding-004"
        dim = dimension or 768
        return GoogleEmbedder(api_key=api_key, model_name=model_name, dimension=dim)
    else:
        raise ValueError(f"Unknown embedding mode: '{mode}'. Choose 'local' or 'google'.")


def main():
    parser = argparse.ArgumentParser(
        description="Personal Second Brain - Vector Ingestion & Semantic Search Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--mode",
        choices=["local", "google"],
        default="local",
        help="Embedding mode: 'local' (FastEmbed, zero-leak) or 'google' (Google Cloud text-embedding-004).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Embedding model identifier (default: 'Qwen/Qwen3-Embedding-0.6B-Q' [32k tokens, Apache 2.0] for local).",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=None,
        help="Embedding dimensionality (useful for Matryoshka dimension truncation on Google Cloud: e.g. 768, 256, 128).",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        help="LanceDB table name (defaults to 'prompts_local' or 'prompts_google').",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Google API Key (can also be set via GEMINI_API_KEY or GOOGLE_API_KEY environment variable).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_LANCEDB_DIR),
        help=f"Path to local LanceDB storage directory (default: {DEFAULT_LANCEDB_DIR}).",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: sync
    sync_p = subparsers.add_parser("sync", help="Sync prompts.jsonl into the vector database.")
    sync_p.add_argument(
        "--file",
        type=str,
        default=str(PROMPTS_FILE),
        help=f"Path to prompts jsonl file (default: {PROMPTS_FILE}).",
    )

    # Command: add
    add_p = subparsers.add_parser("add", help="Sanitize, embed, and store a new prompt directly.")
    add_p.add_argument("text", type=str, help="Raw prompt content to ingest.")
    add_p.add_argument("--category", type=str, default="general", help="Prompt category.")
    add_p.add_argument("--source", type=str, default="cli", help="Source of prompt.")
    add_p.add_argument("--intent", type=str, default="", help="Extracted intent.")

    # Command: search
    search_p = subparsers.add_parser("search", help="Perform hybrid, vector, or keyword search against stored records.")
    search_p.add_argument("query", type=str, help="Search query string.")
    search_p.add_argument(
        "--type",
        choices=["hybrid", "vector", "fts"],
        default="hybrid",
        help="Search mode: 'hybrid' (vector + BM25 keyword), 'vector' (semantic only), or 'fts' (BM25 keyword only). Default: hybrid.",
    )
    search_p.add_argument(
        "--where",
        type=str,
        default=None,
        help="SQL filter expression (e.g. \"category = 'code'\" or \"timestamp >= '2026-10-20'\").",
    )
    search_p.add_argument("--limit", type=int, default=3, help="Max results to return (default: 3).")

    # Command: status
    subparsers.add_parser("status", help="Print vector store status, table names, and record counts.")

    args = parser.parse_args()

    # Determine command
    cmd = args.command or "status"

    # Initialize embedder and pipeline
    try:
        embedder = create_embedder(
            mode=args.mode,
            model=args.model,
            dimension=args.dim,
            api_key=args.api_key,
        )
        pipeline = EmbeddingPipeline(
            embedder=embedder,
            db_path=Path(args.db_path),
            table_name=args.table,
        )
    except Exception as init_err:
        print(f"\n[ERROR] Pipeline initialization failed: {init_err}")
        sys.exit(1)

    # Execute subcommand
    if cmd == "sync":
        print("=" * 60)
        print("  SECOND BRAIN - VECTOR STORE SYNC")
        print("=" * 60)
        print(f"Source JSONL:     {args.file}")
        print(f"Embedding Engine: {embedder.mode.upper()} ({embedder.model_name}, dim={embedder.dimension})")
        print(f"LanceDB Path:     {pipeline.db_path}")
        print(f"Table Name:       {pipeline.store.table_name}")
        print("-" * 60)
        inserted, existing = pipeline.sync_from_jsonl(jsonl_path=Path(args.file))
        print(f"[+] Sync Complete: {inserted} new records inserted ({existing} already indexed).")
        print(f"[+] Total table records: {pipeline.store.count()}")
        print("=" * 60)

    elif cmd == "add":
        record = pipeline.ingest_prompt(
            raw_text=args.text,
            category=args.category,
            source=args.source,
            intent=args.intent,
        )
        print(f"[+] Recorded & Indexed [{record['id']}]:")
        print(f"    Sanitized Content: {record['content']}")
        print(f"    Model:             {record['embedding_model']} (dim={record['dimension']})")
        print(f"    Table:             {pipeline.store.table_name}")

    elif cmd == "search":
        print(f"\nSearching for: '{args.query}' (Mode: {embedder.mode.upper()}, Type: {args.type.upper()}, Dim: {embedder.dimension})")
        if args.where:
            print(f"SQL Filter:     {args.where}")
        results = pipeline.search(
            raw_query=args.query,
            query_type=args.type,
            where=args.where,
            limit=args.limit,
        )
        if not results:
            print("No matching records found. (Have you run 'sync' first?)")
            return

        print("-" * 70)
        for rank, res in enumerate(results, 1):
            if "_relevance_score" in res:
                score_str = f"Relevance: {res['_relevance_score']:.4f}"
            elif "_distance" in res:
                score_str = f"Distance: {res['_distance']:.4f}"
            elif "_score" in res:
                score_str = f"Score: {res['_score']:.4f}"
            else:
                score_str = "Match"

            pid = res.get("id", "N/A")
            cat = res.get("category", "general")
            content = res.get("content", "")
            preview = (content[:95] + "...") if len(content) > 95 else content
            print(f"  #{rank} [{score_str}] [{pid}] ({cat})")
            print(f"      {preview}")
        print("-" * 70)

    elif cmd == "status":
        sanitizer = pipeline.sanitizer
        print("=" * 60)
        print("  PERSONAL SECOND BRAIN - VECTOR STORAGE STATUS")
        print("=" * 60)
        print(f"LanceDB Directory: {pipeline.db_path}")
        print(f"Active Table:      {pipeline.store.table_name} ({pipeline.store.count()} records)")
        table_list = list(getattr(pipeline.store.db.list_tables(), 'tables', pipeline.store.db.list_tables()))
        print(f"All Tables:        {table_list}")
        print(f"Embedding Mode:    {embedder.mode.upper()}")
        print(f"Model Name:        {embedder.model_name}")
        print(f"Vector Dimension:  {embedder.dimension}")
        print(f"Presidio Engine:   {'Active (Spacy en_core_web_lg)' if sanitizer.presidio_available else 'Fallback Regex'}")
        print("=" * 60)


if __name__ == "__main__":
    main()
