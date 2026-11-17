"""Curated specialties: Backend, Databases, and Protocols."""
from typing import Any, Dict

BACKEND_SPECIALTIES: Dict[str, Dict[str, Any]] = {
    "golang": {
        "name": "Idiomatic Go Systems Engineering",
        "slug": "golang",
        "tags": ["golang", "go", "concurrency", "backend", "systems", "microservices"],
        "user_preferences": ["explicit_errors", "context_propagation", "goroutine_lifecycle", "clean_architecture"],
        "fundamentals": (
            "Idiomatic Go engineering prioritizing simplicity, explicit syntax, composition over inheritance, and zero magic. "
            "Enforces explicit error handling (errors are values, wrapped with fmt.Errorf('%w') and checked with errors.Is/errors.As), "
            "the Communicating Sequential Processes (CSP) concurrency model ('Do not communicate by sharing memory; instead, share "
            "memory by communicating' via channels and sync primitives), and ubiquitous context.Context propagation through all I/O "
            "boundaries for timeout and cancellation control. Favors the rich standard library over bloated external dependencies."
        ),
        "key_takeaways": [
            "Explicit error wrapping: never ignore errors with '_'; wrap errors with context (fmt.Errorf('fetch feed %s: %w', url, err)) for traceable root causes.",
            "First parameter ctx context.Context: propagate context through all async, database, and network calls; respect ctx.Err().",
            "Goroutine lifecycle control: never launch a goroutine without knowing how and when it will terminate; use sync.WaitGroup or errgroup.",
            "Clean directory layout: structure projects using standard Go layout (cmd/<app>/main.go, internal/feed/, internal/storage/, pkg/).",
            "Avoid interface pollution: declare interfaces where they are consumed (client side), not where they are implemented; keep interfaces tiny (1-2 methods)."
        ],
        "github_repos": [
            {
                "name": "golang/go",
                "url": "https://github.com/golang/go",
                "stars": "126k+",
                "description": "The Go programming language."
            },
            {
                "name": "uber-go/guide",
                "url": "https://github.com/uber-go/guide",
                "stars": "16k+",
                "description": "The Uber Go Style Guide—clean coding standards and performance patterns."
            },
            {
                "name": "gocolly/colly",
                "url": "https://github.com/gocolly/colly",
                "stars": "22k+",
                "description": "Fast and elegant scraping framework for Gophers."
            }
        ]
    },

    "nodejs": {
        "name": "Modern Node.js & Bun Server Runtime Architecture",
        "slug": "nodejs",
        "tags": ["nodejs", "bun", "javascript", "typescript", "backend", "runtime"],
        "user_preferences": ["native_esm", "abort_signals", "stream_processing", "low_overhead_logging"],
        "fundamentals": (
            "Modern Node.js (v20+ / v22 LTS) and Bun runtime engineering leveraging native ESM (import/export), top-level await, "
            "native Web APIs (fetch, Request, Response, FormData), and non-blocking event loop ergonomics. Offloads CPU-intensive "
            "tasks to Worker Threads to keep the main event loop responsive. Processes high-volume data feeds and files via "
            "streams (stream/promises pipeline) for constant O(1) memory footprint. Utilizes native AbortController/AbortSignal.timeout "
            "for robust request cancellations, and enforces structured JSON logging via Pino for high performance."
        ),
        "key_takeaways": [
            "Native ESM & Top-Level Await: use standard '\"type\": \"module\"' in package.json; avoid CommonJS require() in modern projects.",
            "Never block the event loop: offload heavy cryptographic hashes, image resizing, or CPU parsing to Worker Threads or external services.",
            "Native AbortSignal for timeouts: pass signal: AbortSignal.timeout(5000) into fetch() calls to prevent hung HTTP connections.",
            "Stream large payloads: process XML feeds, large files, and exports using streams (pipeline) to guarantee constant O(1) memory usage.",
            "Structured logging with Pino: log JSON with timestamp, level, context, and error stacks; avoid unstructured console.log in production."
        ],
        "github_repos": [
            {
                "name": "nodejs/node",
                "url": "https://github.com/nodejs/node",
                "stars": "108k+",
                "description": "Node.js JavaScript runtime built on Chrome's V8 engine."
            },
            {
                "name": "pinojs/pino",
                "url": "https://github.com/pinojs/pino",
                "stars": "14k+",
                "description": "Super fast, low-overhead JSON logger for Node.js."
            },
            {
                "name": "oven-sh/bun",
                "url": "https://github.com/oven-sh/bun",
                "stars": "76k+",
                "description": "Incredibly fast all-in-one JavaScript runtime, bundler, and package manager."
            }
        ]
    },

    "postgresql": {
        "name": "PostgreSQL Relational Modeling & Performance Tuning",
        "slug": "postgresql",
        "tags": ["postgresql", "postgres", "sql", "database", "acid", "performance"],
        "user_preferences": ["acid_compliance", "foreign_key_indexes", "partial_indexes", "connection_pooling"],
        "fundamentals": (
            "Advanced relational database modeling and performance optimization on PostgreSQL. Enforces strict relational integrity "
            "via ACID transactions, foreign keys, and check constraints. Leverages targeted indexing strategies (B-Tree for equality/range, "
            "GIN for full-text and JSONB queries, partial indexes for active/pending flags) to minimize index size. Diagnoses query plans "
            "via EXPLAIN (ANALYZE, BUFFERS), mandates connection pooling (PgBouncer) for high concurrency, and utilizes JSONB for "
            "semi-structured feed metadata while keeping queryable entity identifiers strictly relational."
        ),
        "key_takeaways": [
            "Index foreign keys and search paths: always create indexes on foreign key columns and frequently filtered columns (created_at, status).",
            "Use partial indexes for state flags: index only active or pending rows (WHERE processed = false) to reduce index size by up to 90%.",
            "Connection pooling is non-negotiable: place PgBouncer or connection pooler between application workers and Postgres to avoid connection exhaustion.",
            "JSONB for flexible schemas, relational for core entities: use relational columns for foreign keys and queries; reserve jsonb for polymorphic payload data.",
            "Safe migrations: avoid long table locks in production; use CONCURRENTLY for index creation and nullable additions for new columns."
        ],
        "github_repos": [
            {
                "name": "postgres/postgres",
                "url": "https://github.com/postgres/postgres",
                "stars": "16k+",
                "description": "PostgreSQL database source code."
            },
            {
                "name": "pgbouncer/pgbouncer",
                "url": "https://github.com/pgbouncer/pgbouncer",
                "stars": "3k+",
                "description": "Lightweight connection pooler for PostgreSQL."
            },
            {
                "name": "jackc/pgx",
                "url": "https://github.com/jackc/pgx",
                "stars": "10k+",
                "description": "PostgreSQL driver and toolkit for Go."
            }
        ]
    },

    "drizzle-orm": {
        "name": "Drizzle ORM & Type-Safe SQL Architecture",
        "slug": "drizzle-orm",
        "tags": ["drizzle-orm", "typescript", "database", "postgres", "sql", "orm"],
        "user_preferences": ["type_safe_sql", "zero_overhead", "schema_single_source", "drizzle_kit"],
        "fundamentals": (
            "TypeScript-first, zero-overhead SQL ORM that maps directly to pure SQL without heavy runtime overhead or hidden queries. "
            "Treats the TypeScript schema definition (pgTable) as the single source of truth, inferring select and insert types "
            "automatically (InferSelectModel, InferInsertModel). Offers the best of both worlds: relational queries (db.query) for "
            "nested object relationships and query builders (db.select) for exact SQL query control. Features declarative diff-based "
            "schema migrations via Drizzle Kit."
        ),
        "key_takeaways": [
            "Infer types from schema: derive all input and output TypeScript types using typeof table.$inferSelect and typeof table.$inferInsert; never duplicate types manually.",
            "Batch relations to prevent N+1 queries: use db.query.<table_name>.findMany({ with: { ... } }) which executes batched relational lookups.",
            "Separate migration scripts from runtime: run database migrations in a dedicated CI/CD or pre-start script; never run auto-migration inside serverless request paths.",
            "Raw SQL escape hatch with sql: use the sql template tag for complex Postgres functions (tsvector, CTEs, window functions) while maintaining type safety.",
            "Explicit timestamps with timezone: define timestamps as timestamp({ withTimezone: true, mode: 'date' }) to avoid UTC conversion bugs."
        ],
        "github_repos": [
            {
                "name": "drizzle-team/drizzle-orm",
                "url": "https://github.com/drizzle-team/drizzle-orm",
                "stars": "37k+",
                "description": "TypeScript ORM that lets you say 'I love SQL'."
            },
            {
                "name": "drizzle-team/drizzle-kit",
                "url": "https://github.com/drizzle-team/drizzle-kit",
                "stars": "5k+",
                "description": "Migration and prototyping CLI companion for Drizzle ORM."
            }
        ]
    },

    "html-email-design": {
        "name": "Cross-Client HTML Email Architecture & Compatibility",
        "slug": "html-email-design",
        "tags": ["html-email", "email-design", "react-email", "mjml", "outlook-compat"],
        "user_preferences": ["bulletproof_tables", "inline_css", "outlook_vml", "dark_mode_tested"],
        "fundamentals": (
            "Cross-client HTML email engineering addressing 20+ years of email client rendering fragmentation. Accounts for "
            "Microsoft Outlook's Microsoft Word rendering engine (no CSS grid, no flexbox, poor box-model support) by utilizing nested "
            "HTML <table> structures with explicit presentation attributes (cellpadding='0' cellspacing='0' border='0'). Inlines all "
            "critical CSS directly on elements to bypass webmail style-stripping (Gmail). Utilizes MSO conditional comments "
            "(<!--[if mso]>) for Outlook VML buttons and tables, and adopts modern compilation frameworks (React Email, MJML) "
            "to write modern JSX/MJML that compiles down to bulletproof HTML."
        ),
        "key_takeaways": [
            "Compile via React Email or MJML: write clean, maintainable JSX/MJML components and let compilers generate bulletproof, table-based fallback HTML.",
            "Inline all critical CSS: ensure all layout, typography, and color CSS rules are inlined directly onto HTML elements before dispatch.",
            "Always specify image dimensions: provide explicit width and height attributes on <img> tags along with style='display: block; border: 0' to prevent spacing glitches.",
            "MSO conditional wrappers for multi-column grids: wrap multi-column layouts in <!--[if mso]><table role='presentation'><tr><td><![endif]--> to prevent column dropping in Outlook.",
            "Keep email width between 600px and 640px: standard email clients and desktop preview panes render optimally at 600px max width."
        ],
        "github_repos": [
            {
                "name": "resend/react-email",
                "url": "https://github.com/resend/react-email",
                "stars": "14k+",
                "description": "Build and send modern HTML emails using React and TypeScript."
            },
            {
                "name": "mjmlio/mjml",
                "url": "https://github.com/mjmlio/mjml",
                "stars": "16k+",
                "description": "The only framework that makes responsive-email easy."
            },
            {
                "name": "hteumeuleu/email-bugs",
                "url": "https://github.com/hteumeuleu/email-bugs",
                "stars": "2k+",
                "description": "Documented quirks and bug repository for email client rendering engines."
            }
        ]
    },

    "email-delivery": {
        "name": "Transactional Email Delivery Infrastructure & Deliverability",
        "slug": "email-delivery",
        "tags": ["email", "deliverability", "resend", "ses", "spf", "dkim", "dmarc"],
        "user_preferences": ["high_reputation", "spf_dkim_dmarc", "bounce_suppression", "rate_throttled"],
        "fundamentals": (
            "High-deliverability transactional and notification email infrastructure using modern HTTP REST APIs (Resend, AWS SES) "
            "over legacy blocking SMTP. Enforces the complete authentication triad: SPF (Sender Policy Framework), 2048-bit DKIM "
            "cryptographic signing, and strict DMARC alignment (p=quarantine or p=reject). Protects sender reputation by isolating "
            "transactional notifications on dedicated subdomains (news.getmynews.org), throttling outbound dispatches through BullMQ, "
            "subscribing to delivery webhooks for instant hard-bounce (5xx) suppression, and implementing RFC 8058 One-Click Unsubscribe headers."
        ),
        "key_takeaways": [
            "Strict DNS authentication: never send email without verified SPF, DKIM 2048-bit keys, and a p=reject or p=quarantine DMARC policy.",
            "Isolate sending domains: send transactional notifications from a dedicated subdomain (e.g. news.getmynews.org) to protect root domain reputation.",
            "Immediate bounce suppression: listen to delivery webhooks and permanently deactivate recipients that return 5xx hard bounces or spam complaints.",
            "RFC 8058 One-Click Unsubscribe: include List-Unsubscribe headers in every digest and broadcast email to prevent spam classifications.",
            "Rate-limiting outbound dispatches: throttle email dispatches through BullMQ queues to respect API limits and prevent reputation spikes."
        ],
        "github_repos": [
            {
                "name": "resend/resend-node",
                "url": "https://github.com/resend/resend-node",
                "stars": "2k+",
                "description": "Node.js SDK for Resend Email API."
            },
            {
                "name": "nodemailer/nodemailer",
                "url": "https://github.com/nodemailer/nodemailer",
                "stars": "16k+",
                "description": "Easy as cake email sending with Node.js."
            },
            {
                "name": "mailgun/mailgun-go",
                "url": "https://github.com/mailgun/mailgun-go",
                "stars": "1k+",
                "description": "Go library for transactional email delivery."
            }
        ]
    },

    "discord-webhook-apps": {
        "name": "Discord Webhook & Bot Application Integration",
        "slug": "discord-webhook-apps",
        "tags": ["discord", "webhooks", "bot-api", "embeds", "rate-limiting"],
        "user_preferences": ["rate_limit_resilience", "rich_embeds", "secure_tokens", "slash_commands"],
        "fundamentals": (
            "Discord webhook and bot architecture for high-density, real-time community notifications and interactions. "
            "Leverages channel webhooks for zero-overhead, fire-and-forget HTTP POST dispatch of rich Embed cards (title, url, "
            "thumbnail, category color coding, footer timestamps) without maintaining a persistent WebSocket connection. Implements "
            "strict rate-limit handling by parsing X-RateLimit-Reset-After and 429 Retry-After response headers with exponential "
            "backoff. Integrates discord.js for interactive bots supporting slash commands (/subscribe, /settings) and button interactions."
        ),
        "key_takeaways": [
            "Rate-limit header compliance: parse X-RateLimit-Remaining and retry_after; enforce queue delays in BullMQ before dispatching to Discord webhooks.",
            "Respect character limits: truncate title (256 chars) and description (4096 chars) defensively in your service layer before calling Discord.",
            "Color coding by category: use hex color integers in embeds (e.g. 0x5865F2 blurple, 0x2ECC71 green, 0xE74C3C urgent) for visual recognition.",
            "Secure webhook URLs: treat webhook URLs as secrets; never expose them to client browsers or commit them into git repositories.",
            "Interactive bots with Slash Commands: register Discord application slash commands (/subscribe, /settings) using Discord REST API for zero-friction setup."
        ],
        "github_repos": [
            {
                "name": "discordjs/discord.js",
                "url": "https://github.com/discordjs/discord.js",
                "stars": "25k+",
                "description": "A powerful JavaScript library for interacting with the Discord API."
            },
            {
                "name": "bwmarrin/discordgo",
                "url": "https://github.com/bwmarrin/discordgo",
                "stars": "4k+",
                "description": "Go bindings for Discord."
            },
            {
                "name": "discord/discord-api-docs",
                "url": "https://github.com/discord/discord-api-docs",
                "stars": "6k+",
                "description": "Official Discord API documentation and specifications."
            }
        ]
    },

    "telegram-bot-api": {
        "name": "Telegram Bot API & Interactive Messaging",
        "slug": "telegram-bot-api",
        "tags": ["telegram", "bot-api", "telegraf", "messaging", "push-notifications"],
        "user_preferences": ["markdown_v2_escaping", "deep_link_auth", "inline_keyboards", "safe_chunking"],
        "fundamentals": (
            "Telegram Bot API integration for instant, interactive push messaging. Employs HTTPS Webhooks (setWebhook with secret_token "
            "verification) for low-latency production delivery and long polling for local development. Utilizes Telegraf / grammY "
            "frameworks with Inline Keyboards (InlineKeyboardMarkup) for interactive buttons ('Open Link', 'Save for Later', 'Mute'). "
            "Strictly escapes dynamic strings to comply with MarkdownV2 syntax (escaping 18 reserved characters to prevent 400 Bad Request "
            "parser errors). Defensively chunks messages exceeding Telegram's 4096-character limit."
        ),
        "key_takeaways": [
            "MarkdownV2 escape helper is mandatory: run all dynamic text (titles, summaries, author names) through a strict character escaping function before sending.",
            "Deep linking for account binding: generate one-time connection tokens in your dashboard; redirect users to https://t.me/<bot_username>?start=<token> for 1-click account pairing.",
            "Inline keyboard pagination and actions: attach inline buttons ('Open Article', 'Save for Later', 'Mute Topic') directly beneath message cards.",
            "Message chunking at 4000 characters: defensively chunk long summaries into consecutive messages to stay safely below Telegram's 4096-character hard limit.",
            "Webhook verification with secret token: set secret_token when configuring setWebhook, and verify the X-Telegram-Bot-Api-Secret-Token header on incoming requests."
        ],
        "github_repos": [
            {
                "name": "telegraf/telegraf",
                "url": "https://github.com/telegraf/telegraf",
                "stars": "7k+",
                "description": "Modern Telegram Bot framework for Node.js."
            },
            {
                "name": "grammyjs/grammY",
                "url": "https://github.com/grammyjs/grammY",
                "stars": "4k+",
                "description": "Next-generation Telegram Bot framework for TypeScript/JavaScript."
            },
            {
                "name": "go-telegram-bot-api/telegram-bot-api",
                "url": "https://github.com/go-telegram-bot-api/telegram-bot-api",
                "stars": "5k+",
                "description": "Golang bindings for the Telegram Bot API."
            }
        ]
    }
}
