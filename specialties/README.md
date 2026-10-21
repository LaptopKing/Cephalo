# Cephalo — Specialties Architecture

The **Specialties Layer** is Cephalo's modular domain expertise system. It structures long-term memory into a clean, 3-tier hierarchy:

$$\text{Project} \longrightarrow \text{Specialties (1-to-Many)} \longrightarrow \text{User Preferences (Inherited Constraints)}$$

---

## 1. How It Works

When an AI agent or developer tackles a new domain (e.g., ecommerce, car maintenance, Rust systems programming, legal contract review), Cephalo creates a dedicated **Specialty Module**:

1. **Conducts a Deep Dive:** Extracts core fundamentals, verified technical blueprints, and curated benchmarks.
2. **Binds User Constraints:** Automatically links foundational personal preferences (e.g., `extreme_minimalism`, `oem_preferred`, `naturally_aspirated`, `monochrome_viability`) so all future agent actions inherit these rules.
3. **Indexes into LanceDB:** Embeds verified knowledge into local columnar vector tables for instant hybrid recall.

---

## 2. Directory Structure of a Specialty

Every specialty created inside this folder follows a strict schema:

```
specialties/
└── <project-slug>/
    └── <specialty-slug>/
        ├── manifest.json   # Machine-readable metadata, tags, repos, bound preferences
        └── KNOWLEDGE.md    # Human-readable verified blueprints, fundamentals & notes
```

### `manifest.json` Schema
```json
{
  "id": "specialty-<project>-<name>",
  "name": "Human-Readable Name",
  "slug": "url-safe-slug",
  "project": "parent-project-slug",
  "project_slug": "parent-project-slug",
  "created_at": "ISO-8601 Timestamp",
  "updated_at": "ISO-8601 Timestamp",
  "tags": ["tag1", "tag2"],
  "github_repos": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "stars": "15k+",
      "description": "Benchmark reference"
    }
  ],
  "key_takeaways": [
    "Core verified rule 1",
    "Core verified rule 2"
  ],
  "user_preferences_binding": [
    "preference_key_1",
    "preference_key_2"
  ]
}
```

---

## 3. CLI Management

Specialties are managed deterministically via `brain.py`:

```bash
# List all active specialties
python brain.py specialty list

# Filter specialties by project
python brain.py specialty list --project "ecommerce"

# Read a specialty's verified knowledge and manifest
python brain.py specialty read "microservices" --project "backend"

# Create a new specialty
python brain.py specialty create "redis-caching" \
  --project "backend" \
  --fundamentals "Redis 7 cache-aside pattern with TTL jitter." \
  --takeaways "Always set TTL; Use connection pooling" \
  --preferences "low_latency, strict_timeouts"

# Edit an existing specialty
python brain.py specialty edit "redis-caching" --notes "Updated pool size to 50"

# Delete a specialty (requires explicit confirmation flag)
python brain.py specialty delete "redis-caching" --confirm
```

---

## 4. Privacy Guarantee

> [!NOTE]
> All user-created specialties created inside `specialties/` are stored strictly on your local machine and are **ignored by `.gitignore`**. Your private business logic, vehicle configurations, proprietary code blueprints, and research notes are never pushed to public repositories.
