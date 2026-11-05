//! Cephalo Sovereign Native DeepWiki Server (wiki.rs)
//! ===================================================
//! Ultra-lightweight native Axum server serving the DeepWiki documentation,
//! 24-hour timeline scrubber feed, and activity heatmap directly from local storage.
//! Replaces Python's SimpleHTTPRequestHandler with sub-1ms response latency.

use axum::{
    extract::{Query, Request, State},
    http::{header, HeaderValue, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::sync::Arc;
use tower_http::services::ServeDir;

pub struct WikiState {
    #[allow(dead_code)]
    pub root_dir: PathBuf,
    pub docs_wiki_dir: PathBuf,
    pub data_dir: PathBuf,
}

#[derive(Debug, Deserialize)]
pub struct TimelineQuery {
    pub limit: Option<usize>,
    pub hour: Option<u32>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TimelineRecord {
    pub id: String,
    pub timestamp: String,
    pub category: String,
    pub title: String,
    pub summary: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub window_title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub delta: Option<f64>,
}

/// Middleware to enforce strict CORS origins (localhost, 127.0.0.1, extensions)
async fn cors_origin_gate(req: Request, next: Next) -> Response {
    let origin_header = req.headers().get("origin").and_then(|v| v.to_str().ok()).unwrap_or("").to_string();
    let is_allowed = origin_header.is_empty()
        || origin_header.starts_with("http://localhost")
        || origin_header.starts_with("http://127.0.0.1")
        || origin_header.starts_with("moz-extension://")
        || origin_header.starts_with("chrome-extension://");

    if req.method() == axum::http::Method::OPTIONS {
        if is_allowed {
            let allow_origin = if origin_header.is_empty() {
                "http://127.0.0.1"
            } else {
                &origin_header
            };
            let mut res = StatusCode::NO_CONTENT.into_response();
            let headers = res.headers_mut();
            headers.insert(header::ACCESS_CONTROL_ALLOW_ORIGIN, HeaderValue::from_str(allow_origin).unwrap_or(HeaderValue::from_static("http://127.0.0.1")));
            headers.insert(header::ACCESS_CONTROL_ALLOW_METHODS, HeaderValue::from_static("GET, POST, OPTIONS"));
            headers.insert(header::ACCESS_CONTROL_ALLOW_HEADERS, HeaderValue::from_static("Content-Type"));
            return res;
        } else {
            return StatusCode::FORBIDDEN.into_response();
        }
    }

    if !is_allowed {
        return (StatusCode::FORBIDDEN, Json(json!({"error": "CORS origin rejected"}))).into_response();
    }

    let mut response = next.run(req).await;
    let allow_origin = if origin_header.is_empty() {
        "http://127.0.0.1"
    } else {
        &origin_header
    };
    let headers = response.headers_mut();
    headers.insert(header::ACCESS_CONTROL_ALLOW_ORIGIN, HeaderValue::from_str(allow_origin).unwrap_or(HeaderValue::from_static("http://127.0.0.1")));
    headers.insert(header::ACCESS_CONTROL_ALLOW_METHODS, HeaderValue::from_static("GET, POST, OPTIONS"));
    headers.insert(header::ACCESS_CONTROL_ALLOW_HEADERS, HeaderValue::from_static("Content-Type"));
    response
}

/// GET /api/timeline
async fn timeline_handler(
    State(state): State<Arc<WikiState>>,
    Query(query): Query<TimelineQuery>,
) -> impl IntoResponse {
    let limit = query.limit.unwrap_or(50);
    let mut records: Vec<TimelineRecord> = Vec::new();

    // 1. Ingest prompts.jsonl
    let prompts_file = state.data_dir.join("prompts.jsonl");
    if let Ok(file) = File::open(&prompts_file) {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(val) = serde_json::from_str::<Value>(trimmed) {
                let id = val.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let timestamp = val.get("timestamp").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let category = val.get("category").and_then(|v| v.as_str()).unwrap_or("general").to_string();
                let content = val.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string();

                let title = format!("[{}] {}", category, if content.len() > 60 { &content[..60] } else { &content });
                records.push(TimelineRecord {
                    id,
                    timestamp,
                    category,
                    title,
                    summary: content,
                    process_name: None,
                    window_title: None,
                    path: None,
                    delta: None,
                });
            }
        }
    }

    // 2. Ingest screen frames
    let frames_file = state.data_dir.join("frames/frame_index.jsonl");
    if let Ok(file) = File::open(&frames_file) {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(val) = serde_json::from_str::<Value>(trimmed) {
                let id = val.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let timestamp = val.get("timestamp").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let proc = val.get("process_name").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let win = val.get("window_title").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let path = val.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let delta = val.get("delta").and_then(|v| v.as_f64());

                let title = format!("🖥️ {} ({})", if win.is_empty() { "Active Window" } else { &win }, proc);
                records.push(TimelineRecord {
                    id,
                    timestamp,
                    category: "screen".to_string(),
                    title,
                    summary: win.clone(),
                    process_name: Some(proc),
                    window_title: Some(win),
                    path: Some(path),
                    delta,
                });
            }
        }
    }

    // Sort descending by timestamp
    records.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));

    // Filter by hour if specified
    if let Some(target_hour) = query.hour {
        records.retain(|r| {
            if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(&r.timestamp) {
                dt.format("%H").to_string().parse::<u32>().unwrap_or(99) == target_hour
            } else {
                false
            }
        });
    }

    records.truncate(limit);
    (StatusCode::OK, Json(records))
}

/// GET /api/heatmap
async fn heatmap_handler(State(state): State<Arc<WikiState>>) -> impl IntoResponse {
    let mut days_count: HashMap<String, usize> = HashMap::new();
    let mut total = 0;

    let prompts_file = state.data_dir.join("prompts.jsonl");
    if let Ok(file) = File::open(&prompts_file) {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(val) = serde_json::from_str::<Value>(trimmed) {
                if let Some(ts) = val.get("timestamp").and_then(|v| v.as_str()) {
                    let date_key = if ts.len() >= 10 { &ts[..10] } else { ts };
                    *days_count.entry(date_key.to_string()).or_insert(0) += 1;
                    total += 1;
                }
            }
        }
    }

    let active_days = days_count.len();
    let payload = json!({
        "days": days_count,
        "total": total,
        "active_days": active_days,
        "status": "ok"
    });
    (StatusCode::OK, Json(payload))
}

pub fn create_router(state: Arc<WikiState>) -> Router {
    let serve_dir = ServeDir::new(&state.docs_wiki_dir);

    Router::new()
        .route("/api/timeline", get(timeline_handler))
        .route("/api/heatmap", get(heatmap_handler))
        .fallback_service(serve_dir)
        .layer(middleware::from_fn(cors_origin_gate))
        .with_state(state)
}

pub async fn start_wiki_server(
    root_dir: PathBuf,
    port: u16,
) -> Result<(), Box<dyn std::error::Error>> {
    let docs_wiki_dir = root_dir.join("docs/wiki");
    let data_dir = root_dir.join("data");
    let _ = std::fs::create_dir_all(&docs_wiki_dir);

    let state = Arc::new(WikiState {
        root_dir,
        docs_wiki_dir,
        data_dir,
    });
    let app = create_router(state);
    let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
    let listener = tokio::net::TcpListener::bind(addr).await?;
    println!("[+] Cephalo Native Rust DeepWiki Server listening at http://{}", addr);
    axum::serve(listener, app).await?;
    Ok(())
}
