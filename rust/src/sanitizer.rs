//! Cephalo Sovereign Privacy & Secret Sanitizer (sanitizer.rs)
//! ==========================================================
//! Multi-tier deterministic redaction ensuring zero credentials, tokens,
//! or sensitive PII are ever stored in vector databases or external logs.

use regex::Regex;
use std::collections::HashSet;

pub struct Sanitizer {
    patterns: Vec<(Regex, &'static str)>,
    assignment_pattern: Regex,
}

impl Sanitizer {
    pub fn new() -> Self {
        let patterns = vec![
            // Explicit API Keys & Tokens
            (Regex::new(r"sk-[a-zA-Z0-9_\-]{20,}").unwrap(), "<REDACTED_API_KEY>"),
            (Regex::new(r"ghp_[a-zA-Z0-9]{36}").unwrap(), "<REDACTED_GITHUB_TOKEN>"),
            (Regex::new(r"github_pat_[a-zA-Z0-9_]{50,}").unwrap(), "<REDACTED_GITHUB_TOKEN>"),
            (Regex::new(r"(?i)Bearer\s+[a-zA-Z0-9._\-]{20,}").unwrap(), "Bearer <REDACTED_TOKEN>"),

            // Hungarian Banking & Taxes
            (Regex::new(r"(?i)\bHU\d{2}[\s\-]?(?:\d{4}[\s\-]?){5}\d{4}\b").unwrap(), "<REDACTED_HU_IBAN>"),
            (Regex::new(r"\b\d{8}[\s\-]\d{8}(?:[\s\-]\d{8})?\b").unwrap(), "<REDACTED_HU_BANK_ACC>"),
            (Regex::new(r"\b8\d{9}\b").unwrap(), "<REDACTED_HU_TAX_ID>"),
            (Regex::new(r"\b\d{8}-[1-5]-[0-5]\d\b").unwrap(), "<REDACTED_HU_TAX_NO>"),
            (Regex::new(r"(?:\+36|06)[\s\-]?(?:[1-9]\d{0,1})[\s\-]?\d{3}[\s\-]?\d{3,4}\b").unwrap(), "<REDACTED_HU_PHONE>"),
            (Regex::new(r"\b\d{6}[A-Z]{2}\b").unwrap(), "<REDACTED_HU_ID>"),

            // Credit Cards
            (Regex::new(r"\b(?:\d{4}[ -]?){3}\d{4}\b").unwrap(), "<REDACTED_CARD>"),

            // Network & Email
            (Regex::new(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b").unwrap(), "<REDACTED_EMAIL>"),
            (Regex::new(r"\b(?:\d{1,3}\.){3}\d{1,3}\b").unwrap(), "<REDACTED_IP>"),
        ];

        let assignment_pattern = Regex::new(
            r#"(?i)(api[_-]?key|secret|token|password|auth|bearer)[\s:=]+["']?([a-zA-Z0-9!@#\$%\^&\*_\-]{8,})["']?"#,
        ).unwrap();

        Self {
            patterns,
            assignment_pattern,
        }
    }

    /// Computes Shannon entropy of a string to detect high-entropy keys/secrets.
    pub fn shannon_entropy(s: &str) -> f64 {
        if s.is_empty() {
            return 0.0;
        }
        let mut counts = [0usize; 256];
        for b in s.bytes() {
            counts[b as usize] += 1;
        }
        let len = s.len() as f64;
        let mut entropy = 0.0;
        for &count in &counts {
            if count > 0 {
                let p = count as f64 / len;
                entropy -= p * p.log2();
            }
        }
        entropy
    }

    /// Checks if a line resembles programming code to avoid corrupting identifiers.
    fn is_code_line(line: &str) -> bool {
        let trimmed = line.trim();
        if trimmed.starts_with("//") || trimmed.starts_with("#") || trimmed.starts_with("/*") {
            return false;
        }
        trimmed.contains("fn ")
            || trimmed.contains("def ")
            || trimmed.contains("class ")
            || trimmed.contains("import ")
            || trimmed.contains("let ")
            || trimmed.contains("const ")
            || trimmed.contains("var ")
            || trimmed.ends_with('{')
            || trimmed.ends_with(';')
    }

    /// Sanitizes input text, redacting secrets and tokens deterministically in sub-millisecond time.
    pub fn sanitize(&self, text: &str) -> String {
        let mut result = text.to_string();

        // 1. Regex replacements
        for (re, replacement) in &self.patterns {
            result = re.replace_all(&result, *replacement).to_string();
        }

        // 2. High entropy secret assignment check
        let mut replacements = Vec::new();
        for cap in self.assignment_pattern.captures_iter(&result) {
            if let Some(val_match) = cap.get(2) {
                let val = val_match.as_str();
                if Self::shannon_entropy(val) > 3.2 && val.len() >= 12 {
                    replacements.push((val_match.start(), val_match.end()));
                }
            }
        }

        // Apply replacements from back to front
        replacements.sort_by(|a, b| b.0.cmp(&a.0));
        for (start, end) in replacements {
            result.replace_range(start..end, "<REDACTED_HIGH_ENTROPY_SECRET>");
        }

        result
    }

    /// Extracts hashtag topics (`#rust`, `#architecture`) from text.
    pub fn extract_tags(text: &str) -> Vec<String> {
        let tag_re = Regex::new(r"#([a-zA-Z0-9_\-]+)").unwrap();
        let mut tags = HashSet::new();
        for cap in tag_re.captures_iter(text) {
            if let Some(t) = cap.get(1) {
                tags.insert(t.as_str().to_lowercase());
            }
        }
        let mut res: Vec<String> = tags.into_iter().collect();
        res.sort();
        res
    }
}
