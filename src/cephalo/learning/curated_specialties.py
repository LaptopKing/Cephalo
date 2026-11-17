"""Curated, battle-tested knowledge bank and aliases for core engineering disciplines."""
from typing import Any, Dict
from cephalo.learning.curated_specialties_frontend import FRONTEND_SPECIALTIES
from cephalo.learning.curated_specialties_backend import BACKEND_SPECIALTIES

CURATED_SPECIALTIES: Dict[str, Dict[str, Any]] = {
    **FRONTEND_SPECIALTIES,
    **BACKEND_SPECIALTIES,
}

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


