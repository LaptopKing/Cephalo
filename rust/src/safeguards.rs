//! Cephalo Sovereign Safeguards Configuration & Window Shielding Rules.

use regex::Regex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafeguardsConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_false")]
    pub screen_capture_enabled: bool,
    #[serde(default)]
    pub blacklisted_processes: Vec<String>,
    #[serde(default)]
    pub blacklisted_window_titles: Vec<String>,
    #[serde(default)]
    pub blacklisted_domains: Vec<String>,
}

fn default_true() -> bool {
    true
}

fn default_false() -> bool {
    false
}

impl Default for SafeguardsConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            screen_capture_enabled: false,
            blacklisted_processes: vec![
                "1password".into(),
                "bitwarden".into(),
                "keepass".into(),
                "keepassxc".into(),
                "vaultwarden".into(),
                "lastpass".into(),
                "authenticator".into(),
                "authy".into(),
            ],
            blacklisted_window_titles: vec![
                r"(?i)incognito".into(),
                r"(?i)private browsing".into(),
                r"(?i)inprivate".into(),
                r"(?i)password".into(),
                r"(?i)credential".into(),
                r"(?i)payment|checkout|credit card|cvv|security code".into(),
            ],
            blacklisted_domains: vec![
                "*.bank*".into(),
                "paypal.com".into(),
                "stripe.com/dashboard".into(),
                "revolut.com".into(),
                "wise.com".into(),
            ],
        }
    }
}



impl SafeguardsConfig {
    pub fn is_shielded(&self, title: &str, process: &str) -> (bool, Option<String>) {
        if !self.enabled {
            return (false, None);
        }

        let p_lower = process.to_lowercase();
        for bp in &self.blacklisted_processes {
            if p_lower.contains(&bp.to_lowercase()) {
                return (true, Some(format!("Blacklisted password/auth process: {}", bp)));
            }
        }

        for pattern in &self.blacklisted_window_titles {
            if let Ok(re) = Regex::new(pattern) {
                if re.is_match(title) {
                    return (true, Some(format!("Blacklisted private window title pattern: {}", pattern)));
                }
            }
        }

        // Check blacklisted sensitive web domains against active window title
        let t_lower = title.to_lowercase();
        for bd in &self.blacklisted_domains {
            let clean_domain = bd.trim_start_matches("*.").to_lowercase();
            if !clean_domain.is_empty() && t_lower.contains(&clean_domain) {
                return (true, Some(format!("Blacklisted sensitive domain: {}", bd)));
            }
        }

        (false, None)
    }
}
