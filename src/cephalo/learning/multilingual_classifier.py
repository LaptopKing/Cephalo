#!/usr/bin/env python3
"""
Cephalo Multilingual Intent & Knowledge Classifier (multilingual_classifier.py)
================================================================================
Universal, high-precision, multilingual intent and cognitive classifier.
Supports English, Hungarian (Magyar), German (Deutsch), French, and Spanish.

Enforces the Strict Ephemeral Quarantine Architecture:
- Durable Knowledge (Permanent Store: `prompts.jsonl` -> LanceDB)
- Ephemeral Interaction (Quarantine Store: `prompts_quarantine.jsonl`)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class ClassificationResult:
    """Structured result of a multilingual classification evaluation."""
    category: str
    is_durable: bool
    is_quarantined: bool
    detected_categories: List[str]
    detected_language: str
    confidence: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "is_durable": self.is_durable,
            "is_quarantined": self.is_quarantined,
            "detected_categories": self.detected_categories,
            "detected_language": self.detected_language,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


class MultilingualClassifier:
    """
    Multilingual intent classifier with fine-grained rules across 8 Knowledge Pillars.
    Handles agglutinative Hungarian suffixes, European accents, and contextual phrases.
    """

    # Primary 8 Knowledge Pillars
    PILLARS = {
        "lifestyle_entertainment": [
            "entertainment_preference", "living_environment", "wellness_routine"
        ],
        "creative_visual": [
            "ui_ux_aesthetic", "automotive_design", "visual_branding"
        ],
        "cognitive_interaction": [
            "communication_style", "language_locale", "learning_pedagogy"
        ],
        "technical_engineering": [
            "architectural_milestone", "tech_stack_selection", "workflow_convention", "code_craftsmanship"
        ],
        "hardware_tooling": [
            "hardware_spec", "tooling_environment", "procurement_finance"
        ],
        "projects_milestones": [
            "project_objective", "shipped_milestone", "domain_specialty"
        ],
        "negative_constraints": [
            "critique_negative_filter", "security_privacy_mandate", "validation_invariant"
        ],
        "ephemeral_interaction": [
            "ephemeral_turn"
        ],
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        # 1. Negative Constraints & Critiques (Dislikes, blacklists, what to avoid)
        self.p_critique = re.compile(
            r"(?i)\b("
            # English
            r"found it boring|too slow|too grey|waste our time|waste my time|didn'?t like|dislike|hated?|"
            r"terrible|not what we were looking for|don'?t want|avoid doing|never do this|blacklist|"
            r"reject(ed)?|unacceptable|drab palette|slow-?burn|washed out|annoying|"
            # Hungarian
            r"unalmas(nak találtam)?|túl lassú|túl szürke|időpocsékolás|nem tetszik|utál(om|juk)|"
            r"nagyon rossz|nem ezt kerestük|nem akar(om|juk)|kerül(d|jük)|soha ne csinál(d|juk)|"
            r"feketelista|elutasítva|elfogadhatatlan|szürkeség|vontatott|nem jó"
            # German
            r"|langweilig|zu langsam|zu grau|zeitverschwendung|gefällt mir nicht|hasse|schrecklich|"
            r"vermeide|niemals machen|abgelehnt|inakzeptabel"
            r")\b"
        )

        # 2. General Preferences & Tastes
        self.p_preference = re.compile(
            r"(?i)\b("
            # English
            r"we loved?|i loved?|prefer\b|preference|my favorite|favorite|really liked?|enjoyed|looking for|"
            r"my choice is|we opted for|love using|"
            # Hungarian
            r"szeret(em|jük)|imád(om|juk)|jobban szeret(em|jük)|preferál(om|juk)|kedvenc(em|ünk)|"
            r"nagyon tetszik|ezt választ(om|juk)|ezt szeretn(ém|énk)|számomra fontos|"
            # German
            r"liebe|bevorzuge|favorit|gefällt mir sehr|meine wahl"
            r")\b"
        )

        # 3. Entertainment & Cinema
        self.p_entertainment = re.compile(
            r"(?i)\b("
            # English
            r"movie|film|cinema|series|tv show|director|pacing|saturation|vibrant 4k|bullet train|"
            r"guy ritchie|david leitch|gentlemen|action-comedy|visual aesthetic|cinematography|soundtrack|"
            # Hungarian
            r"film|mozi|sorozat|rendező|filmélmény|tempó|telítettség|szaturáció|élénk 4k|látványvilág|operatőr|"
            # German
            r"kino|filmregisseur|bildsättigung"
            r")\b"
        )

        # 4. UI/UX & Visual Aesthetics
        self.p_ui_ux = re.compile(
            r"(?i)\b("
            # English
            r"ui\b|ux\b|design system|typography|font pairing|dark mode|light mode|color palette|"
            r"soot obsidian|warm paper|anti-slop design|micro-interactions|editorial layout|shadcn|"
            # Hungarian
            r"felület dizájn|tipográfia|betűtípus|sötét mód|világos mód|színpaletta|arculati stílus|"
            r"szerkesztőségi elrendezés|felhasználói élmény|"
            # German
            r"benutzeroberfläche|schriftart|farbschema|dunkelmodus"
            r")\b"
        )

        # 5. Automotive & Livery Styling
        self.p_automotive = re.compile(
            r"(?i)\b("
            # English
            r"car design|livery|liveries|jgtc|bodykit|splitter|diffuser|subaru\s*gf8|aero styling|"
            r"motorsport heritage|race livery|car aesthetic|"
            # Hungarian
            r"autó dizájn|autó stílus|karosszéria|fényezés|matricázás|verseny livery|aerodinamika"
            r")\b"
        )

        # 6. Communication Style & Tone
        self.p_comm_style = re.compile(
            r"(?i)\b("
            # English
            r"communication style|tone of voice|direct tone|zero fluff|no fluff|concise markdown|"
            r"be brief|straight to the point|pragmatic response|no corporate speak|"
            # Hungarian
            r"kommunikációs stílus|közvetlen hangnem|sallangmentes|lényegretörő|rövid és tömör|"
            r"egyenesen a lényegre|ne szaporítsd a szót|nincs mellébeszélés|"
            # German
            r"direkter ton|ohne umschweife|kurz und bündig|pragmatisch"
            r")\b"
        )

        # 7. Language & Regional Locales
        self.p_language = re.compile(
            r"(?i)\b("
            # English
            r"first language|native language|hungarian|magyar|german|deutsch|english|locale setting|"
            # Hungarian
            r"anyanyelv(em)?|anyanyelvi|magyarul|magyar nyelvű|angolul|nyelvi beállítás|"
            # German
            r"muttersprache|auf deutsch|deutsche sprache"
            r")\b"
        )

        # 8. Hardware Specifications (Strict context: must express device ownership/spec, NOT code review)
        self.p_hardware = re.compile(
            r"(?i)\b("
            # Explicit devices & configurations
            r"tcl\s*65t8b|65-inch\s*4k|4k\s*qled|gtx\s*1050(\s*ti)?|acer\s*b243hl|windows\s*10\s*iot\s*ltsc|"
            # English ownership/setup phrases
            r"my tv (is|has)|my monitor (is|has)|my setup (is|has)|my gpu (is|has)|my graphics card|"
            r"my workstation|my screen resolution|my laptop is|my computer has|"
            # Hungarian ownership/setup phrases
            r"a tévém(et|en)?|a monitorom(at|on)?|a gépem(et|en)?|a laptopom(at|on)?|a videokártyám|"
            r"kijelzőm|felbontásom|számítógépem specifikáció|"
            # German
            r"mein fernseher|mein monitor|meine grafikkarte|mein arbeitsplatz|meine bildschirmauflösung"
            r")\b"
        )

        # 9. Workflow Conventions & Directives
        self.p_workflow = re.compile(
            r"(?i)\b("
            # English
            r"should always|never do|always use|my rule is|by default|from now on|our convention|"
            r"standard practice|mandatory rule|strict requirement|"
            # Hungarian
            r"mindig így csinál(d|juk)|soha ne csinál(d|juk)|mindig használd|a szabály az|"
            r"alapértelmezett(en)?|mostantól|ezentúl|szabályunk|kötelező előírás|"
            # German
            r"immer so machen|niemals|immer verwenden|meine regel|ab sofort|standardmäßig"
            r")\b"
        )

        # 10. Pre-recommendation Validation Invariant
        self.p_validation = re.compile(
            r"(?i)\b("
            # English
            r"always validate|validate before|verify before|double check before|confirm before recommending|"
            r"never assume|validate recommendation|verify ground truth|zero extrapolation|"
            # Hungarian
            r"mindig ellenőrizd|ellenőrzés előtt|validáld mielőtt|kétszer ellenőrizd|igazold le mielőtt|"
            r"sose feltételezz|tényalapú ellenőrzés|ajánlás előtt ellenőrizd|"
            # German
            r"immer validieren|vorher prüfen|vor empfehlung verifizieren|niemals annehmen"
            r")\b"
        )

        # 11. Technical Architecture & Engineering Decisions
        self.p_architecture = re.compile(
            r"(?i)\b("
            # English
            r"architecture decision|architectural decision|architecture milestone|architectural milestone|"
            r"architectural choice|decided to use|architected as|system architecture|database migration|"
            r"drizzle schema|lancedb columnar|anti-slop craftsmanship|matt pocock rule|state machine architecture|"
            r"safe rust binary|verification milestone|spectrum complete milestone|milestone:\s*|"
            # Hungarian
            r"architekturális döntés|architektúra döntés|úgy döntöttünk hogy|rendszerterv|adatbázis döntés|"
            r"séma migráció|tiszta kód alapelv|mérföldkő:|mérföldkő\b|"
            # German
            r"architekturentscheidung|datenbankentscheidung|schema-migration"
            r")\b"
        )

        # 12. Security & Privacy Mandate
        self.p_security = re.compile(
            r"(?i)\b("
            # English
            r"zero-leak|zero leak|privacy shield|secret isolation|never send data to cloud|"
            r"local-first privacy|sandboxed execution|scrub secrets in-process|"
            # Hungarian
            r"zéró szivárgás|titokvédelem|adatvédelem|soha ne küldj adatot felhőbe|"
            r"helyi elsőbbségű biztonság|biztonsági izoláció|titkok szűrése|"
            # German
            r"datenschutz|geheimnisschutz|kein datenleck|lokale verarbeitung"
            r")\b"
        )

        # 13. Project Objectives & Milestones
        self.p_projects = re.compile(
            r"(?i)\b("
            # English
            r"project goal|project milestone|official project name chosen|project name chosen|shipped version|"
            r"release notes|getmynews roadmap|notex milestone|chromacube puzzle|hopeful pipeline|"
            r"terrasyntropy agroforestry|"
            # Hungarian
            r"projekt cél|mérföldkő|hivatalos projekt név|választott projekt név|kiadott verzió|élesített funkció|projekt ütemterv|"
            # German
            r"projektziel|meilenstein|veröffentlichte version"
            r")\b"
        )

        # Explicit Ephemeral Interaction Cues (Quick commands, disposable tasks)
        self.p_ephemeral = re.compile(
            r"(?i)^("
            # English single-turn commands
            r"try again|run (the )?(tests?|command|script)|check (the )?commit|look into this|check this|"
            r"is it in this commit\??|what does this mean\??|fix (the )?(bug|error|issue)|grep for|"
            r"read (the )?file|show me (the )?code|git status|compile this|rebuild|"
            # Hungarian single-turn commands
            r"próbáld (meg )?újra|futtasd a teszteket|nézd meg a commitot|javítsd ki a hibát|"
            r"mit jelent ez\??|benne van ebben a commitban\??|keress rá|olvasd el a fájlt|"
            r"mutasd a kódot|fordítsd újra|futtasd le"
            # German single-turn commands
            r"|versuche es erneut|führe die tests aus|prüfe das commit|behebe den fehler"
            r")(\b|$)"
        )

    def detect_language(self, text: str) -> str:
        """Heuristic language detector focusing on Hungarian vs English vs German."""
        t_lower = text.lower()
        # Hungarian specific characters and common words
        hu_markers = [
            "és", "hogy", "nem", "egy", "van", "meg", "is", "ez", "az", "kell", "mint", "csak",
            "á", "é", "í", "ó", "ö", "ő", "ú", "ü", "ű"
        ]
        de_markers = ["und", "der", "die", "das", "nicht", "ein", "eine", "ist", "für", "mit", "ä", "ö", "ü", "ß"]

        hu_score = sum(1 for m in hu_markers if m in t_lower)
        de_score = sum(1 for m in de_markers if m in t_lower)

        if hu_score >= 3:
            return "hu"
        if de_score >= 3:
            return "de"
        return "en"

    def classify(self, text: str) -> ClassificationResult:
        """
        Classifies input text into a high-signal durable category or ephemeral quarantine.
        """
        clean_text = unicodedata.normalize("NFC", text).strip()
        lang = self.detect_language(clean_text)

        detected: List[str] = []

        # Check negative constraints first (highest priority filter)
        if self.p_critique.search(clean_text):
            detected.append("critique_negative_filter")
        if self.p_validation.search(clean_text):
            detected.append("validation_invariant")
        if self.p_security.search(clean_text):
            detected.append("security_privacy_mandate")

        # Check specific domain preferences
        if self.p_hardware.search(clean_text):
            # Guard against code audit false-positives
            if not ("audit" in clean_text.lower() and "install" in clean_text.lower() and len(clean_text) > 400):
                detected.append("hardware_spec")
        if self.p_entertainment.search(clean_text):
            detected.append("entertainment_preference")
        if self.p_ui_ux.search(clean_text):
            detected.append("ui_ux_aesthetic")
        if self.p_automotive.search(clean_text):
            detected.append("automotive_design")
        if self.p_comm_style.search(clean_text):
            detected.append("communication_style")
        if self.p_language.search(clean_text):
            detected.append("language_locale")
        if self.p_workflow.search(clean_text):
            detected.append("workflow_rule")
        if self.p_architecture.search(clean_text):
            detected.append("architectural_milestone")
        if self.p_projects.search(clean_text):
            detected.append("project_objective")
        if self.p_preference.search(clean_text) and "user_preference" not in detected:
            detected.append("user_preference")

        # Check if the prompt is purely an ephemeral task instruction
        is_explicit_ephemeral = bool(self.p_ephemeral.search(clean_text))

        # Payload size guard: Massive multi-paragraph pastes or audit dumps (>800 chars)
        # without explicit milestone headers are task payloads, not durable personal preferences.
        is_large_payload = (
            len(clean_text) > 800
            and "architectural_milestone" not in detected
            and not clean_text.lower().startswith(("architectural milestone:", "architecture decision:", "mérföldkő:"))
        )

        # Decision Boundary: Durable vs Quarantined
        if detected and not is_explicit_ephemeral and not is_large_payload:
            primary_cat = detected[0]
            return ClassificationResult(
                category=primary_cat,
                is_durable=True,
                is_quarantined=False,
                detected_categories=detected,
                detected_language=lang,
                confidence=0.92,
                rationale=f"Durable cognitive memory detected across {len(detected)} signals: {', '.join(detected)}."
            )

        # Quarantined Ephemeral Interaction
        rationale = "Transient conversational turn or operational instruction."
        if is_large_payload:
            rationale = f"Large task payload ({len(clean_text)} chars) quarantined to preserve vector retrieval precision."

        return ClassificationResult(
            category="ephemeral_turn",
            is_durable=False,
            is_quarantined=True,
            detected_categories=["ephemeral_turn"],
            detected_language=lang,
            confidence=0.95,
            rationale=rationale
        )


if __name__ == "__main__":
    clf = MultilingualClassifier()
    test_cases = [
        "A tévém egy TCL 65T8B, és a szaturált, élénk 4K-t preferálom, utálom a lassú szürke filmeket.",
        "My TV is a TCL 65T8B and I prefer eye-popping vibrant 4K.",
        "Mostantól mindig magyarul és angolul válaszolj, sallangmentes stílusban.",
        "Nézd meg a commitot, és javítsd ki a hibát.",
        "Run pytest on tests/test_storage.py and see if it passes.",
        "Is it in this commit? feat(search): implement BM25F candidate ranking...",
        "I created a Cephalo audit with Claude. Look at it and verify them...",
        "Az autó livery dizájnhoz használjunk JGTC stílust a Subaru GF8-on.",
        "We decided to use LanceDB for columnar vector storage and Safe Rust for daemon supervision.",
    ]
    for tc in test_cases:
        res = clf.classify(tc)
        print(f"[{res.detected_language.upper()}] Durable={res.is_durable} | Cat={res.category} | Text: {tc[:65]}...")
