"""Curated specialties: Frontend, UI/UX, and Engineering craftsmanship."""
from typing import Any, Dict

FRONTEND_SPECIALTIES: Dict[str, Dict[str, Any]] = {
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

}
