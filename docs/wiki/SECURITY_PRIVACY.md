# Zero-Leak Privacy & Sanitization Shield

Cephalo guarantees that private notes, personal details, and sensitive credentials never leak to external model APIs, third-party vector databases, or public repositories.

## Multi-Tier Sanitization Architecture

```mermaid
flowchart LR
    Raw["Raw Prompt / Web Content"] --> T1A["Tier 1A: Regex Shield
(PII, Tax IDs, IBANs, Phone, IPs)"]
    T1A --> T1B["Tier 1B: Entropy Guard
(High-entropy API keys & tokens)"]
    T1B --> T1C["Tier 1C: AST Code Shield
(Protects code syntax from NLP mangling)"]
    T1C --> T2["Tier 2: GLiNER / Presidio
(Local Named-Entity Masking)"]
    T2 --> Clean["Sanitized Safe Payload
(LanceDB & prompts.jsonl)"]
```

## Hungarian + English PII Redaction
Cephalo specifically handles:
- **Hungarian Tax Numbers (Adóazonosító):** 10-digit format (`8XXXXXXXXX`).
- **Hungarian IBANs:** Standard 28-character format.
- **Hungarian Phone Numbers:** Mobile and landline formats (`+36 20/30/70 ...`).
- **High-Entropy Tokens:** Base64, hex, and random tokens with Shannon entropy $> 4.3$.
