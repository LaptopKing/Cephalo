//! Cephalo User Profile Blueprint Manager (profile.rs)
//! ====================================================
//! Token-efficient sectional extraction and mutation of USER_PROFILE.md.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

pub struct ProfileManager {
    profile_path: PathBuf,
}

impl ProfileManager {
    pub fn new(root_dir: &Path) -> Self {
        Self {
            profile_path: root_dir.join("USER_PROFILE.md"),
        }
    }

    pub fn exists(&self) -> bool {
        self.profile_path.exists()
    }

    pub fn read_full(&self) -> std::io::Result<String> {
        fs::read_to_string(&self.profile_path)
    }

    /// Lists all markdown section headings (e.g. "## 2. User Identity & Verified Hardware").
    pub fn list_sections(&self) -> Vec<String> {
        let content = match self.read_full() {
            Ok(c) => c,
            Err(_) => return Vec::new(),
        };

        content
            .lines()
            .filter(|l| l.starts_with('#'))
            .map(|l| l.trim().to_string())
            .collect()
    }

    /// Extracts a single targeted section by name, saving thousands of tokens.
    pub fn get_section(&self, section_name: &str) -> Option<String> {
        let content = self.read_full().ok()?;
        let sec_lower = section_name.to_lowercase();
        let lines: Vec<&str> = content.lines().collect();

        let mut in_section = false;
        let mut target_level = 0;
        let mut section_lines = Vec::new();

        for line in lines {
            let trimmed = line.trim();
            if trimmed.starts_with('#') {
                let level = trimmed.chars().take_while(|&c| c == '#').count();
                let heading = trimmed[level..].trim().to_lowercase();

                if heading.contains(&sec_lower) {
                    in_section = true;
                    target_level = level;
                    section_lines.push(line);
                    continue;
                } else if in_section && level <= target_level {
                    // Reached next section of equal or higher rank
                    break;
                }
            }

            if in_section {
                section_lines.push(line);
            }
        }

        if section_lines.is_empty() {
            None
        } else {
            Some(section_lines.join("\n").trim().to_string())
        }
    }

    /// Appends or updates a bullet point in a specific section.
    pub fn update_section(
        &self,
        section_name: &str,
        bullet_text: &str,
        replace: bool,
    ) -> std::io::Result<bool> {
        let content = self.read_full()?;
        let sec_lower = section_name.to_lowercase();
        let lines: Vec<&str> = content.lines().collect();

        let mut output = Vec::new();
        let mut found_section = false;
        let mut in_section = false;
        let mut target_level = 0;
        let mut inserted = false;

        for line in lines {
            let trimmed = line.trim();
            if trimmed.starts_with('#') {
                let level = trimmed.chars().take_while(|&c| c == '#').count();
                let heading = trimmed[level..].trim().to_lowercase();

                if heading.contains(&sec_lower) {
                    found_section = true;
                    in_section = true;
                    target_level = level;
                    output.push(line.to_string());
                    if replace {
                        output.push(format!("- {}", bullet_text.trim_start_matches("- ")));
                        inserted = true;
                    }
                    continue;
                } else if in_section && level <= target_level {
                    // Exiting target section
                    if !inserted && !replace {
                        output.push(format!("- {}", bullet_text.trim_start_matches("- ")));
                        inserted = true;
                    }
                    in_section = false;
                }
            }

            if in_section && replace {
                // If replace mode, skip previous section body
                continue;
            }

            output.push(line.to_string());
        }

        if in_section && !inserted && !replace {
            output.push(format!("- {}", bullet_text.trim_start_matches("- ")));
        }

        if !found_section {
            return Ok(false);
        }

        let temp_path = self.profile_path.with_extension("tmp");
        {
            let mut file = fs::File::create(&temp_path)?;
            for l in output {
                writeln!(file, "{}", l)?;
            }
            file.flush()?;
        }
        fs::rename(temp_path, &self.profile_path)?;

        Ok(true)
    }
}
