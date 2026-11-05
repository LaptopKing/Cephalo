//! Cephalo Specialties Layer Manager (specialties.rs)
//! ==================================================
//! Project-scoped domain blueprints and accumulated engineering memory.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpecialtyInfo {
    pub project: String,
    pub slug: String,
    pub path: String,
    pub title: String,
    pub modified: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Specialty {
    pub project: String,
    pub slug: String,
    pub title: String,
    pub content: String,
    pub traits: Vec<String>,
}

pub struct SpecialtyManager {
    base_dir: PathBuf,
}

impl SpecialtyManager {
    pub fn new(root_dir: &Path) -> Self {
        Self {
            base_dir: root_dir.join("specialties"),
        }
    }

    pub fn list_specialties(&self) -> Vec<SpecialtyInfo> {
        let mut results = Vec::new();
        if !self.base_dir.exists() {
            return results;
        }

        if let Ok(projects) = fs::read_dir(&self.base_dir) {
            for proj_entry in projects.flatten() {
                if !proj_entry.path().is_dir() {
                    continue;
                }
                let project = proj_entry.file_name().to_string_lossy().to_string();

                if let Ok(entries) = fs::read_dir(proj_entry.path()) {
                    for entry in entries.flatten() {
                        let path = entry.path();
                        let slug = entry.file_name().to_string_lossy().to_string();

                        if slug.to_lowercase() == "readme.md" || slug.to_lowercase() == "readme" {
                            continue;
                        }

                        // Case 1: Directory module (manifest.json + KNOWLEDGE.md)
                        if path.is_dir() {
                            let manifest_path = path.join("manifest.json");
                            let knowledge_path = path.join("KNOWLEDGE.md");

                            let mut title = slug.replace('-', " ");
                            if manifest_path.exists() {
                                if let Ok(content) = fs::read_to_string(&manifest_path) {
                                    if let Ok(v) = serde_json::from_str::<Value>(&content) {
                                        if let Some(name) = v.get("name").and_then(|n| n.as_str()) {
                                            title = name.to_string();
                                        }
                                    }
                                }
                            }

                            let modified = entry
                                .metadata()
                                .and_then(|m| m.modified())
                                .map(|t| chrono::DateTime::<chrono::Utc>::from(t).to_rfc3339())
                                .unwrap_or_default();

                            let primary_path = if knowledge_path.exists() {
                                knowledge_path
                            } else {
                                path.clone()
                            };

                            results.push(SpecialtyInfo {
                                project: project.clone(),
                                slug: slug.clone(),
                                path: primary_path.to_string_lossy().to_string(),
                                title,
                                modified,
                            });
                        }
                        // Case 2: Flat markdown file (slug.md)
                        else if path.is_file() && path.extension().is_some_and(|ext| ext == "md") {
                            let file_stem = path.file_stem().unwrap().to_string_lossy().to_string();
                            let content = fs::read_to_string(&path).unwrap_or_default();
                            let first_line = content.lines().next().unwrap_or("").trim();
                            let title = if let Some(stripped) = first_line.strip_prefix("# ") {
                                stripped.trim().to_string()
                            } else {
                                file_stem.replace('-', " ")
                            };

                            let modified = entry
                                .metadata()
                                .and_then(|m| m.modified())
                                .map(|t| chrono::DateTime::<chrono::Utc>::from(t).to_rfc3339())
                                .unwrap_or_default();

                            results.push(SpecialtyInfo {
                                project: project.clone(),
                                slug: file_stem,
                                path: path.to_string_lossy().to_string(),
                                title,
                                modified,
                            });
                        }
                    }
                }
            }
        }

        results.sort_by(|a, b| a.project.cmp(&b.project).then(a.slug.cmp(&b.slug)));
        results
    }

    pub fn get_specialty(&self, project: &str, slug: &str) -> Option<Specialty> {
        let dir_target = self.base_dir.join(project).join(slug);
        let knowledge_target = dir_target.join("KNOWLEDGE.md");
        let manifest_target = dir_target.join("manifest.json");
        let file_target = self.base_dir.join(project).join(format!("{}.md", slug));

        if knowledge_target.exists() {
            let content = fs::read_to_string(&knowledge_target).ok()?;
            let mut title = slug.replace('-', " ");
            if manifest_target.exists() {
                if let Ok(m_str) = fs::read_to_string(&manifest_target) {
                    if let Ok(v) = serde_json::from_str::<Value>(&m_str) {
                        if let Some(n) = v.get("name").and_then(|n| n.as_str()) {
                            title = n.to_string();
                        }
                    }
                }
            }
            return Some(Specialty {
                project: project.to_string(),
                slug: slug.to_string(),
                title,
                content,
                traits: Vec::new(),
            });
        }

        if file_target.exists() {
            let content = fs::read_to_string(&file_target).ok()?;
            let first_line = content.lines().next().unwrap_or("").trim();
            let title = if let Some(stripped) = first_line.strip_prefix("# ") {
                stripped.trim().to_string()
            } else {
                slug.replace('-', " ")
            };
            return Some(Specialty {
                project: project.to_string(),
                slug: slug.to_string(),
                title,
                content,
                traits: Vec::new(),
            });
        }

        // Cross-project fallback search
        let all = self.list_specialties();
        for s in all {
            if s.slug.eq_ignore_ascii_case(slug) {
                let p = PathBuf::from(&s.path);
                if let Ok(c) = fs::read_to_string(p) {
                    return Some(Specialty {
                        project: s.project,
                        slug: s.slug,
                        title: s.title,
                        content: c,
                        traits: Vec::new(),
                    });
                }
            }
        }

        None
    }

    pub fn create_specialty(
        &self,
        project: &str,
        slug: &str,
        title: &str,
        content: &str,
    ) -> std::io::Result<PathBuf> {
        let proj_dir = self.base_dir.join(project).join(slug);
        fs::create_dir_all(&proj_dir)?;
        let knowledge_path = proj_dir.join("KNOWLEDGE.md");
        let manifest_path = proj_dir.join("manifest.json");

        let formatted = if content.starts_with("# ") {
            content.to_string()
        } else {
            format!("# {}\n\n{}", title, content)
        };

        fs::write(&knowledge_path, formatted)?;

        let manifest = serde_json::json!({
            "name": title,
            "slug": slug,
            "project": project,
            "created_at": chrono::Utc::now().to_rfc3339(),
        });
        fs::write(&manifest_path, serde_json::to_string_pretty(&manifest)?)?;

        Ok(knowledge_path)
    }
}
