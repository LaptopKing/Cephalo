//! Cephalo Sovereign Hardware & Thermal Resource Governor (governor.rs)
//! ======================================================================
//! Implements a strict hardware hierarchy managing CPU, memory, thermals,
//! and battery state.
//!
//! Invariant: The user must NEVER feel that Cephalo is running. Background
//! tasks yield immediately when the system is under load or on low battery.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use sysinfo::{CpuRefreshKind, MemoryRefreshKind, RefreshKind, System};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum GovernorMode {
    EmergencyConservation,
    BatterySaverSequential,
    AcPowerBalanced,
    AcPowerThrottled,
}

impl GovernorMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            GovernorMode::EmergencyConservation => "EMERGENCY_CONSERVATION",
            GovernorMode::BatterySaverSequential => "BATTERY_SAVER_SEQUENTIAL",
            GovernorMode::AcPowerBalanced => "AC_POWER_BALANCED",
            GovernorMode::AcPowerThrottled => "AC_POWER_THROTTLED",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareMetrics {
    pub on_battery: bool,
    pub power_plugged: bool,
    pub battery_percent: Option<f32>,
    pub cpu_count: usize,
    pub cpu_percent: f32,
    pub load_1m: f64,
    pub mem_total_mb: u64,
    pub mem_available_mb: u64,
    pub safe_concurrency: usize,
    pub mode: GovernorMode,
    pub throttle_reason: String,
    pub recommended_threads: usize,
    pub timestamp: String,
}

pub struct ResourceGovernor {
    system: System,
}

impl ResourceGovernor {
    pub fn new() -> Self {
        let refresh = RefreshKind::nothing()
            .with_cpu(CpuRefreshKind::everything())
            .with_memory(MemoryRefreshKind::everything());
        let mut system = System::new_with_specifics(refresh);
        system.refresh_cpu_all();
        system.refresh_memory();
        Self { system }
    }

