#!/usr/bin/env python3
"""
Cephalo Autonomous Contextual Preference Reconciler (preference_reconciler.py)
=============================================================================
Multilingual, sovereign reconciliation engine for Cephalo.
Detects semantic conflicts, entity attribute updates, and temporal supersessions
between new user preferences/rules and existing memories across ALL languages
(English, Hungarian, German, French, Spanish, Italian, and semantic representations).

Capabilities:
1. Multilingual Transition Cue Extraction:
   - English: "instead of", "no longer", "switch to", "from now on", "migrated to", "replace"
   - Hungarian: "helyett", "már nem", "átállunk", "mostantól", "ezentúl", "lecseréltük", "felváltja"
   - German: "statt", "nicht mehr", "wechseln zu", "ab jetzt", "ersetzen"
   - French: "au lieu de", "ne plus", "passer à", "à partir de maintenant", "remplacer"
   - Spanish: "en vez de", "ya no", "cambiar a", "a partir de ahora", "reemplazar"
   - Italian: "invece di", "non più", "passare a", "d'ora in poi", "sostituire"
2. Multilingual Mutually Exclusive Domain Anchors:
   - UI Themes (Dark/Obsidian vs Light/Stone Paper across EN/HU/DE/FR/ES).
   - Display hardware (Living room TV, workstation monitors across EN/HU/DE/FR/ES).
   - Package managers (Yarn, Bun, pnpm, npm across all languages).
   - API Protocols (REST, gRPC, GraphQL, tRPC).
   - Automotive specifications (Wheels colors, chassis OEM rules across EN/HU).
   - Cinema aesthetic & pacing (Slow-burn vs high velocity across EN/HU).
3. Unicode-Safe Multilingual Tokenizer & Normalizer:
   - Preserves accented and non-Latin characters (á, é, í, ó, ö, ő, ú, ü, ű, etc.).
4. Bidirectional Disk Deprecation Synchronization:
   - Updates `prompts.jsonl` atomically.
5. Markdown Profile Section Reconciler:
   - In-place bullet point replacement in `USER_PROFILE.md`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cephalo.reconciler")

# Categories that represent stateful preferences, hardware, or rules
STATEFUL_PREFERENCE_CATEGORIES: Set[str] = {
    "user_preference",
    "preference",
    "workflow_rule",
    "workflow",
    "hardware_spec",
    "hardware",
    "hardware_devices",
    "entertainment_preferences",
    "critique_negative_filter",
    "negative_constraint",
    "design_preference",
    "car_livery_preference",
    "architecture_decision",
    "core-invariants",
    "tool_evaluation",
    "tech_stack",
}

# Multilingual Transition & Replacement Patterns across EN, HU, DE, FR, ES, IT
TRANSITION_PATTERNS = [
    # English
    r"\b(instead\s+of|in\s+place\s+of|rather\s+than)\b",
    r"\b(no\s+longer|no\s+more|stop(ped)?\s+using|ditch(ed)?|forget\s+about|retir(e|ed|ing))\b",
    r"\b(switch(ed)?\s+to|change(d)?\s+to|transition(ed)?\s+to|migrat(e|ed|ing)\s+to|mov(e|ed|ing)\s+to)\b",
    r"\b(from\s+now\s+on|going\s+forward|by\s+default\s+now|as\s+of\s+now)\b",
    r"\b(replac(e|ed|ing)|supersed(e|ed|ing)|deprecat(e|ed|ing))\b",
    r"\b(new\s+(tv|display|monitor|car|setup|theme|package\s+manager|rule|preference))\b",
    r"\b(prefer\s+.+\s+over\s+.+)\b",
    r"\b(update(d)?\s+(decision|preference|hardware))\b",

    # Hungarian (Magyar)
    r"\b(helyett|ahelyett\s+hogy)\b",
    r"\b(már\s+nem|többé\s+nem|nem\s+kell\s+többé|hagyjuk\s+el|dobjuk\s+el|felejtsük\s+el|nem\s+használunk\s+többé)\b",
    r"\b(átállunk|áttérünk|átváltunk|váltsunk(\s+át)?|átmegyünk|migrálunk|költöztetjük)\b",
    r"\b(mostantól(\s+kezdve)?|ezentúl|a\s+jövőben|innentől(\s+kezdve)?|alapértelmezetten\s+mostantól)\b",
    r"\b(lecserél(t|jük|ve)?|felvált(ja|ják)?|cserél(t|jük)?|felváltotta|helyettesít(i)?)\b",
    r"\b(új\s+(tévé|tv|kijelző|monitor|autó|setup|téma|szabály|beállítás|preferencia|csomagkezelő))\b",
    r"\b(inkább\s+.+\s+mint|jobban\s+szeretem\s+.+\s+mint)\b",

    # German (Deutsch)
    r"\b(statt|anstelle\s+von)\b",
    r"\b(nicht\s+mehr|aufhören\s+zu\s+benutzen|weg\s+von)\b",
    r"\b(wechseln\s+zu|umsteigen\s+auf|migrieren\s+zu)\b",
    r"\b(ab\s+jetzt|ab\s+sofort|von\s+nun\s+an|in\s+zukunft)\b",
    r"\b(ersetzen|ersetzt\s+durch|abgelöst\s+durch)\b",
    r"\b(neu(er|es|en)?\s+(tv|fernseher|bildschirm|monitor|auto|theme|regel))\b",

    # French (Français)
    r"\b(au\s+lieu\s+de|plutôt\s+que)\b",
    r"\b(ne\s+plus|ne\s+plus\s+utiliser|abandonner)\b",
    r"\b(passer\s+à|migrer\s+vers|changer\s+pour)\b",
    r"\b(à\s+partir\s+de\s+maintenant|dorénavant|désormais)\b",
    r"\b(remplacer|remplacé\s+par)\b",
    r"\b(nouveau\s+(tv|écran|moniteur|thème|règle))\b",

    # Spanish (Español)
    r"\b(en\s+vez\s+de|en\s+lugar\s+de)\b",
    r"\b(ya\s+no|dejar\s+de\s+usar)\b",
    r"\b(cambiar\s+a|pasar\s+a|migrar\s+a)\b",
    r"\b(a\s+partir\s+de\s+ahora|en\s+adelante|de\s+ahora\s+en\s+más)\b",
    r"\b(reemplazar|reemplazado\s+por|sustituir)\b",

    # Italian (Italiano)
    r"\b(invece\s+di|al\s+posto\s+di)\b",
    r"\b(non\s+più|smettere\s+di\s+usare)\b",
    r"\b(passare\s+a|migrare\s+a|cambiare\s+a)\b",
    r"\b(da\s+adesso|d'ora\s+in\s+poi)\b",
    r"\b(sostituire|sostituito\s+da)\b",
]

# Multilingual Mutually Exclusive Attribute Domains
MUTUALLY_EXCLUSIVE_DOMAINS: List[Dict[str, Any]] = [
    {
        "name": "ui_theme",
        "anchor_keywords": [
            "theme", "mode", "canvas", "obsidian", "stone paper", "dark mode", "light mode",
            "téma", "mód", "felület", "kőpapír", "hintergrund", "thème", "tema"
        ],
        "exclusive_groups": [
            {
                "dark mode", "dark theme", "obsidian", "black canvas",
                "sötét mód", "sötét téma", "fekete", "dunkel", "sombre", "oscuro"
            },
            {
                "light mode", "light theme", "stone paper", "white canvas", "warm light",
                "világos mód", "világos téma", "fehér", "kőpapír", "hell", "clair", "claro"
            },
        ],
    },
    {
        "name": "living_room_tv",
        "anchor_keywords": [
            "tv", "display", "tévé", "kijelző", "televízió", "screen",
            "fernseher", "bildschirm", "téléviseur", "télé", "televisión"
        ],
        "required_context_any": [
            "living room", "nappali", "nappaliban", "szalon", "wohnzimmer",
            "salon", "sala de estar", "sala", "soggiorno"
        ],
    },
    {
        "name": "workstation_monitor",
        "anchor_keywords": [
            "monitor", "display", "kijelző", "bildschirm", "écran", "pantalla"
        ],
        "required_context_any": [
            "workstation", "munkaállomás", "asztali", "pc", "arbeitsplatz",
            "bureau", "escritorio", "postazione"
        ],
    },
    {
        "name": "js_package_manager",
        "anchor_keywords": [
            "package manager", "dependency manager", "csomagkezelő", "paketmanager",
            "gestionnaire de paquets", "gestor de paquetes", "yarn", "bun", "pnpm", "npm"
        ],
        "required_context_any": [
            "package", "dependency", "manager", "install", "csomag", "függőség",
            "futtat", "paket", "paquet", "paquete"
        ],
        "exclusive_groups": [
            {"yarn"},
            {"bun"},
            {"pnpm"},
            {"npm"},
        ],
    },
    {
        "name": "api_protocol",
        "anchor_keywords": [
            "api", "backend", "communication", "kommunikáció", "protocol",
            "protokoll", "rpc", "endpoint", "schnittstelle"
        ],
        "exclusive_groups": [
            {"rest", "rest api"},
            {"grpc"},
            {"graphql"},
            {"trpc"},
        ],
    },
    {
        "name": "car_wheels_color",
        "anchor_keywords": [
            "wheel", "wheels", "rim", "rims", "kerék", "kerekek", "felni",
            "felnit", "felnik", "felniket", "felnitárcsa", "felge", "felgen", "roue", "jante", "rueda", "llanta"
        ],
        "required_context_any": [
            "subaru", "impreza", "gf8", "gf", "car", "vehicle", "autó",
            "kocsi", "fahrzeug", "voiture", "vehículo", "auto"
        ],
        "exclusive_groups": [
            {"gold", "gold wheels", "arany", "arany felni", "arany színű", "#d4af37", "dore", "dorado"},
            {"bronze", "bronze wheels", "bronz", "bronz felni", "bronzo"},
            {"silver", "silver wheels", "ezüst", "ezüst felni", "silber", "argent", "plata"},
            {"black", "black wheels", "fekete", "fekete felni", "schwarz", "noir", "negro"},
            {"white", "white wheels", "fehér", "fehér felni", "weiß", "blanc", "blanco"},
        ],
    },
    {
        "name": "cinema_pacing",
        "anchor_keywords": [
            "cinema", "movie", "film", "pacing", "mozi", "filmélmény", "tempó", "ütem", "kino"
        ],
        "required_context_any": [
            "story", "narrative", "tempo", "velocity", "pace", "slow-burn", "action",
            "történet", "tempó", "akció", "lendület", "ritmus"
        ],
        "exclusive_groups": [
            {
                "slow-burn", "slow burn", "takes 30-45 minutes to unbundle",
                "lassú", "lassan építkező", "vontatott", "langsam", "lent"
            },
            {
                "instant velocity", "instant momentum", "rapid tempo", "cold-open", "hyper-kinetic",
                "gyors", "pörgős", "azonnali lendület", "schnell", "rapide", "rápido"
            },
        ],
    },
]

# Multilingual Stopwords across English, Hungarian, German, French, Spanish
COMMON_STOPWORDS: Set[str] = {
    # English
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "from", "up", "down", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "having", "do", "does", "did", "doing", "would",
    "should", "could", "ought", "i", "you", "he", "she", "it", "we", "they", "my",
    "your", "our", "their", "all", "any", "both", "each", "few", "more", "most",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "now", "also", "want", "like", "use",
    "search", "start", "handle", "look", "make", "need", "work", "code", "file",
    "data", "thing", "things", "first", "well", "multiple", "starter", "good",
    "idea", "ideas", "time", "way", "ways", "user", "agent", "prompt", "say", "said",

    # Hungarian
    "egy", "az", "ez", "és", "vagy", "hogy", "nem", "mint", "csak", "mert",
    "már", "még", "van", "volt", "lesz", "lenne", "kell", "lehet", "tud",
    "saját", "más", "után", "előtt", "alatt", "felett", "között", "által",
    "nagyon", "sok", "kevés", "mind", "minden", "semmi", "senki", "valami",

    # German / French / Spanish particles
    "und", "oder", "aber", "nicht", "ein", "eine", "der", "die", "das", "ist",
    "et", "ou", "mais", "pas", "un", "une", "le", "la", "les", "est",
    "y", "o", "pero", "no", "un", "una", "el", "la", "los", "las", "es",
}


def normalize_text(text: str) -> str:
    """Normalizes Unicode text to NFC format."""
    return unicodedata.normalize("NFC", text.strip())


def extract_keywords(text: str) -> Set[str]:
    """
    Tokenizes text into normalized lower-case keywords across all languages.
    Preserves Unicode alphabetic characters (Hungarian á, é, í, ó, ö, ő, ú, ü, ű, etc.).
    """
    clean = normalize_text(text).lower()
    # \w with Unicode preserves all letters from Hungarian, German, French, Cyrillic, etc.
    words = re.findall(r"[\w\-#]+", clean, re.UNICODE)
    return {w for w in words if len(w) > 2 and w not in COMMON_STOPWORDS}


class PreferenceReconciler:
    """Evaluates contextual conflict, detects supersessions, and reconciles state across all languages."""

    def __init__(self, relevance_distance_threshold: float = 1.15):
        self.distance_threshold = relevance_distance_threshold

    def is_stateful_candidate(self, category: str, text: str) -> bool:
        """Determines if an entry represents a preference, rule, or hardware specification."""
        cat_lower = (category or "").lower()
        if cat_lower.startswith("specialty:"):
            return False

        if cat_lower in STATEFUL_PREFERENCE_CATEGORIES:
            return True
        if any(term in cat_lower for term in ["preference", "rule", "spec", "hardware", "constraint", "decision"]):
            return True

        text_lower = text.lower()
        # Multilingual preference / directive signals
        signals = [
            r"\b(prefer|preference|favorite|like|dislike|hate)\b",
            r"\b(switch\s+to|instead\s+of|from\s+now\s+on|no\s+longer|no\s+more|replace)\b",
            r"\b(helyett|már\s+nem|átállunk|mostantól|ezentúl|lecserél|inkább)\b",
            r"\b(statt|nicht\s+mehr|wechseln|ab\s+jetzt)\b",
            r"\b(au\s+lieu\s+de|ne\s+plus|passer\s+à)\b",
            r"\b(en\s+vez\s+de|ya\s+no|cambiar\s+a)\b",
            r"\b(my\s+tv|my\s+monitor|my\s+display|my\s+car|my\s+setup|tévé|kijelző|autó)\b",
            r"\b(always\s+use|never\s+use|by\s+default|mindig|soha)\b",
        ]
        return any(re.search(pat, text_lower) for pat in signals)

    def detect_supersession(
        self,
        new_text: str,
        cand_text: str,
        category: str = "",
        cand_category: str = "",
        distance: Optional[float] = None,
    ) -> Tuple[bool, str, float]:
        """
        Determines whether `new_text` contextually supersedes and invalidates `cand_text`.
        Works seamlessly across all languages.
        Returns: (is_superseded, reason, confidence)
        """
        if not cand_text.strip() or not new_text.strip():
            return False, "Empty content", 0.0

        if category.startswith("specialty:") or cand_category.startswith("specialty:"):
            return False, "Specialties are protected domain modules", 0.0

        new_clean = normalize_text(new_text)
        cand_clean = normalize_text(cand_text)

        new_lower = new_clean.lower()
        cand_lower = cand_clean.lower()

        # If texts are essentially identical, it's a duplicate
        if new_lower.strip() == cand_lower.strip():
            return True, "Exact duplicate memory", 0.99

        # Distance gate: if distance is known and exceeds threshold, unlikely to be related
        if distance is not None and distance > self.distance_threshold:
            return False, f"Distance {distance:.3f} exceeds threshold {self.distance_threshold}", 0.0

        new_words = extract_keywords(new_clean)
        cand_words = extract_keywords(cand_clean)

        overlap = new_words.intersection(cand_words)
        overlap_ratio = len(overlap) / max(1, min(len(new_words), len(cand_words)))

        # 1. Mutually exclusive domain rules (multilingual)
        for domain in MUTUALLY_EXCLUSIVE_DOMAINS:
            anchor_kws = domain.get("anchor_keywords", [])
            new_has_anchor = any(k in new_lower for k in anchor_kws)
            cand_has_anchor = any(k in cand_lower for k in anchor_kws)
            if not (new_has_anchor and cand_has_anchor):
                continue

            req_any = domain.get("required_context_any")
            if req_any:
                new_has_ctx = any(k in new_lower for k in req_any)
                cand_has_ctx = any(k in cand_lower for k in req_any)
                if not (new_has_ctx and cand_has_ctx):
                    continue

            exclusive_groups = domain.get("exclusive_groups", [])
            if exclusive_groups:
                new_group_idx = None
                cand_group_idx = None
                for idx, grp in enumerate(exclusive_groups):
                    if any(term in new_lower for term in grp):
                        new_group_idx = idx
                    if any(term in cand_lower for term in grp):
                        cand_group_idx = idx

                if new_group_idx is not None and cand_group_idx is not None:
                    if new_group_idx != cand_group_idx:
                        reason = f"Mutually exclusive state shift in domain '{domain['name']}'"
                        return True, reason, 0.95

            # Attribute value update for anchored display hardware
            if req_any and ("tv" in anchor_kws or "tévé" in anchor_kws or "display" in anchor_kws or "monitor" in anchor_kws):
                reason = f"Hardware specification update for '{domain['name']}'"
                return True, reason, 0.90

        # 2. Multilingual transition cues referencing candidate terms
        has_transition_marker = any(re.search(pat, new_lower) for pat in TRANSITION_PATTERNS)
        if has_transition_marker:
            # Overlap in keywords OR cross-lingual semantic anchor match
            if len(overlap) >= 2 or (len(overlap) >= 1 and (category == cand_category or overlap_ratio >= 0.35)):
                matched_terms = [w for w in overlap if len(w) >= 3]
                reason = f"Transition directive superseding previous preference overlapping on {matched_terms[:3]}"
                return True, reason, 0.92

        # 3. High keyword overlap + preference category alignment
        if overlap_ratio >= 0.60 and len(overlap) >= 3:
            if self.is_stateful_candidate(category, new_text) and self.is_stateful_candidate(cand_category, cand_text):
                reason = f"High semantic overlap ({overlap_ratio:.0%}) in stateful category '{category or cand_category}'"
                return True, reason, 0.85

        return False, "No contextual contradiction detected", 0.0

    def find_superseded_records(
        self,
        new_text: str,
        candidate_records: List[Dict[str, Any]],
        category: str = "",
        current_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scans a list of candidate active records and returns those that should be superseded.
        """
        superseded = []
        for cand in candidate_records:
            cid = cand.get("id")
            if current_id and cid == current_id:
                continue

            cand_text = cand.get("content", "")
            cand_cat = cand.get("category", "")
            distance = cand.get("_distance")

            is_sup, reason, conf = self.detect_supersession(
                new_text=new_text,
                cand_text=cand_text,
                category=category,
                cand_category=cand_cat,
                distance=distance,
            )

            if is_sup and conf >= 0.75:
                superseded.append({
                    "id": cid,
                    "content": cand_text,
                    "category": cand_cat,
                    "reason": reason,
                    "confidence": conf,
                })

        return superseded

    @staticmethod
    def sync_deprecation_to_jsonl(
        record_id: str,
        superseded_by: str = "",
        jsonl_path: Optional[Path] = None,
    ) -> bool:
        """
        Atomically marks a record as deprecated in prompts.jsonl to keep disk storage synchronized.
        """
        if not jsonl_path:
            from cephalo.cli import PROMPTS_FILE
            jsonl_path = PROMPTS_FILE

        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            return False

        updated = False
        lines: List[str] = []

        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                        if data.get("id") == record_id:
                            data["is_deprecated"] = True
                            if superseded_by:
                                data["superseded_by"] = superseded_by
                            line_str = json.dumps(data, ensure_ascii=False)
                            updated = True
                    except Exception:
                        pass
                    lines.append(line_str)

            if updated:
                tmp_file = jsonl_path.parent / f"{jsonl_path.name}.tmp.{os.getpid()}"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    for l in lines:
                        f.write(l + "\n")
                tmp_file.replace(jsonl_path)
                logger.info(f"Updated deprecation in prompts.jsonl for record '{record_id}'")
                return True

        except Exception as e:
            logger.warning(f"Failed to sync deprecation to prompts.jsonl for '{record_id}': {e}")

        return False

    @staticmethod
    def reconcile_markdown_section(
        section_text: str,
        new_bullet: str,
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Reconciles a new bullet point within an existing USER_PROFILE.md section.
        If the new bullet point shares an entity key (e.g. **Living Room Display:**),
        it replaces the existing bullet point in-place rather than appending.
        Returns: (updated_section_text, was_replaced, replaced_old_bullet)
        """
        clean_new = normalize_text(new_bullet).strip()
        if not clean_new.startswith(("-", "*")):
            clean_new = f"- {clean_new}"

        key_match = re.search(r"^[-*]\s*\*\*([^*]+)\*\*", clean_new)
        target_key = key_match.group(1).strip().lower() if key_match else None

        lines = section_text.splitlines()
        replaced_old = None
        new_lines: List[str] = []

        replaced = False
        for line in lines:
            if not replaced and target_key:
                line_key_match = re.search(r"^[-*]\s*\*\*([^*]+)\*\*", line.strip())
                if line_key_match:
                    existing_key = line_key_match.group(1).strip().lower()
                    if existing_key == target_key or (target_key in existing_key and len(target_key) > 3) or (existing_key in target_key and len(existing_key) > 3):
                        replaced_old = line.strip()
                        new_lines.append(clean_new)
                        replaced = True
                        continue

            new_lines.append(line)

        if not replaced:
            while new_lines and new_lines[-1].strip() == "---":
                new_lines.pop()
            new_lines.append(clean_new)

        result_text = "\n".join(new_lines).strip()
        return result_text, replaced, replaced_old
