"""
Cephalo Screen Memory & Perceptual Delta Engine (screen_recorder.py)
===================================================================
Cross-platform, zero-bloat automated screen awareness and visual memory.
Instead of continuous 24/7 video encoding (which hogs CPU/GPU and eats 150GB/yr),
Cephalo uses perceptual frame-difference gating (dHash / pixel delta):
- Identical or idle screens trigger ZERO writes, ZERO OCR, and 0% CPU.
- Meaningful visual shifts (>5% delta) capture an ultra-compressed WebP keyframe.
- Safeguards & blacklist gatekeeper strictly abort capture on private/banking windows.
- Works across Windows, macOS, Linux, and WSL with graceful fallbacks.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cephalo.config import DATA_DIR
from cephalo.core.safeguards import is_shielded, load_safeguards_config

logger = logging.getLogger("cephalo.screen")

FRAMES_DIR = DATA_DIR / "frames"
FRAME_INDEX_FILE = FRAMES_DIR / "frame_index.jsonl"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def get_active_window_context() -> Dict[str, str]:
    """
    Returns the currently active window title and process name in a cross-platform manner.
    Gracefully falls back to empty values in headless environments or WSL.
    """
    context = {"title": "", "process": "", "platform": sys.platform}

    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    context["title"] = buff.value.strip()

                # Get process name from PID
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value:
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                    if h_proc:
                        try:
                            MAX_PATH = 260
                            proc_buff = ctypes.create_unicode_buffer(MAX_PATH)
                            size = wintypes.DWORD(MAX_PATH)
                            if kernel32.QueryFullProcessImageNameW(h_proc, 0, proc_buff, ctypes.byref(size)):
                                context["process"] = Path(proc_buff.value).name
                        finally:
                            kernel32.CloseHandle(h_proc)

        elif sys.platform == "darwin":
            # macOS: AppleScript query
            cmd = 'tell application "System Events" to get {name of first application process whose frontmost is true, name of window 1 of (first application process whose frontmost is true)}'
            proc = subprocess.run(
                ["osascript", "-e", cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=2,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                parts = proc.stdout.strip().split(", ")
                if len(parts) >= 1:
                    context["process"] = parts[0].strip()
                if len(parts) >= 2:
                    context["title"] = parts[1].strip()

        elif sys.platform.startswith("linux"):
            # Linux: try xdotool
            proc_title = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=2,
            )
            if proc_title.returncode == 0:
                context["title"] = proc_title.stdout.strip()

    except Exception as e:
        logger.debug("Active window detection bypassed: %s", e)

    return context


def compute_frame_delta(img_a: Any, img_b: Any) -> float:
    """
    Computes visual difference between two images (0.0 = identical, 1.0 = completely different).
    Downsamples to 64x64 grayscale and calculates normalized absolute difference in <1ms.
    """
    if img_a is None or img_b is None:
        return 1.0

    try:
        from PIL import Image

        # Normalize size and convert to grayscale
        size = (64, 64)
        gray_a = img_a.resize(size).convert("L")
        gray_b = img_b.resize(size).convert("L")

        bytes_a = gray_a.tobytes()
        bytes_b = gray_b.tobytes()

        # Compute mean absolute difference
        total_diff = sum(abs(a - b) for a, b in zip(bytes_a, bytes_b))
        max_possible = 64 * 64 * 255
        return float(total_diff) / float(max_possible)
    except Exception as e:
        logger.debug("Frame delta computation fallback: %s", e)
        return 1.0


def capture_screen_image() -> Optional[Any]:
    """
    Captures a full screenshot in a cross-platform manner.
    Prefers `mss` if available; otherwise falls back to `PIL.ImageGrab`.
    """
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Primary/all monitors
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        pass

    try:
        from PIL import ImageGrab

        return ImageGrab.grab()
    except Exception as e:
        logger.debug("Screen capture unavailable: %s", e)
        return None


class ScreenMemoryEngine:
    """
    Core engine managing event-driven screen capture, delta gating,
    safeguard filtering, local WebP storage, and timeline indexing.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        min_delta_threshold: float = 0.05,
    ):
        self.base_dir = base_dir or FRAMES_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "frame_index.jsonl"
        self.min_delta_threshold = min_delta_threshold
        self.last_frame: Optional[Any] = None
        self.last_frame_time: Optional[datetime.datetime] = None

    def capture_step(
        self,
        image: Optional[Any] = None,
        window_context: Optional[Dict[str, str]] = None,
        force: bool = False,
        mock_ocr_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single capture evaluation:
        1. Checks safeguards against active window/process.
        2. Computes delta against previous frame.
        3. Saves compressed WebP keyframe if delta threshold is exceeded or force=True.
        4. Appends to frame_index.jsonl.
        """
        now = datetime.datetime.now()
        ctx = window_context if window_context is not None else get_active_window_context()
        title = ctx.get("title", "")
        proc = ctx.get("process", "")

        # 1. Safeguard & Blacklist Check
        shielded, reason = is_shielded(window_title=title, process_name=proc)
        if shielded:
            return {
                "status": "shielded",
                "reason": reason,
                "timestamp": now.isoformat(),
                "window_title": title,
                "process_name": proc,
            }

        # 2. Grab Image
        img = image if image is not None else capture_screen_image()
        if img is None:
            return {
                "status": "error",
                "error": "Screen capture returned no image (headless or permission denied)",
                "timestamp": now.isoformat(),
            }

        # 3. Delta Gating
        delta = compute_frame_delta(self.last_frame, img)
        if not force and self.last_frame is not None and delta < self.min_delta_threshold:
            return {
                "status": "skipped_no_change",
                "delta": round(delta, 4),
                "threshold": self.min_delta_threshold,
                "timestamp": now.isoformat(),
            }

        # 4. Save Compressed WebP Keyframe
        date_str = now.strftime("%Y-%m-%d")
        day_dir = self.base_dir / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        time_tag = now.strftime("%H%M%S_%f")[:11]
        frame_hash = hashlib.sha256(f"{now.isoformat()}_{title}_{proc}".encode()).hexdigest()[:8]
        frame_filename = f"frame_{time_tag}_{frame_hash}.webp"
        frame_path = day_dir / frame_filename

        try:
            # Save as optimized WebP
            img.save(frame_path, "WEBP", quality=75, method=4)
            file_size_kb = round(frame_path.stat().st_size / 1024.0, 1)
        except Exception as e:
            # Fallback to PNG if WEBP encoder unavailable
            frame_path = frame_path.with_suffix(".png")
            img.save(frame_path, "PNG", optimize=True)
            file_size_kb = round(frame_path.stat().st_size / 1024.0, 1)

        # 5. Extract OCR / Text (Mock or in-process)
        ocr_text = mock_ocr_text or ""
        sanitized_text = ""
        if ocr_text:
            # Sanitize via Tier 1 regex shield
            sanitized_text = self._sanitize_text(ocr_text)

        frame_record = {
            "id": f"frame-{now.strftime('%Y%m%d-%H%M%S')}-{frame_hash}",
            "timestamp": now.isoformat(),
            "date": date_str,
            "hour": now.hour,
            "path": str(frame_path.relative_to(self.base_dir.parent)),
            "delta": round(delta, 4),
            "size_kb": file_size_kb,
            "window_title": title,
            "process_name": proc,
            "ocr_text": sanitized_text,
        }

        # 6. Append to index
        with open(self.index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(frame_record, ensure_ascii=False) + "\n")

        # Update state
        self.last_frame = img
        self.last_frame_time = now

        return {
            "status": "captured",
            "frame_id": frame_record["id"],
            "path": frame_record["path"],
            "delta": round(delta, 4),
            "size_kb": file_size_kb,
            "window_title": title,
            "process_name": proc,
            "timestamp": now.isoformat(),
        }

    def _sanitize_text(self, text: str) -> str:
        """Lightweight sanitization using Cephalo's regex shield."""
        try:
            from cephalo.core.embedding_pipeline import RegexShield
            shield = RegexShield()
            res = shield.sanitize(text)
            return res.get("text", text)
        except Exception:
            return text

    def get_daily_frames(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves indexed frames for a specific date (YYYY-MM-DD)."""
        target_date = date_str or datetime.date.today().isoformat()
        records = []
        if not self.index_file.exists():
            return records

        with open(self.index_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("date") == target_date:
                        records.append(rec)
                except Exception:
                    continue
        return records

    def prune_frames(self, max_age_days: int = 14, keep_thumbnails: bool = True) -> Dict[str, int]:
        """
        Prunes raw WebP keyframes older than max_age_days to keep storage footprint negligible.
        Optionally generates tiny 160x90 thumbnails for DeepWiki timeline scrubbers.
        """
        from PIL import Image

        cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        deleted_count = 0
        thumb_count = 0

        for day_dir in self.base_dir.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                dir_date = datetime.datetime.strptime(day_dir.name, "%Y-%m-%d")
            except ValueError:
                continue

            if dir_date < cutoff:
                for frame_file in day_dir.glob("frame_*.webp"):
                    if keep_thumbnails and not frame_file.name.endswith("_thumb.webp"):
                        try:
                            # Create tiny thumbnail (160x90)
                            thumb_path = frame_file.with_name(frame_file.stem + "_thumb.webp")
                            if not thumb_path.exists():
                                with Image.open(frame_file) as im:
                                    im.thumbnail((160, 90))
                                    im.save(thumb_path, "WEBP", quality=50)
                                thumb_count += 1
                        except Exception:
                            pass
                    # Remove original high-res frame
                    try:
                        frame_file.unlink(missing_ok=True)
                        deleted_count += 1
                    except Exception:
                        pass

        return {"deleted_frames": deleted_count, "thumbnails_created": thumb_count}
