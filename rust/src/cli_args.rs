//! Command Line Interface (CLI) Arguments & Flags Specification for Clap.

use clap::{Args, Parser, Subcommand};

#[derive(Parser, Debug)]
#[command(
    name = "cephalo",
    version = "0.2.0",
    about = "⚡ Cephalo Sovereign Second Brain & Autonomous Memory Engine (Native Rust)",
    long_about = "High-performance, local-first long-term memory coprocessor with strict hardware hierarchy and multi-agent coordination."
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
pub enum Commands {
    /// Inspect Cephalo engine status, hardware telemetry, and memory metrics
    Status,

    /// Query Cephalo local memory using high-speed hybrid search
    Search(SearchArgs),

    /// Record a preference, architectural milestone, decision, or constraint
    Record(RecordArgs),

    /// Inspect and mutate user profile blueprint (USER_PROFILE.md)
    Profile(ProfileArgs),

    /// Manage project domain specialties
    Specialty(SpecialtyArgs),

    /// Manage subagent lifecycle, checkpointing, and power throttling
    Subagent(SubagentArgs),

    /// Multi-agent coordination and task state ledger
    Task(TaskArgs),

    /// Inspect and drain serialized background work queue
    Queue(QueueArgs),

    /// Cross-platform perceptual delta screen capture and visual memory
    Screen(ScreenArgs),

    /// Manage always-on background daemon and boot autostart
    Daemon(DaemonArgs),

    /// Generate high-density compaction carryover memory anchor
    Carryover(CarryoverArgs),

    /// Generate visual daily cognitive executive digest
    Digest(DigestArgs),

    /// Manage privacy safeguards, blacklists, and security gatekeepers
    Safeguard(SafeguardArgs),

    /// Fast token-efficient AST symbol search across workspace projects
    Def(DefArgs),

    /// Validate and synchronize memories in prompts.jsonl
    Sync(SyncArgs),

    /// Autonomous continuous learning across workspaces
    Learn(PassthroughArgs),

    /// Google-style live web search with AI quick summaries
    Web(PassthroughArgs),

    /// Clean web text & markdown extraction
    Fetch(FetchArgs),

    /// Deep autonomous research synthesis
    Research(PassthroughArgs),

    /// Universal migration engine for AI harnesses and settings
    Migrate(PassthroughArgs),

    /// Fast pure-CPU OCR on images and frames
    Ocr(PassthroughArgs),

    /// Audit active memories and deprecate conflicting entries
    Reconcile(PassthroughArgs),

    /// Local sovereign DeepWiki knowledge engine
    Wiki(WikiArgs),

    /// Cognitive execution patterns and reflexes
    Pattern(PassthroughArgs),

    /// Export structured context blocks for external LLMs
    Context(PassthroughArgs),

    /// YouTube video transcript extraction and indexing
    Youtube(PassthroughArgs),

    /// Email notification and ingest client
    Email(PassthroughArgs),

    /// Multi-channel quick capture HTTP webhook gateway
    Webhook(WebhookArgs),

    /// Start native stdio Model Context Protocol (MCP) server for AI agents
    Mcp,
}

#[derive(Args, Debug)]
pub struct SearchArgs {
    /// Search query string
    pub query: String,

    /// Optional category filter (e.g. preferences, architecture, hardware)
    #[arg(short, long)]
    pub category: Option<String>,

    /// Maximum results to return
    #[arg(short, long, default_value_t = 5)]
    pub limit: usize,

    /// Output raw JSON format
    #[arg(long)]
    pub json: bool,

    /// Output compact bullet points
    #[arg(long)]
    pub compact: bool,
}

#[derive(Args, Debug)]
pub struct RecordArgs {
    /// Fact, preference, or architectural milestone to record
    pub content: String,

    /// Category for memory classification
    #[arg(short, long, default_value = "general")]
    pub category: String,

