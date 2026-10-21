#!/usr/bin/env python3
"""
Cephalo Autonomous Specialty Synthesizer & Knowledge Engine
============================================================
Provides automated knowledge synthesis and specialty generation for:
1. Curated foundational technologies, frameworks, UI/UX, and methodologies.
2. Dynamic synthesis for ANY novel or unknown technology/methodology.
3. Automated text discovery & extraction from prompts, docs, or project files.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def slugify(text: str) -> str:
    """Converts a string into a clean filesystem slug."""
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9\-]', '', text)
    return text or "default"


# Curated, battle-tested knowledge bank for core engineering disciplines
CURATED_SPECIALTIES: Dict[str, Dict[str, Any]] = {
    "coding-craftsmanship": {
        "name": "Software Engineering Craftsmanship & Anti-Slop Discipline",
        "slug": "coding-craftsmanship",
        "tags": ["coding", "anti-slop", "engineering", "best-practices", "typescript", "architecture"],
        "user_preferences": ["anti_slop", "clean_code", "minimal_indirection", "strict_types", "explicit_errors"],
        "fundamentals": (
            "Rigorous software engineering discipline designed to eliminate 'AI slop' (hallucinated abstractions, "
            "useless wrappers, boilerplate placeholders, and swallowed errors). Synthesizes Matt Pocock's "
            "'Skills for Real Engineers' (specs before tickets, tickets before code, vertical slices, structured grilling) "
            "with the Linux Kernel coding philosophy (Linus Torvalds: functions fit on 1-2 screens, maximum 3 levels of "
            "indentation, self-evident code without comments explaining basic syntax, minimal indirection, and explicit "
            "error handling at the call site). Enforces the Rule of Three (no speculative generic abstractions before 3 "
            "real use cases), explicit type boundaries with zero 'as unknown as any' escapes, and zero dead code."
        ),
        "key_takeaways": [
            "Specification before implementation: write crisp domain specs and types first; implement in isolated, testable vertical slices.",
            "Maximum 3 levels of indentation: invert 'if' conditions with early returns; keep functions focused on a single responsibility.",
            "Anti-AI-slop hygiene: ban generic empty helpers, hallucinated packages, redundant wrapper classes, and comments explaining trivial syntax.",
            "No speculative abstractions: write concrete, straightforward code; abstract only when 3 distinct call sites share identical invariants.",
            "Explicit error handling: never swallow errors or discard stack traces; attach descriptive context at the boundary.",
            "Strict type boundaries: no 'any', no unsafe type assertions; validate all external boundary inputs with runtime schemas (Zod/Pydantic)."
        ],
        "github_repos": [
            {
                "name": "mattpocock/skills",
                "url": "https://github.com/mattpocock/skills",
                "stars": "3.5k+",
                "description": "Skills for real software engineers driving AI coding agents with discipline and guardrails against drift."
            },
            {
                "name": "torvalds/linux",
                "url": "https://github.com/torvalds/linux",
                "stars": "180k+",
                "description": "The Linux kernel source tree—gold standard for simplicity, minimal indirection, and robust error paths."
            },
            {
                "name": "goldbergyoni/nodebestpractices",
                "url": "https://github.com/goldbergyoni/nodebestpractices",
                "stars": "98k+",
                "description": "Curated Node.js engineering best practices, error handling conventions, and architecture patterns."
            },
            {
                "name": "uber-go/guide",
                "url": "https://github.com/uber-go/guide",
                "stars": "16k+",
                "description": "Uber Go Style Guide—clean, pragmatic idioms for production-grade software engineering."
            }
        ]
    },

    "ui-ux-design": {
        "name": "Modern UI/UX Design Systems & Ergonomics",
        "slug": "ui-ux-design",
        "tags": ["ui-ux", "design-system", "accessibility", "tailwind", "radix", "heuristics"],
        "user_preferences": ["clean_ui", "wcag_aa", "token_based", "responsive", "micro_interactions"],
        "fundamentals": (
            "Modern user interface and user experience design architecture grounded in Nielsen Norman Group (NN/g) "
            "usability heuristics, Refactoring UI principles, and WCAG 2.1 AA accessibility standards. Features a tokenized "
            "design system architecture (CSS variables for colors, typography, spacing, and elevation), seamless dark mode "
            "transitions without class bloat, and four mandatory states for all async views (Loading/Skeleton, Error with retry, "
            "Empty with clear CTA, and Populated). Focuses on mobile-first responsive ergonomics, minimum 44x44px touch targets, "
            "and purposeful micro-interactions (150-250ms ease-out) that deliver immediate tactile feedback."
        ),
        "key_takeaways": [
            "Design system tokens first: define colors, spacing, and typography as CSS variables; never hardcode arbitrary hex codes in components.",
            "Four mandatory UI states: every async view must explicitly handle Loading (skeletons), Error (actionable retry), Empty (helpful CTA), and Populated.",
            "Strict WCAG 2.1 AA compliance: ensure 4.5:1 text contrast ratios, visible focus rings, aria-labels on icon buttons, and full keyboard navigability.",
            "Mobile-first ergonomics: design for primary thumb zones; enforce 44x44px minimum tap targets across touch viewports.",
            "Micro-interactions with purpose: use subtle CSS transitions (150-250ms ease-out) for state changes; avoid sluggish or gratuitous animations."
        ],
        "github_repos": [
            {
                "name": "tailwindlabs/tailwindcss",
                "url": "https://github.com/tailwindlabs/tailwindcss",
                "stars": "84k+",
                "description": "Utility-first CSS framework and design token system for modern web interfaces."
            },
            {
                "name": "radix-ui/primitives",
                "url": "https://github.com/radix-ui/primitives",
                "stars": "16k+",
                "description": "Unstyled, accessible UI components for React adhering strictly to WAI-ARIA authoring guidelines."
            },
            {
                "name": "lucide-icons/lucide",
                "url": "https://github.com/lucide-icons/lucide",
                "stars": "14k+",
                "description": "Beautiful, consistent, accessible icon library for modern web applications."
            },
            {
                "name": "shadcn-ui/ui",
                "url": "https://github.com/shadcn-ui/ui",
                "stars": "80k+",
                "description": "Re-usable components built with Radix UI and Tailwind CSS, giving 100% code ownership."
            }
        ]
    },

    "nextjs": {
        "name": "Next.js 15 Full-Stack App Architecture",
        "slug": "nextjs",
        "tags": ["nextjs", "react", "app-router", "rsc", "server-actions", "fullstack"],
        "user_preferences": ["app_router", "rsc_first", "server_actions", "streaming", "turbopack"],
        "fundamentals": (
            "Next.js 15 App Router architecture leveraging React Server Components (RSC) by default for zero client bundle "
            "overhead and direct database/backend access. Client Components ('use client') are pushed strictly to interactive leaf "
            "nodes. Mutations are colocated with Server Actions ('use server') featuring Zod payload validation and automatic "
            "revalidation via revalidateTag/revalidatePath. Employs incremental UI streaming with loading.tsx and React Suspense, "
            "Turbopack for sub-second hot module reloading, and isolated Route Handlers for external webhooks."
        ),
        "key_takeaways": [
            "Keep Server Components default: fetch data and access DB directly on the server; use 'use client' only at interactive leaf nodes.",
            "Colocate mutations with Server Actions: validate payloads with Zod on the server; trigger revalidatePath or revalidateTag on success.",
            "Granular streaming with Suspense: wrap slow data-fetching components in <Suspense fallback={<Skeleton />}> to eliminate blocking waterfalls.",
            "Route Handlers for webhooks & public APIs: reserve app/api/*/route.ts for external integrations and webhooks, not internal React UI fetching.",
            "Strict metadata and OpenGraph: define static and dynamic generateMetadata for SEO, social previews, and canonical links."
        ],
        "github_repos": [
            {
                "name": "vercel/next.js",
                "url": "https://github.com/vercel/next.js",
                "stars": "128k+",
                "description": "The React Framework for the Web with App Router, RSC, and Server Actions."
            },
            {
                "name": "shadcn-ui/taxonomy",
                "url": "https://github.com/shadcn-ui/taxonomy",
                "stars": "19k+",
                "description": "Open-source Next.js 15 App Router reference application with auth, subscriptions, and Drizzle/Prisma."
            },
            {
                "name": "t3-oss/create-t3-app",
                "url": "https://github.com/t3-oss/create-t3-app",
                "stars": "26k+",
                "description": "Type-safe Next.js fullstack stack patterns and conventions."
            }
        ]
    },

    "tailwindcss": {
        "name": "Tailwind CSS v4 & Utility Token Systems",
        "slug": "tailwindcss",
        "tags": ["tailwindcss", "css", "styling", "design-tokens", "frontend"],
        "user_preferences": ["utility_first", "css_variables", "no_dynamic_strings", "clean_markup"],
        "fundamentals": (
            "Tailwind CSS v4 modern utility-first architecture with CSS-first configuration via @theme and the high-speed "
            "Rust-based Oxide compiler. Emphasizes utility composition directly in markup over monolithic @apply abstractions. "
            "Integrates design tokens seamlessly with CSS variables (--background, --foreground, --radius) for instant theming "
            "and dark mode support. Strictly avoids dynamic class string interpolation (e.g. `bg-${color}-500`) to preserve "
            "static compiler scanning, pairing with clsx and tailwind-merge for conflict-free conditional styles."
        ),
        "key_takeaways": [
            "No dynamic string concatenation: Tailwind static scanner requires full class strings; use lookup dictionaries for dynamic variant styles.",
            "Avoid @apply sprawl: rely on React/HTML component composition rather than creating monolithic CSS classes with @apply.",
            "CSS variable-backed design tokens: map --background, --foreground, and brand colors to CSS variables for instant dark mode switching.",
            "Class merging hygiene: always merge conditional utility classes using clsx and tailwind-merge (cn() helper) to prevent specificity conflicts.",
            "Container queries for component isolation: use @container queries for card and widget components so they adapt to their parent container rather than viewport."
        ],
        "github_repos": [
            {
                "name": "tailwindlabs/tailwindcss",
                "url": "https://github.com/tailwindlabs/tailwindcss",
                "stars": "84k+",
                "description": "The core Tailwind CSS engine and repository."
            },
            {
                "name": "dcastilho/tailwind-merge",
                "url": "https://github.com/dcastilho/tailwind-merge",
                "stars": "4k+",
                "description": "Utility to merge Tailwind CSS classes in JS without style conflicts."
            },
            {
                "name": "lukeed/clsx",
                "url": "https://github.com/lukeed/clsx",
                "stars": "6k+",
                "description": "Tiny utility for constructing className strings conditionally."
            }
        ]
    },

    "shadcn-ui": {
        "name": "shadcn/ui Component Architecture & Primitives",
        "slug": "shadcn-ui",
        "tags": ["shadcn-ui", "radix", "react", "components", "accessibility"],
        "user_preferences": ["code_ownership", "accessible_primitives", "cva_variants", "zod_forms"],
        "fundamentals": (
            "Copy-paste component architecture where UI building blocks reside directly inside your codebase (components/ui/), "
            "eliminating third-party NPM dependency lock-in while granting complete styling and behavioral control. Built upon "
            "Radix UI unstyled, accessible primitives adhering to WAI-ARIA standards (full keyboard traps, ARIA attributes, portals). "
            "Employs Class Variance Authority (CVA) for type-safe component variants (variant='outline', size='sm') and pairs "
            "seamlessly with React Hook Form and Zod for robust client-side and server-side form validation."
        ),
        "key_takeaways": [
            "Direct code ownership: adapt and modify UI components directly in components/ui/ rather than fighting third-party library abstractions.",
            "Type-safe variants via CVA: define all visual states, sizes, and colors through cva() definitions with explicit TypeScript variant props.",
            "Form validation pairing: pair every input form with Zod schema inference and React Hook Form for client and server validation parity.",
            "Keyboard accessibility out of the box: never remove focus rings (focus-visible:ring-2) or disable Tab key navigation.",
            "Composition with asChild: leverage Radix UI's Slot / asChild pattern to pass styles to Next.js <Link> without invalid nested anchor tags."
        ],
        "github_repos": [
            {
                "name": "shadcn-ui/ui",
                "url": "https://github.com/shadcn-ui/ui",
                "stars": "80k+",
                "description": "The official shadcn/ui component registry and CLI."
            },
            {
                "name": "radix-ui/primitives",
                "url": "https://github.com/radix-ui/primitives",
                "stars": "16k+",
                "description": "Unstyled accessible UI primitives for modern React applications."
            },
            {
                "name": "joe-bell/cva",
                "url": "https://github.com/joe-bell/cva",
                "stars": "4k+",
                "description": "Class Variance Authority for managing component variants."
            }
        ]
    },

    "redis": {
        "name": "Redis High-Performance In-Memory Data Store",
        "slug": "redis",
        "tags": ["redis", "database", "cache", "in-memory", "pub-sub", "streams"],
        "user_preferences": ["sub_millisecond", "explicit_ttl", "no_keys_wildcard", "atomic_ops"],
        "fundamentals": (
            "In-memory key-value data structure store delivering sub-millisecond read/write latency across strings, hashes, "
            "lists, sets, sorted sets, and streams. Implements robust caching patterns (cache-aside, TTL expiration, volatile-lru "
            "eviction) to prevent unbounded RAM usage. Employs single-threaded atomic primitives (INCR, SETNX, HINCRBY) and Lua "
            "scripts (EVAL) for race-free multi-step mutations without complex distributed locking. Serves as the high-throughput "
            "backbone for BullMQ job queues, rate limiters, and session storage."
        ),
        "key_takeaways": [
            "Keyspace naming convention: format keys systematically as <project>:<entity>:<id>:<attr> (e.g. getmynews:feed:142:etag).",
            "Always enforce TTLs on cache keys: prevent unbounded RAM growth by setting explicit expiration times on all transient cache entries.",
            "Never run KEYS * in production: KEYS blocks the single-threaded Redis event loop; always use SCAN with cursor iteration.",
            "Atomic operations with Lua or SETNX: eliminate check-then-set race conditions using atomic SET ... NX EX locks or Lua scripts.",
            "Connection pooling & Keep-Alive: reuse Redis client connections via connection pools; never open and close connections per request."
        ],
        "github_repos": [
            {
                "name": "redis/redis",
                "url": "https://github.com/redis/redis",
                "stars": "67k+",
                "description": "The Redis in-memory database source code."
            },
            {
                "name": "redis/ioredis",
                "url": "https://github.com/redis/ioredis",
                "stars": "13k+",
                "description": "Robust, performance-focused, full-featured Redis client for Node.js."
            },
            {
                "name": "redis/go-redis",
                "url": "https://github.com/redis/go-redis",
                "stars": "20k+",
                "description": "Type-safe Redis client for Go."
            }
        ]
    },

    "bullmq": {
        "name": "BullMQ Distributed Job Queue & Workflows",
        "slug": "bullmq",
        "tags": ["bullmq", "redis", "queue", "background-jobs", "workers", "scheduling"],
        "user_preferences": ["job_id_dedup", "exponential_backoff", "worker_isolation", "graceful_shutdown"],
        "fundamentals": (
            "Distributed job queue and message processing engine built on Redis for Node.js and TypeScript. Manages complete "
            "job lifecycles (waiting, active, delayed, prioritized, completed, failed) with fine-grained concurrency control "
            "and queue-level rate limiting (e.g. max 10 jobs/sec for external webhooks). Ensures reliability through deterministic "
            "jobId deduplication, exponential backoff retries on transient errors, stalled job recovery via heartbeat locks, and "
            "graceful worker shutdown (SIGTERM handling) allowing in-flight jobs to finish cleanly."
        ),
        "key_takeaways": [
            "Enforce deterministic jobId: set jobId based on content hash or unique entity ID to guarantee deduplication at the queue boundary.",
            "Exponential backoff retry strategy: configure attempts: 5, backoff: { type: 'exponential', delay: 2000 } on external API jobs (Telegram, Discord, email).",
            "Worker concurrency tuning: tune worker concurrency based on I/O vs CPU workload; isolate heavy Playwright scrapers from light webhook senders.",
            "Graceful shutdown handler: listen for SIGTERM/SIGINT to call worker.close() allowing active in-flight jobs to finish before process exit.",
            "Cleanup completed and failed jobs: set removeOnComplete: { age: 3600, count: 1000 } and removeOnFail: { age: 86400 } to avoid Redis RAM exhaustion."
        ],
        "github_repos": [
            {
                "name": "taskforcesh/bullmq",
                "url": "https://github.com/taskforcesh/bullmq",
                "stars": "4k+",
                "description": "Modern TypeScript distributed message queue and batching architecture for Redis."
            },
            {
                "name": "OptimalBits/bull",
                "url": "https://github.com/OptimalBits/bull",
                "stars": "15k+",
                "description": "The predecessor Redis queue library with foundational design patterns."
            },
            {
                "name": "felixmosh/bull-board",
                "url": "https://github.com/felixmosh/bull-board",
                "stars": "4k+",
                "description": "UI dashboard for inspecting Bull and BullMQ queues, active jobs, and failure traces."
            }
        ]
    },

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


# Aliases mapping common search terms to curated specialty slugs
SPECIALTY_ALIASES: Dict[str, str] = {
    "coding": "coding-craftsmanship",
    "craftsmanship": "coding-craftsmanship",
    "real-engineer": "coding-craftsmanship",
    "anti-slop": "coding-craftsmanship",
    "anti-ai-slop": "coding-craftsmanship",
    "clean-code": "coding-craftsmanship",
    "ui": "ui-ux-design",
    "ux": "ui-ux-design",
    "ui/ux": "ui-ux-design",
    "ui-ux": "ui-ux-design",
    "next": "nextjs",
    "next.js": "nextjs",
    "next-js": "nextjs",
    "tailwind": "tailwindcss",
    "tailwind-css": "tailwindcss",
    "shadcn": "shadcn-ui",
    "shadcn/ui": "shadcn-ui",
    "go": "golang",
    "node": "nodejs",
    "node.js": "nodejs",
    "node-js": "nodejs",
    "postgres": "postgresql",
    "postresql": "postgresql",
    "drizzle": "drizzle-orm",
    "html-email": "html-email-design",
    "email": "email-delivery",
    "email-sending": "email-delivery",
    "discord": "discord-webhook-apps",
    "discord-webhook": "discord-webhook-apps",
    "discord-webhooks": "discord-webhook-apps",
    "telegram": "telegram-bot-api",
    "telegram-bot": "telegram-bot-api",
}


class SpecialtySynthesizer:
    """Intelligently resolves, synthesizes, and generates domain specialties."""

    @staticmethod
    def resolve_slug(topic: str) -> str:
        """Resolves topic string or alias to a canonical specialty slug."""
        raw_slug = slugify(topic)
        # Check alias dictionary
        if raw_slug in SPECIALTY_ALIASES:
            return SPECIALTY_ALIASES[raw_slug]
        # Check direct match
        for key in CURATED_SPECIALTIES:
            if raw_slug == key or raw_slug.replace("-", "") == key.replace("-", ""):
                return key
        return raw_slug

    @classmethod
    def get_curated(cls, topic: str) -> Optional[Dict[str, Any]]:
        """Returns pre-compiled curated data for a topic if available."""
        slug = cls.resolve_slug(topic)
        return CURATED_SPECIALTIES.get(slug)

    @classmethod
    def synthesize(
        cls,
        topic: str,
        project: str = "global",
        custom_fundamentals: Optional[str] = None,
        custom_takeaways: Optional[List[str]] = None,
        custom_repos: Optional[List[Dict[str, Any]]] = None,
        user_preferences: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes a production-grade specialty:
        - If the topic is in the curated bank, utilizes the expert verified content.
        - If unknown, dynamically generates an architectural profile based on domain heuristics.
        """
        slug = cls.resolve_slug(topic)
        curated = CURATED_SPECIALTIES.get(slug)

        if curated:
            name = curated["name"]
            fundamentals = custom_fundamentals or curated["fundamentals"]
            takeaways = custom_takeaways or curated["key_takeaways"]
            repos = custom_repos or curated["github_repos"]
            prefs = user_preferences or curated["user_preferences"]
            tags = curated.get("tags", [slug, project])
        else:
            # Dynamic Autonomous Synthesis for Novel / Unknown Technology or Methodology
            clean_title = topic.replace("-", " ").replace("_", " ").title()
            name = f"{clean_title} Architecture & Engineering"
            tags = [slug, project, "autonomous-synthesis"]
            prefs = user_preferences or ["clean_code", "anti_slop", "robust_error_handling", "pragmatic_engineering"]

            fundamentals = custom_fundamentals or (
                f"Autonomous domain engineering profile for '{clean_title}'. Emphasizes verified fundamentals, "
                f"clear architectural separation of concerns, minimal indirection, and strict adherence to anti-slop "
                f"engineering standards. Ensures explicit error paths, deterministic lifecycle management, and high "
                f"cohesion across all implementations."
            )

            takeaways = custom_takeaways or [
                f"Architecture boundary discipline: isolate '{clean_title}' operations behind clean, explicit interfaces.",
                f"Explicit error handling: handle errors at call sites; never swallow exceptions or fail silently.",
                f"Anti-slop simplicity: avoid premature abstractions and speculative generic wrappers; follow the Rule of Three.",
                f"Resource cleanup & lifecycle: ensure all connections, timers, and worker handles are deterministically closed.",
                f"Testing & verification: test critical boundary conditions, invalid payloads, and timeout recovery scenarios."
            ]

            repos = custom_repos or [
                {
                    "name": f"awesome-{slug}",
                    "url": f"https://github.com/search?q={slug}+awesome",
                    "stars": "Curated",
                    "description": f"Curated list of libraries, architectures, and best practices for {clean_title}."
                }
            ]

        return {
            "name": name,
            "slug": slug,
            "project": project,
            "fundamentals": fundamentals,
            "key_takeaways": takeaways,
            "github_repos": repos,
            "user_preferences": prefs,
            "tags": tags,
        }

    @classmethod
    def discover_technologies(cls, text: str) -> List[str]:
        """Extracts technology and methodology candidates from a text block."""
        detected = set()
        clean_text = text.lower()

        # Check all known keys and aliases
        for candidate, slug in SPECIALTY_ALIASES.items():
            pattern = r'\b' + re.escape(candidate) + r'\b'
            if re.search(pattern, clean_text):
                detected.add(slug)

        for key in CURATED_SPECIALTIES:
            pattern = r'\b' + re.escape(key.replace("-", " ")) + r'\b'
            if re.search(pattern, clean_text):
                detected.add(key)
            pattern_dash = r'\b' + re.escape(key) + r'\b'
            if re.search(pattern_dash, clean_text):
                detected.add(key)

        return sorted(list(detected))
