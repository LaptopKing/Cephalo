"""
Cephalo PII, Secret, and Sensitive Pattern Sanitizer.
"""

import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cephalo.sanitizer")

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
        (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '<REDACTED_AWS_KEY>'),
        (re.compile(r'\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{50,})\b'), '<REDACTED_GITHUB_TOKEN>'),
        (re.compile(r'\bxox[baprs]-[a-zA-Z0-9\-]{20,}\b'), '<REDACTED_SLACK_TOKEN>'),
        (re.compile(r'\beyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]+\b'), '<REDACTED_JWT>'),
        (re.compile(r'Bearer\s+[a-zA-Z0-9\._\-]{20,}', re.IGNORECASE), 'Bearer <REDACTED_TOKEN>'),
        (re.compile(r'\b(?:postgres|postgresql|mysql|mongodb|redis|amqp):\/\/[^\s:]+:[^\s@]+@[^\s]+\b'), '<REDACTED_CONNECTION_STRING>'),
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

    PEM_KEY_PATTERN = re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----')

    ASSIGNMENT_PATTERN = re.compile(
        r'(?i)\b([a-zA-Z0-9_]*(?:api[_-]?key|secret[_-]?access[_-]?key|aws[_-]?secret|secret|token|password|passwd|auth|bearer)[a-zA-Z0-9_]*)\b\s*[:=]\s*["\']?([^"\'\s\r\n]{3,})["\']?'
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
            logger.warning(f"Presidio NLP engine not initialized ({e}); falling back to deterministic regex and entropy tier.")

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

        # Tier 1B: Shannon Entropy & Explicit Assignment Guard
        def replace_entropy_secret(match):
            prefix = match.group(1)
            token = match.group(2)
            prefix_lower = prefix.lower()
            # Explicit secret keys are unconditionally redacted regardless of length or entropy
            if any(k in prefix_lower for k in ("password", "passwd", "secret", "token", "api_key", "bearer", "auth")):
                return f"{prefix}=<REDACTED_SECRET>"
            is_hex = bool(re.fullmatch(r'[0-9a-fA-F]+', token))
            ent = calculate_shannon_entropy(token)
            threshold = 3.0 if is_hex else 3.4
            if ent >= threshold or len(token) >= 20:
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
        # Redact multiline PEM certificates and keys first
        text = self.PEM_KEY_PATTERN.sub("<REDACTED_PRIVATE_KEY>", text)
        lines = text.split("\n")
        return "\n".join(self.sanitize_line(l) for l in lines)


# ==============================================================================
# 2. Embedding Layer (Dual Modes: Mode A Local & Mode B Google Cloud)
# ==============================================================================
