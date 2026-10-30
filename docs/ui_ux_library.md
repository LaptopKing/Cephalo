# Cephalo Human-Centered Natural UI/UX Design System & Library
> **Cephalo Permanent Standard** | Grounded in: **Readwise Reader, Substack, Linear, Things 3, Bear, Apple News**  
> **Core Law:** *Simplicity is key, ALWAYS. Zero AI-slop, zero cheesy sparkles, zero raw HTML. Natural, calm, modern pastel aesthetics.*

---

## 1. The Anti-AI-Slop Manifesto

Traditional AI-generated web apps fall into identical visual traps that make them look artificial, robotic, and tiring to use:
* ❌ **The "Cyberpunk AI Dashboard" Trap:** Pitch-black (`#000000`) or cold navy (`#0B0F19`) backgrounds, electric cyan buttons, and neon purple gradients.
* ❌ **The Sparkle Trope (`✨` / `<Sparkles />`):** Plastering 4-pointed stars on every button, header, and card to scream "Look, an AI made this!"
* ❌ **Cheesy "AI 3-Bullet Points" Containers:** Cramming articles with noisy, robotic summary boxes that interrupt the natural reading flow.
* ❌ **Raw Unescaped HTML & Entities:** Exposing `&amp;`, `&#39;`, `&#x2F;`, or rogue `<p>` tags because scrapers didn't clean strings before rendering.
* ❌ **Visual Noise Over Content:** Excessive cards, borders, shadows, and marketing fluff obscuring the actual information the user came to read.

### The Human-Centered Replacement
* ✅ **Natural, Tactile Canvas:** Soft, unbleached stone paper (`#FAFAF7`) and warm linen surfaces that treat screens like quality editorial print.
* ✅ **Modern, Calm Pastel Accents:** Subdued, earthy tones (Sage, Terracotta, Dusty Slate, Lavender, Soft Honey) used strictly with high-contrast typography (WCAG 2.1 AA > 4.5:1, typical > 10:1).
* ✅ **Typography as Structure:** Hierarchical contrast, generous line-heights (`1.6` to `1.7`), and restrained measure (`65ch`–`72ch`) eliminate the need for heavy decorative boxes.
* ✅ **Simplicity & Clear Human Communication:** Clear Hungarian or English microcopy, calm toast confirmations, honest system statuses, and zero cognitive overhead.

---

## 2. Design Tokens Matrix (Tailwind CSS Ready)

### Canvas & Surfaces

| Token | Light Mode (Hex / HSL) | Dark Mode (Hex / HSL) | Semantic Purpose |
| :--- | :--- | :--- | :--- |
| `--background` | `#FAFAF7` (`45 20% 97.5%`) | `#161615` (`45 5% 8.5%`) | Primary document canvas (warm paper / charcoal) |
| `--card` | `#FFFFFF` (`0 0% 100%`) | `#1E1E1C` (`45 4% 11.8%`) | Cards, modals, elevated surfaces |
| `--secondary` | `#F4F4F0` (`45 15% 95%`) | `#282724` (`45 5% 15.3%`) | Pill bars, filter containers, subtle sections |
| `--border` | `#E8E7E1` (`45 12% 89%`) | `#2E2D29` (`45 6% 17.5%`) | Tactile, restrained dividers and borders |
| `--foreground` | `#1C1917` (`24 10% 10%`) | `#EDEAE5` (`40 15% 92%`) | Primary text (deep stone-ink / warm cream) |
| `--muted-foreground` | `#78716C` (`24 5% 46%`) | `#9C978F` (`40 5% 58%`) | Secondary labels, dates, reading times |

### Modern Pastel Palette Tokens

| Pastel Accent | Light Mode (Bg / Fg) | Dark Mode (Bg / Fg) | Usage & Association |
| :--- | :--- | :--- | :--- |
| **Sage Green** | `bg-[#EAF1EB]` / `text-[#2D5A37]` | `bg-[#1D2B20]` / `text-[#9CC6A4]` | Science, nature, successful sync, active states |
| **Warm Terracotta** | `bg-[#FAF0EB]` / `text-[#9E452B]` | `bg-[#331D16]` / `text-[#E79780]` | Markets, economy, alerts, breaking news |
| **Dusty Slate / Steel** | `bg-[#EDF1F5]` / `text-[#324B64]` | `bg-[#1B242E]` / `text-[#93A9C1]` | Tech, engineering, infrastructure, tools |
| **Soft Lavender** | `bg-[#F2EFF7]` / `text-[#554175]` | `bg-[#251E30]` / `text-[#B7A4D4]` | Culture, essays, community, long reads |
| **Soft Honey / Amber** | `bg-[#FAF4E6]` / `text-[#825C18]` | `bg-[#2E2413]` / `text-[#E0BC6D]` | Domestic press, curated collections, bookmarks |

---

## 3. Mandatory Component & Content Engineering Rules