    /// Probes Linux /sys/class/power_supply for real-time battery status without external dependencies.
    fn probe_linux_battery() -> (bool, Option<f32>) {
        let base = Path::new("/sys/class/power_supply");
        if !base.exists() {
            return (false, None);
        }

        let mut battery_capacity: Option<f32> = None;
        let mut on_battery = false;

        if let Ok(entries) = fs::read_dir(base) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.starts_with("BAT") {
                    let cap_file = entry.path().join("capacity");
                    if let Ok(content) = fs::read_to_string(cap_file) {
                        if let Ok(val) = content.trim().parse::<f32>() {
                            battery_capacity = Some(val);
                        }
                    }

                    let status_file = entry.path().join("status");
                    if let Ok(status) = fs::read_to_string(status_file) {
                        let st = status.trim().to_lowercase();
                        if st == "discharging" {
                            on_battery = true;
                        }
                    }
                }
            }
        }

        (on_battery, battery_capacity)
    }

    /// Cross-platform battery probing for Linux, macOS, and Windows.
    fn probe_battery() -> (bool, Option<f32>) {
        if cfg!(target_os = "linux") {
            let (on_bat, cap) = Self::probe_linux_battery();
            if cap.is_some() || on_bat {
                return (on_bat, cap);
            }
        } else if cfg!(target_os = "macos") {
            if let Ok(out) = std::process::Command::new("pmset").args(["-g", "batt"]).output() {
                let text = String::from_utf8_lossy(&out.stdout);
                let on_bat = text.contains("Battery Power");
                if let Some(idx) = text.find('%') {
                    if idx >= 3 {
                        let slice = &text[idx - 3..idx].trim_start_matches(|c: char| !c.is_ascii_digit());
                        if let Ok(val) = slice.parse::<f32>() {
                            return (on_bat, Some(val));
                        }
                    }
                }
                return (on_bat, None);
            }
        } else if cfg!(target_os = "windows") {
            if let Ok(out) = std::process::Command::new("powershell")
                .args(["-NoProfile", "-Command", "Get-CimInstance -ClassName Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining"])
                .output()
            {
                let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
                if let Ok(val) = text.parse::<f32>() {
                    return (true, Some(val));
                }
            }
        }
        (false, None)
    }

    /// Evaluates real-time hardware status against Cephalo's strict safety hierarchy.
    pub fn inspect_resources(&mut self) -> HardwareMetrics {
        self.system.refresh_cpu_all();
        self.system.refresh_memory();

        let (mut on_battery, battery_percent) = Self::probe_battery();

        // Fallback for container or desktop without battery
        if battery_percent.is_none() && !on_battery {
            on_battery = false;
        }

        let power_plugged = !on_battery;
        let cpu_count = self.system.cpus().len().max(1);
        let cpu_percent = self.system.global_cpu_usage();
        let load_1m = System::load_average().one;
        let mem_total_mb = self.system.total_memory() / (1024 * 1024);
        let mem_available_mb = self.system.available_memory() / (1024 * 1024);

        let safe_concurrency;
        let mode;
        let throttle_reason;
        let recommended_threads;

        // Hierarchy Evaluation
        if on_battery {
            if let Some(pct) = battery_percent {
                if pct < 20.0 {
                    // Level 0: Critical battery floor (<20%). Complete pause.
                    safe_concurrency = 0;
                    mode = GovernorMode::EmergencyConservation;
                    throttle_reason = format!(
                        "Battery critically low ({:.1}%). Cephalo background execution paused to prevent laptop shutdown. Connect charger.",
                        pct
                    );
                    recommended_threads = 1;
                } else {
                    // Level 1: Standard battery mode (>=20%). Strict serialization.
                    safe_concurrency = 1;
                    mode = GovernorMode::BatterySaverSequential;
                    throttle_reason = format!(
                        "Running on Battery ({:.1}%). Strict sequential execution (max 1 task, 1 thread).",
                        pct
                    );
                    recommended_threads = 1;
                }
            } else {
                safe_concurrency = 1;
                mode = GovernorMode::BatterySaverSequential;
                throttle_reason = "Running on Battery. Strict sequential execution.".to_string();
                recommended_threads = 1;
            }
        } else {
            // AC Power connected
            if cpu_percent > 85.0 || mem_available_mb < 600 {
                // High system load on AC -> pause new background work to preserve user flow
                safe_concurrency = 0;
                mode = GovernorMode::EmergencyConservation;
                throttle_reason = format!(
                    "System under heavy foreground load (CPU: {:.1}%, Mem: {}MB free). Background tasks paused.",
                    cpu_percent, mem_available_mb
                );
                recommended_threads = 1;
            } else if cpu_percent > 70.0 || (load_1m > cpu_count as f64 * 0.8) {
                // Moderate load on AC -> throttled to 1 task
                safe_concurrency = 1;
                mode = GovernorMode::AcPowerThrottled;
                throttle_reason = format!(
                    "Elevated CPU usage ({:.1}%). Capped to 1 background task to keep fan noise low.",
                    cpu_percent
                );
                recommended_threads = 1;
            } else if cpu_percent < 50.0 && mem_available_mb > 2500 {
                // Nominal AC power -> up to 2 tasks concurrently
                safe_concurrency = 2;
                mode = GovernorMode::AcPowerBalanced;
                throttle_reason = "AC Power connected and thermals nominal. Up to 2 concurrent background jobs allowed.".to_string();
                recommended_threads = 2.min(cpu_count);
            } else {
                safe_concurrency = 1;
                mode = GovernorMode::AcPowerBalanced;
                throttle_reason = "AC Power connected. 1 background task allowed.".to_string();
                recommended_threads = 1;
            }
        }

        HardwareMetrics {
            on_battery,
            power_plugged,
            battery_percent,
            cpu_count,
            cpu_percent,
            load_1m,
            mem_total_mb,
            mem_available_mb,
            safe_concurrency,
            mode,
            throttle_reason,
            recommended_threads,
            timestamp: chrono::Utc::now().to_rfc3339(),
        }
    }

    /// Returns whether a heavy background job is allowed to execute right now.
    pub fn is_heavy_allowed(&mut self) -> bool {
        let m = self.inspect_resources();
        m.safe_concurrency > 0
    }

    /// Sets process environment variables (OMP_NUM_THREADS, MKL_NUM_THREADS)
    /// to guarantee CPU matrix libraries obey the governor.
    pub fn apply_thread_limits(&mut self) {
        let m = self.inspect_resources();
        let threads = m.recommended_threads.to_string();
        std::env::set_var("OMP_NUM_THREADS", &threads);
        std::env::set_var("MKL_NUM_THREADS", &threads);
        std::env::set_var("RAYON_NUM_THREADS", &threads);
    }
}
