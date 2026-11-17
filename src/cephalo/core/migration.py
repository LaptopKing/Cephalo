"""
Cephalo Migration & Portability Engine (migration.py)
Single-command, zero-loss, encrypted/compressed migration package manager.
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import os
import platform
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cephalo.config import DATA_DIR, PROFILE_FILE, ROOT_DIR
from cephalo.core.migration_manifest import (
    CompressionFormat,
    FileEntry,
    HarnessDetector,
    MigrationManifest,
    MigrationScope,
    compute_bytes_sha256,
    compute_sha256,
    should_exclude,
)
from cephalo.core.migration_planner import MigrationPlanner
from cephalo.core.migration_restore import MigrationRestorer

logger = logging.getLogger("cephalo.core.migration")

class MigrationManager(MigrationPlanner):
    """Orchestrates migration creation, inspection, and restoration."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or ROOT_DIR).resolve()
        self.data_dir = self.base_dir / "data"
        self.migrations_dir = self.data_dir / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # EXPORT (PACK)
    # -------------------------------------------------------------------------
    def create_migration(
        self,
        scope: MigrationScope = MigrationScope.SETTINGS,
        output_path: Optional[Path] = None,
        compression_format: CompressionFormat = CompressionFormat.XZ,
        include_build_artifacts: bool = False,
        include_secrets: bool = False,
        preset: int = 6,
        fast: bool = False,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        Creates a complete, lossless, compressed migration archive via direct streaming.

        Args:
            scope: MigrationScope.SETTINGS (settings only) or MigrationScope.ALL (everything)
            output_path: Destination path for the archive file (optional)
            compression_format: XZ (default, highest ratio), GZ, or ZIP
            include_build_artifacts: Whether to include build dirs like target/ or .venv
            preset: LZMA compression preset (0-9, default: 6 for balanced maximum throughput)
            fast: If True, uses preset 3 for ultra-fast exports
            comment: Optional comment or description embedded in manifest
        """
        start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        scope_str = scope.value if isinstance(scope, MigrationScope) else str(scope)
        fmt_str = compression_format.value if isinstance(compression_format, CompressionFormat) else str(compression_format)

        if fast:
            preset = 1

        if not output_path:
            ext = f".cephalo.tar.{fmt_str}" if fmt_str in ("xz", "gz") else f".cephalo.{fmt_str}"
            filename = f"cephalo-migration-{timestamp}-{scope_str}{ext}"
            output_path = self.migrations_dir / filename
        else:
            output_path = Path(output_path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initiating Cephalo migration export: scope={scope_str}, format={fmt_str}, preset={preset}, target={output_path}")

        # Lightweight temporary directory only for clean atomic SQLite snapshots
        with tempfile.TemporaryDirectory(prefix="cephalo_mig_sqlite_") as temp_db_str:
            temp_db_dir = Path(temp_db_str)
            planned_items: List[Tuple[Path, str, str]] = []

            # 1. Plan Cephalo Core
            self._plan_cephalo_core(
                planned_items=planned_items,
                scope=scope,
                include_build_artifacts=include_build_artifacts,
                include_secrets=include_secrets,
                temp_dir=temp_db_dir,
            )

            # 2. Plan Multi-Harness
            harnesses = self._plan_harnesses(
                planned_items=planned_items,
                scope=scope,
                include_build_artifacts=include_build_artifacts,
            )

            # 3. Plan Projects (if ALL)
            projects: List[str] = []
            if scope == MigrationScope.ALL:
                projects = self._plan_projects(
                    planned_items=planned_items,
                    include_build_artifacts=include_build_artifacts,
                )

            # 4. Multi-threaded Parallel Hashing
            file_entries, valid_items = self._hash_planned_items(planned_items)

            manifest = MigrationManifest(
                version="1.0.0",
                cephalo_version="1.1.0",
                scope=scope_str,
                format=fmt_str,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_host=platform.node(),
                source_os=f"{sys.platform} ({platform.platform()})",
                source_python=sys.version.split()[0],
                source_cephalo_dir=str(self.base_dir),
                total_files=len(file_entries),
                total_uncompressed_bytes=sum(f.size for f in file_entries),
                harnesses_detected=list(harnesses.keys()),
                projects_detected=projects,
                files=[f.to_dict() for f in file_entries],
            )

            manifest_bytes = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False).encode("utf-8")

            # 5. Direct Streaming to Compressed Archive (Manifest First!)
            self._stream_to_archive(
                output_path=output_path,
                manifest_bytes=manifest_bytes,
                valid_items=valid_items,
                compression_format=compression_format,
                preset=preset,
            )

        duration = time.time() - start_time
        compressed_size = output_path.stat().st_size
        ratio = (1.0 - (compressed_size / max(manifest.total_uncompressed_bytes, 1))) * 100.0

        logger.info(
            f"Migration archive created successfully in {duration:.2f}s: "
            f"{manifest.total_uncompressed_bytes:,} bytes -> {compressed_size:,} bytes "
            f"({ratio:.1f}% reduction) at {output_path}"
        )

        return {
            "status": "success",
            "archive_path": str(output_path),
            "scope": scope_str,
            "format": fmt_str,
            "files_count": manifest.total_files,
            "uncompressed_bytes": manifest.total_uncompressed_bytes,
            "compressed_bytes": compressed_size,
            "compression_ratio_pct": round(ratio, 2),
            "duration_seconds": round(duration, 2),
            "harnesses": manifest.harnesses_detected,
            "projects": manifest.projects_detected,
            "created_at": manifest.created_at,
        }

    def _stream_to_archive(
        self,
        output_path: Path,
        manifest_bytes: bytes,
        valid_items: List[Tuple[Path, str, str]],
        compression_format: CompressionFormat,
        preset: int = 6,
    ) -> None:
        """Compresses planned items directly into archive with manifest as first entry."""
        fmt = compression_format.value if isinstance(compression_format, CompressionFormat) else str(compression_format)

        if fmt in ("xz", "gz"):
            mode = f"w:{fmt}"
            kwargs: Dict[str, Any] = {}
            if fmt == "xz":
                kwargs["preset"] = preset
            else:
                kwargs["compresslevel"] = 6

            with tarfile.open(output_path, mode=mode, **kwargs) as tar:
                # 1. Manifest FIRST for instant inspection
                ti = tarfile.TarInfo(name="manifest.json")
                ti.size = len(manifest_bytes)
                ti.mtime = int(time.time())
                ti.mode = 0o644
                tar.addfile(ti, io.BytesIO(manifest_bytes))

                # 2. Files streamed directly
                for src_f, arc_f, _ in valid_items:
                    try:
                        tar.add(src_f, arcname=arc_f)
                    except (PermissionError, OSError) as e:
                        logger.warning(f"Skipping file during archiving {src_f}: {e}")
        elif fmt == "zip":
            # Multi-threaded parallel zip compression for ultra-fast exports
            workers = min(32, (os.cpu_count() or 4) * 2)
            with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                zf.writestr("manifest.json", manifest_bytes)

                def _compress_file(item: Tuple[Path, str, str]) -> Optional[Tuple[str, Optional[bytes], int, int]]:
                    src_f, arc_f, _ = item
                    try:
                        if not src_f.exists() or not src_f.is_file():
                            return None
                        st = src_f.stat()
                        # For files under 64MB, compress in parallel thread
                        if st.st_size > 64 * 1024 * 1024:
                            return (arc_f, None, st.st_size, 0)
                        data = src_f.read_bytes()
                        compressed = zlib.compress(data, 6)
                        crc = zlib.crc32(data)
                        return (arc_f, compressed, len(data), crc)
                    except Exception as e:
                        logger.warning(f"Error reading file for zip {src_f}: {e}")
                        return None

                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    for res in executor.map(_compress_file, valid_items):
                        if res is not None:
                            arc_f, comp_data, orig_size, crc = res
                            if comp_data is not None:
                                zinfo = zipfile.ZipInfo(filename=arc_f, date_time=time.localtime(time.time())[:6])
                                zinfo.compress_type = zipfile.ZIP_DEFLATED
                                zinfo.file_size = orig_size
                                zinfo.compress_size = len(comp_data)
                                zinfo.CRC = crc
                                zf.writestr(zinfo, comp_data)
                            else:
                                for src_orig, arc_orig, _ in valid_items:
                                    if arc_orig == arc_f:
                                        zf.write(src_orig, arcname=arc_orig)
                                        break
        else:
            raise ValueError(f"Unsupported compression format: {fmt}")

    # -------------------------------------------------------------------------
    # INSPECT
    # -------------------------------------------------------------------------
    def _read_manifest_from_archive(self, archive_path: Path) -> Dict[str, Any]:
        return MigrationRestorer(self)._read_manifest_from_archive(archive_path)

    def _merge_hooks_json(self, *args, **kwargs) -> Any:
        return MigrationRestorer(self)._merge_hooks_json(*args, **kwargs)

    def _merge_mcp_config_json(self, *args, **kwargs) -> Any:
        return MigrationRestorer(self)._merge_mcp_config_json(*args, **kwargs)

    def inspect_migration(self, archive_path: Path) -> Dict[str, Any]:
        """
        Inspects a migration archive without extracting its contents.
        Reads the manifest and returns metadata, statistics, and file listing.
        """
        archive_path = Path(archive_path).resolve()
        if not archive_path.exists():
            raise FileNotFoundError(f"Migration archive not found: {archive_path}")

        manifest_data = self._read_manifest_from_archive(archive_path)
        stat = archive_path.stat()
        manifest_data["archive_path"] = str(archive_path)
        manifest_data["compressed_size_bytes"] = stat.st_size
        manifest_data["compressed_size_formatted"] = self._format_bytes(stat.st_size)

        uncompressed = manifest_data.get("total_uncompressed_bytes", 0)
        if uncompressed > 0:
            ratio = (1.0 - (stat.st_size / uncompressed)) * 100.0
            manifest_data["compression_ratio"] = f"{ratio:.1f}% reduction"
        else:
            manifest_data["compression_ratio"] = "N/A"

        return manifest_data

    # -------------------------------------------------------------------------
    # RESTORE (IMPORT & SETUP)
    # -------------------------------------------------------------------------

    def restore_migration(
        self,
        archive_path: Path,
        dry_run: bool = False,
        auto_backup: bool = True,
        target_cephalo_dir: Optional[Path] = None,
        only_cephalo: bool = False,
        only_harnesses: bool = False,
    ) -> Dict[str, Any]:
        restorer = MigrationRestorer(self)
        return restorer.restore_migration(
            archive_path=archive_path,
            dry_run=dry_run,
            auto_backup=auto_backup,
            target_cephalo_dir=target_cephalo_dir,
            only_cephalo=only_cephalo,
            only_harnesses=only_harnesses,
        )

    def list_migrations(self) -> List[Dict[str, Any]]:
        """Scans the default migrations directory and returns all available migration archives."""
        if not self.migrations_dir.exists():
            return []

        results = []
        for item in sorted(self.migrations_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if item.is_file() and item.name.endswith((".cephalo.tar.xz", ".cephalo.tar.gz", ".cephalo.zip", ".tar.xz", ".tar.gz", ".zip")):
                try:
                    info = self.inspect_migration(item)
                    results.append({
                        "filename": item.name,
                        "path": str(item),
                        "size_bytes": info.get("compressed_size_bytes", 0),
                        "size_formatted": info.get("compressed_size_formatted", "0 B"),
                        "scope": info.get("scope", "unknown"),
                        "created_at": info.get("created_at", ""),
                        "files_count": info.get("total_files", 0),
                        "harnesses": info.get("harnesses_detected", []),
                        "projects": info.get("projects_detected", []),
                    })
                except Exception as e:
                    results.append({
                        "filename": item.name,
                        "path": str(item),
                        "size_bytes": item.stat().st_size,
                        "size_formatted": self._format_bytes(item.stat().st_size),
                        "scope": "unknown",
                        "error": str(e),
                    })
        return results

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        """Formats byte count into human-readable string (KB, MB, GB)."""
        val = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if val < 1024.0 or unit == "TB":
                return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
            val /= 1024.0
        return f"{num_bytes} B"


__all__ = [
    "MigrationScope",
    "CompressionFormat",
    "FileEntry",
    "MigrationManifest",
    "HarnessDetector",
    "MigrationManager",
    "compute_sha256",
    "should_exclude",
]
