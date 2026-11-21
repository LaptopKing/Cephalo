"""
Cephalo LanceDB Vector Store and Hybrid Query Engine.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import lancedb
import numpy as np
import pyarrow as pa

logger = logging.getLogger("cephalo.lancedb_store")

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
            pa.field("superseded_by", pa.string()),
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
        if "superseded_by" not in existing_fields:
            fields_to_add.append(pa.field("superseded_by", pa.string()))
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

    def deprecate_record(self, record_id: str, superseded_by: str = "", sync_to_jsonl: bool = True) -> bool:
        """Marks a record as deprecated when superseded by a newer memory."""
        if self.table.count_rows() == 0:
            return False
        try:
            clean_id = record_id.replace("'", "''")
            clean_sub = (superseded_by or "").replace("'", "''")
            update_values = {"is_deprecated": True}
            if "superseded_by" in self.table.schema.names:
                update_values["superseded_by"] = clean_sub
            self.table.update(where=f"id = '{clean_id}'", values=update_values)
            logger.info(f"Deprecated memory record '{record_id}' (superseded by '{superseded_by}')")

            if sync_to_jsonl:
                try:
                    from cephalo.core.preference_reconciler import PreferenceReconciler
                    PreferenceReconciler.sync_deprecation_to_jsonl(record_id, superseded_by=superseded_by)
                except Exception as sync_err:
                    logger.debug(f"Could not sync deprecation to jsonl: {sync_err}")

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

    def delete_records(self, ids: Set[str] | List[str]) -> int:
        """Deletes records by ID from the LanceDB table."""
        if not ids or self.table.count_rows() == 0:
            return 0
        deleted_count = 0
        try:
            id_list = list(ids)
            chunk_size = 50
            for i in range(0, len(id_list), chunk_size):
                chunk = id_list[i : i + chunk_size]
                escaped_chunk = [cid.replace("'", "''") for cid in chunk]
                formatted_ids = ", ".join(f"'{c}'" for c in escaped_chunk)
                self.table.delete(f"id IN ({formatted_ids})")
                deleted_count += len(chunk)
            # Also purge any legacy records with blank/empty content
            if "content" in self.table.schema.names:
                self.table.delete("content = '' OR content IS NULL")
        except Exception as e:
            logger.warning(f"Error during LanceDB deletion: {e}")
        return deleted_count

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
            if "superseded_by" not in rec or rec["superseded_by"] is None:
                rec["superseded_by"] = ""
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

        # 1. Hybrid Search (Dense Vector + BM25 Full-Text with Semantic Weighting)
        if query_type.lower() == "hybrid" and query_vector is not None and query_text:
            try:
                self.ensure_fts_index("content")
                builder = (
                    self.table.search(query_type="hybrid")
                    .vector(query_vector)
                    .text(query_text)
                )
                try:
                    from lancedb.rerankers import LinearCombinationReranker
                    builder = builder.rerank(LinearCombinationReranker(weight=0.8))
                except Exception:
                    pass

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
