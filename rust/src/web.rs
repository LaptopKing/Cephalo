//! Cephalo Sovereign Native Web Fetch & Search Engine (web.rs)
//! ============================================================
//! High-speed, async HTTP web fetch and text/markdown extraction.
//! Executes network calls directly in Rust without invoking Python interpreters.

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebFetchResult {
    pub url: String,
    pub title: String,
    pub content: String,
    pub status: u16,
    pub elapsed_ms: u128,
}

pub struct WebEngine {
    client: reqwest::Client,
}

impl WebEngine {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(15))
            .user_agent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Cephalo/0.2.0")
            .build()
            .unwrap_or_default();
        Self { client }
    }

    /// Fetches a URL and returns clean, human-readable markdown text.
    pub async fn fetch(&self, url: &str) -> Result<WebFetchResult, Box<dyn std::error::Error>> {
        let start = std::time::Instant::now();
        let resp = self.client.get(url).send().await?;
        let status = resp.status().as_u16();
        let html = resp.text().await?;
        let elapsed_ms = start.elapsed().as_millis();

        let title = extract_html_title(&html).unwrap_or_else(|| url.to_string());
        let content = html_to_markdown(&html);

        Ok(WebFetchResult {
            url: url.to_string(),
            title,
            content,
            status,
            elapsed_ms,
        })
    }
}

impl Default for WebEngine {
    fn default() -> Self {
        Self::new()
    }
}

fn extract_html_title(html: &str) -> Option<String> {
    let re = Regex::new(r"(?i)<title[^>]*>(.*?)</title>").ok()?;
    let caps = re.captures(html)?;
    Some(caps.get(1)?.as_str().trim().to_string())
}

/// Converts raw HTML to clean, readable markdown.
pub fn html_to_markdown(html: &str) -> String {
    let mut stripped = html.to_string();
    // 1. Remove script, style, head, nav, footer, iframe tags
    for tag in ["script", "style", "nav", "footer", "header", "iframe", "noscript"] {
        let pattern = format!(r"(?is)<{}[^>]*>.*?</{}>", tag, tag);
        if let Ok(re) = Regex::new(&pattern) {
            stripped = re.replace_all(&stripped, "").to_string();
        }
    }

    // 2. Convert headings
    let re_h1 = Regex::new(r"(?i)<h1[^>]*>(.*?)</h1>").unwrap();
    let re_h2 = Regex::new(r"(?i)<h2[^>]*>(.*?)</h2>").unwrap();
    let re_h3 = Regex::new(r"(?i)<h3[^>]*>(.*?)</h3>").unwrap();
    let s = re_h1.replace_all(&stripped, "\n# $1\n");
    let s = re_h2.replace_all(&s, "\n## $1\n");
    let s = re_h3.replace_all(&s, "\n### $1\n");

    // 3. Convert links <a href="url">text</a> -> [text](url)
    let re_link = Regex::new(r#"(?i)<a[^>]*href=["']([^"']*)["'][^>]*>(.*?)</a>"#).unwrap();
    let s = re_link.replace_all(&s, "[$2]($1)");

    // 4. Convert list items <li> -> *
    let re_li = Regex::new(r"(?i)<li[^>]*>(.*?)</li>").unwrap();
    let s = re_li.replace_all(&s, "\n* $1");

    // 5. Convert paragraphs and line breaks
    let re_p = Regex::new(r"(?i)<p[^>]*>(.*?)</p>").unwrap();
    let re_br = Regex::new(r"(?i)<br\s*/?>").unwrap();
    let s = re_p.replace_all(&s, "\n$1\n");
    let s = re_br.replace_all(&s, "\n");

    // 6. Strip all remaining HTML tags
    let re_tags = Regex::new(r"<[^>]+>").unwrap();
    let s = re_tags.replace_all(&s, " ");

    // 7. Clean HTML entities
    let s = s.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'");

    // 8. Collapse consecutive blank lines
    let re_newlines = Regex::new(r"\n{3,}").unwrap();
    let s = re_newlines.replace_all(&s, "\n\n");

    s.trim().to_string()
}