### Rule 1: Clean Text Invariant (Zero Raw HTML & Entities)
Every user-facing string (title, subtitle, author, snippet) MUST be sanitized through a dedicated HTML entity decoder before rendering:
* Decode `&#x2F;` $\to$ `/`, `&amp;` $\to$ `&`, `&#39;` $\to$ `'`, `&quot;` $\to$ `"`, `&ndash;` $\to$ `–`, `&mdash;` $\to$ `—`.
* Strip any leftover `<p>`, `<a>`, `<span>`, `<div>` tags from summaries.
* Trim extraneous whitespace.

### Rule 2: Remove Tacky AI Gimmicks
* Never display AI 3-bullet points inside content cards unless explicitly requested in a dedicated deep-dive view.
* Remove `✨` sparkles icons from standard operational views. Use functional icons (`Newspaper`, `Rss`, `Send`, `Bell`, `Clock`, `ArrowUpRight`, `Sliders`).

### Rule 3: Editorial Card Hierarchy
1. **Source & Time Header:** Publication name in subtle medium weight + dot divider (`•`) + relative timestamp (e.g. `15m` / `15 perc`) + category pastel tag.
2. **Headline:** Prominent, high-contrast, uncluttered typography (`font-serif` or clean `font-semibold` sans).
3. **Excerpt:** Clean 2–3 line natural text snippet (no bullet points, no HTML).
4. **Footer:** Reading time (`3 min read` / `3 perc`) + minimal "Read original" / "Eredeti cikk" link with `ArrowUpRight`.

### Rule 4: Human User Communication
* **Clarity:** Notifications should state what happened simply without technical jargon.
* **Toasts:** Use unobtrusive, warm toasts (neutral stone background, gentle entrance/exit) rather than intrusive modal dialogs.
* **Filters:** Segmented controls with tactile pills rather than sprawling accordion menus.


---

## 4. Mobile-First Layout & Touch Ergonomics

> **Benchmarked against:** Apple News, Readwise Reader, Substack iOS/Mobile Web, Linear Mobile, Things 3

### Rule 5: Bottom-Zone Thumb Anchoring
* **Fixed Bottom Navigation Bar:** On mobile viewports (`< 768px`), all primary navigation (Home, Search, Sources, Alerts) MUST be fixed in the bottom thumb zone (`fixed bottom-0 left-0 right-0 z-50`).
* **Safe Area Inset Handling:** Always apply `pb-[max(0.5rem,env(safe-area-inset-bottom,0px))]` to prevent collisions with iOS home indicators.
* **Scroll Compensation:** The main page scroll view must include bottom padding (`pb-24 md:pb-10`) so no content or buttons are occluded by the navigation bar.

### Rule 6: Single-Row Horizontal Category Swipe
* **Zero CLS (No Multi-line Stacking):** Never allow filter buttons or topic tags to wrap into awkward multi-line clouds on mobile.
* **Fluid Momentum Carousel:** Use single-row horizontal scrolling (`flex overflow-x-auto no-scrollbar scroll-smooth flex-nowrap`) with snap alignment (`snap-x snap-mandatory`) and touch momentum (`-webkit-overflow-scrolling: touch`).
* **Edge Affordance:** Utilize subtle edge masks (`mask-edge-fade`) to signal that more categories exist off-screen.

### Rule 7: 44px Minimum Touch Targets & Stretched Links
* **Ergonomic Touch Targets:** Every interactive icon, pill, toggle, or link must have a minimum tap area of 44×44px (NN/g and Apple HIG guideline).
* **Pseudo-Element Card Tapability:** Use Heydon Pickering's stretched link pattern (`after:absolute after:inset-0 after:z-10` on the headline link) to make 100% of the card touch-activatable, while elevating secondary actions (source link, share, bookmark) with `relative z-20` for independent clicks without DOM nesting errors.

---

## 5. Zero-Feed Cold-Start & Natural Language Topic Research

### The "No-RSS" User Invariant
95% of users do not possess RSS/XML URLs. A modern news platform must never fail or block when a user has no feeds:
1. **Natural Language Query Resolution:** Allow users to type plain text topics (e.g. *"Quantum Computing"*, *"Hungarian Real Estate"*, *"Formula 1 Engine Upgrades"*).
2. **Autonomous Multi-Bridge Discovery:**
   - **Google News RSS Bridge:** Localized queries (`https://news.google.com/rss/search?q={query}&hl={lang}`) provide instant, real-time structured XML articles.
   - **Web Crawler & DOM Extraction:** Given any website URL, automatically inspect for `<link rel="alternate" type="application/rss+xml">`. If missing, scrape article headlines, dates, and images directly from the DOM using Cheerio.
   - **1-Click Subscription:** Present a 3-article live preview and provide an instant 1-click *"Követés saját csatornaként"* button that saves the dynamic stream into persistent storage (`localStorage` / DB).