    /// Source attribution (e.g. agent, user, cli)
    #[arg(short, long, default_value = "agent")]
    pub source: String,

    /// Explicit tags to attach
    #[arg(short, long)]
    pub tags: Option<Vec<String>>,
}

#[derive(Args, Debug)]
pub struct ProfileArgs {
    /// Targeted section name to extract (e.g. 'hardware', 'cinema')
    #[arg(short, long)]
    pub section: Option<String>,

    /// List all section headings in USER_PROFILE.md
    #[arg(long)]
    pub list: bool,

    /// Target section name to update
    #[arg(long)]
    pub update_section: Option<String>,

    /// Bullet content to insert/replace
    #[arg(long)]
    pub bullet: Option<String>,

    /// Replace existing section content instead of appending
    #[arg(long)]
    pub replace: bool,

    /// Output JSON format
    #[arg(long)]
    pub json: bool,
}

#[derive(Args, Debug)]
pub struct SpecialtyArgs {
    #[command(subcommand)]
    pub action: Option<SpecialtySubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum SpecialtySubcommands {
    /// List all available domain specialties
    List {
        #[arg(long)]
        json: bool,
    },
    /// Retrieve full specification for a domain specialty module
    Get {
        slug: String,
        #[arg(short, long, default_value = "global")]
        project: String,
        #[arg(long)]
        json: bool,
    },
    /// Create or update a specialty module
    Create {
        slug: String,
        #[arg(short, long, default_value = "global")]
        project: String,
        #[arg(short, long)]
        title: Option<String>,
        #[arg(short, long, default_value = "")]
        content: String,
    },
}

#[derive(Args, Debug)]
pub struct SubagentArgs {
    #[command(subcommand)]
    pub action: Option<SubagentSubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum SubagentSubcommands {
    /// Inspect resource governor telemetry, safe concurrency, and thermal state
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Record a subagent task checkpoint for crash resilience
    Checkpoint {
        task_id: String,
        #[arg(short, long, default_value_t = 0)]
        step: i32,
        #[arg(long)]
        state: Option<String>,
    },
    /// Resume an interrupted subagent task
    Resume {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
    /// List all subagent tasks
    List {
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Debug)]
pub struct TaskArgs {
    #[command(subcommand)]
    pub action: Option<TaskSubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum TaskSubcommands {
    /// List active tasks in the multi-agent ledger
    List {
        #[arg(long)]
        json: bool,
    },
    /// Inspect details for a specific task
    Get {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
    /// Resume an interrupted task and build agent brief
    Resume {
        task_id: String,
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Debug)]
pub struct QueueArgs {
    #[command(subcommand)]
    pub action: Option<QueueSubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum QueueSubcommands {
    /// View queue status and metrics
    Status {
        #[arg(long)]
        json: bool,
    },
    /// List jobs in the queue
    List {
        #[arg(short, long, default_value_t = 25)]
        limit: usize,
        #[arg(long)]
        json: bool,
    },
    /// Drain pending queue jobs sequentially
    Run,
    /// Clear completed and failed jobs
    Clear {
        #[arg(long, default_value_t = 0)]
        hours: i64,
    },
}

#[derive(Args, Debug)]
pub struct ScreenArgs {
    #[command(subcommand)]
    pub action: Option<ScreenSubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum ScreenSubcommands {
    /// Capture active desktop keyframe and enqueue OCR
    Snap {
        #[arg(long)]
        force: bool,
        #[arg(long)]
        json: bool,
    },
    /// Inspect screen memory status
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Enable continuous desktop screen memory capture
    Enable,
    /// Disable continuous desktop screen memory capture
    Disable,
    /// Prune old keyframes older than N days
    Prune {
        #[arg(long, default_value_t = 14)]
        days: u32,
        #[arg(long)]
        json: bool,
    },
}

#[derive(Args, Debug)]
pub struct DaemonArgs {
    #[command(subcommand)]
    pub action: Option<DaemonSubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum DaemonSubcommands {
    /// Run the background supervisor loop
    Run {
        #[arg(short, long, default_value_t = 90)]
        interval: u64,
    },
    /// Install automatic startup on login/boot across platforms
    Autostart,
    /// Check background daemon process status
    Status,
    /// Stop background daemon
    Stop,
}

#[derive(Args, Debug)]
pub struct CarryoverArgs {
    #[arg(short, long)]
    pub specialty: Option<String>,
    #[arg(long)]
    pub json: bool,
}

#[derive(Args, Debug)]
pub struct DigestArgs {
    /// Specific date (YYYY-MM-DD), defaults to today
    #[arg(short, long)]
    pub date: Option<String>,
    #[arg(long)]
    pub json: bool,
}

#[derive(Args, Debug)]
pub struct SafeguardArgs {
    #[command(subcommand)]
    pub action: Option<SafeguardSubcommands>,
}

#[derive(Subcommand, Debug)]
pub enum SafeguardSubcommands {
    /// Display current safeguard configuration and blacklists
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Add a process name to blacklist
    AddProc {
        name: String,
    },
    /// Add a window title regex pattern to blacklist
    AddTitle {
        pattern: String,
    },
    /// Remove a process from blacklist
    RemoveProc {
        name: String,
    },
    /// Remove a window title pattern from blacklist
    RemoveTitle {
        pattern: String,
    },
}

#[derive(Args, Debug)]
pub struct DefArgs {
    /// Symbol name to search for (function, class, struct, type)
    pub symbol: String,
    /// Target directory to scan (defaults to current dir)
    #[arg(short, long)]
    pub path: Option<String>,
    /// Match exact symbol name
    #[arg(short, long)]
    pub exact: bool,
    #[arg(long)]
    pub json: bool,
}

#[derive(Args, Debug)]
pub struct SyncArgs {
    #[arg(long)]
    pub json: bool,
}

#[derive(Args, Debug)]
pub struct FetchArgs {
    /// Target webpage or YouTube URL
    pub url: String,

    /// Output raw JSON format
    #[arg(long)]
    pub json: bool,

    /// Pass through additional CLI arguments
    #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
    pub extra: Vec<String>,
}

#[derive(Args, Debug)]
pub struct WikiArgs {
    #[command(subcommand)]
    pub action: Option<WikiSubcommands>,

    /// Port to serve on (default: 7433)
    #[arg(short, long, default_value_t = 7433)]
    pub port: u16,
}

#[derive(Subcommand, Debug)]
pub enum WikiSubcommands {
    /// Serve generated DeepWiki on local HTTP server
    Serve {
        #[arg(short, long, default_value_t = 7433)]
        port: u16,
    },
    /// Generate offline Markdown documentation
    Generate,
}

#[derive(Args, Debug)]
pub struct WebhookArgs {
    #[command(subcommand)]
    pub action: Option<WebhookSubcommands>,

    /// Webhook port (default: 7434)
    #[arg(short, long, default_value_t = 7434)]
    pub port: u16,

    /// Optional Bearer authentication token
    #[arg(long)]
    pub token: Option<String>,
}

#[derive(Subcommand, Debug)]
pub enum WebhookSubcommands {
    /// Start foreground HTTP webhook receiver
    Serve {
        #[arg(short, long, default_value_t = 7434)]
        port: u16,
        #[arg(long)]
        token: Option<String>,
    },
    /// Check webhook receiver status
    Status {
        #[arg(short, long, default_value_t = 7434)]
        port: u16,
    },
    /// Send a quick memory directly to the webhook receiver
    Send {
        text: String,
        #[arg(short, long, default_value = "quick_note")]
        category: String,
        #[arg(short, long, default_value_t = 7434)]
        port: u16,
    },
}

#[derive(Args, Debug)]
pub struct PassthroughArgs {
    #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
    pub args: Vec<String>,
}

