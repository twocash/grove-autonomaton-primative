"""
content_engine.py - The LLM-Powered Content Compilation Engine

Compiles content seeds into platform-ready drafts using Tier 2 LLM,
strictly governed by Voice and Pillar configurations.

The engine injects voice.yaml, pillars.yaml, the content seed, and
dock context into the LLM prompt for brand-consistent generation.
"""

import yaml
import random
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from engine.profile import get_config_dir, get_entities_dir, get_output_dir


@dataclass
class ContentSeed:
    """A raw content seed to be compiled."""
    name: str
    filepath: Path
    pillar: Optional[str] = None
    theme: Optional[str] = None
    raw_content: str = ""


@dataclass
class CompiledDraft:
    """A platform-ready content draft."""
    seed_name: str
    platform: str
    pillar: str
    content: str
    hashtags: list[str] = field(default_factory=list)
    voice_rules_applied: list[str] = field(default_factory=list)
    compiled_at: str = ""


class ContentEngine:
    """
    Compiles content seeds into platform-ready drafts.

    The engine applies voice rules from voice.yaml and pillar
    themes from pillars.yaml to ensure brand consistency.
    """

    def __init__(self):
        self.config_dir = get_config_dir()
        self.pillars_path = self.config_dir / "pillars.yaml"
        self.voice_path = self.config_dir / "voice.yaml"
        self.seeds_dir = get_entities_dir() / "content-seeds"
        self.output_dir = get_output_dir() / "content"
        self.pillars = self._load_pillars()
        self.voice = self._load_voice()

    def _load_pillars(self) -> dict:
        """Load pillar configuration."""
        if not self.pillars_path.exists():
            return {}
        with open(self.pillars_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_voice(self) -> dict:
        """Load voice configuration."""
        if not self.voice_path.exists():
            return {}
        with open(self.voice_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _compile_with_llm(
        self,
        seed_content: str,
        pillar: str,
        platform: str
    ) -> str:
        """
        Compile content using Tier 2 LLM (Sonnet).

        Injects voice config, pillar context, and platform requirements
        into the prompt for brand-consistent content generation.

        Args:
            seed_content: Raw content seed text
            pillar: Content pillar (from profile pillars.yaml)
            platform: Target platform (e.g., 'tiktok', 'instagram', 'x')

        Returns:
            LLM-generated content draft
        """
        from engine.llm_client import call_llm

        # Get voice configuration
        voice_config = self.voice or {}
        tone = voice_config.get("tone", {})
        signature_phrases = tone.get("signature_phrases", [])
        personality = tone.get("personality", [])

        # Get platform-specific voice
        platform_voice = voice_config.get("platform_voice", {}).get(platform, {})
        format_prefs = platform_voice.get("format_preferences", [])
        emoji_use = platform_voice.get("emoji_use", "minimal")
        hashtag_limit = platform_voice.get("hashtag_limit", 3)

        # Get pillar context
        pillar_config = self.pillars.get("pillars", {}).get(pillar, {})
        pillar_desc = pillar_config.get("description", pillar)
        pillar_hashtags = pillar_config.get("hashtags", [])[:hashtag_limit]

        # Load content config for tone
        from engine.config_loader import load_content_config
        content_config = load_content_config()
        default_tone = content_config.get("default_tone", "Professional")

        # Build the prompt
        prompt = f"""You are a content creator applying specific voice and brand guidelines.

## Voice Configuration
- Personality: {', '.join(personality) if personality else 'professional, authentic'}
- Signature phrases to use: {', '.join(signature_phrases[:3]) if signature_phrases else 'none specified'}
- Tone: {default_tone}

## Pillar Context
- Content pillar: {pillar}
- Pillar description: {pillar_desc}
- Suggested hashtags: {' '.join(pillar_hashtags) if pillar_hashtags else 'none'}

## Platform Requirements ({platform})
- Format preferences: {', '.join(format_prefs) if format_prefs else 'standard post'}
- Emoji usage: {emoji_use}
- Character/length constraints: {'280 chars for X, longer form for others' if platform == 'x' else 'platform appropriate'}

## Content Seed
{seed_content}

---

Generate a ready-to-post {platform} content draft based on the seed above.
Apply the voice configuration and stay true to the pillar theme.
Include relevant hashtags at the end if appropriate for the platform.

Your response should be the final draft text only, no explanations or metadata."""

        # Apply Privacy Mask before sending to external LLM
        # This ensures no student names are ever sent externally
        from engine.compiler import apply_privacy_mask
        masked_prompt = apply_privacy_mask(prompt)

        # Call Tier 2 (Sonnet) for quality content generation
        return call_llm(
            prompt=masked_prompt,
            tier=2,  # Sonnet for quality
            intent="content_compilation"
        )

    def compile_weekly_content(self, seeds_directory: Optional[str] = None) -> list[CompiledDraft]:
        """
        Compile all content seeds into platform-ready drafts using LLM.

        Args:
            seeds_directory: Path to seeds (default: entities/content-seeds/)

        Returns:
            List of compiled drafts ready for approval
        """
        seeds_path = Path(seeds_directory) if seeds_directory else self.seeds_dir

        # Ensure seeds directory exists
        if not seeds_path.exists():
            seeds_path.mkdir(parents=True, exist_ok=True)
            return []

        # Load all seed files
        seeds = self._load_seeds(seeds_path)

        if not seeds:
            return []

        # Compile each seed for each platform using LLM
        drafts = []
        platforms = self.voice.get("platform_voice", {}).keys()

        for seed in seeds:
            for platform in platforms:
                try:
                    # Use LLM for compilation
                    content = self._compile_with_llm(
                        seed_content=seed.raw_content,
                        pillar=seed.pillar or "general",
                        platform=platform
                    )

                    # Get pillar hashtags
                    pillar_config = self.pillars.get("pillars", {}).get(seed.pillar, {})
                    hashtag_limit = self.voice.get("platform_voice", {}).get(platform, {}).get("hashtag_limit", 3)
                    pillar_hashtags = pillar_config.get("hashtags", [])[:hashtag_limit]

                    draft = CompiledDraft(
                        seed_name=seed.name,
                        platform=platform,
                        pillar=seed.pillar or "general",
                        content=content,
                        hashtags=pillar_hashtags,
                        voice_rules_applied=["llm_compiled"],
                        compiled_at=datetime.now(timezone.utc).isoformat()
                    )
                    drafts.append(draft)

                except Exception as e:
                    from engine.telemetry import log_event
                    log_event(
                        source="content_engine",
                        raw_transcript=f"seed:{seed.name} platform:{platform}",
                        zone_context="yellow",
                        inferred={"error": str(e), "error_type": type(e).__name__,
                                  "seed": seed.name, "platform": platform, "stage": "compilation_error"}
                    )
                    continue  # Skip this draft but continue batch

        return drafts

    def _load_seeds(self, seeds_path: Path) -> list[ContentSeed]:
        """Load content seeds from markdown files."""
        seeds = []

        for filepath in seeds_path.glob("*.md"):
            content = filepath.read_text(encoding="utf-8")

            # Parse seed metadata from content
            pillar = self._extract_pillar(content)
            theme = self._extract_theme(content)

            seeds.append(ContentSeed(
                name=filepath.stem,
                filepath=filepath,
                pillar=pillar,
                theme=theme,
                raw_content=content
            ))

        return seeds

    def _extract_pillar(self, content: str) -> Optional[str]:
        """Extract pillar from seed content (looks for pillar: tag)."""
        for line in content.split("\n"):
            if line.lower().startswith("pillar:"):
                return line.split(":", 1)[1].strip().lower()
        # Default to first pillar from config
        pillars = self.pillars.get("pillars", {})
        if pillars:
            return list(pillars.keys())[0]
        # Ultimate fallback from content config
        from engine.config_loader import load_content_config
        content_config = load_content_config()
        return content_config.get("default_pillar", "general")

    def _extract_theme(self, content: str) -> Optional[str]:
        """Extract theme from seed content."""
        for line in content.split("\n"):
            if line.lower().startswith("theme:"):
                return line.split(":", 1)[1].strip().lower()
        return None

    def _compile_for_platform(self, seed: ContentSeed, platform: str) -> Optional[CompiledDraft]:
        """
        Compile a seed for a specific platform applying voice rules.
        """
        platform_config = self.voice.get("platform_voice", {}).get(platform, {})
        pillar_config = self.pillars.get("pillars", {}).get(seed.pillar, {})

        if not platform_config:
            return None

        # Get voice rules
        format_prefs = platform_config.get("format_preferences", [])
        hashtag_limit = platform_config.get("hashtag_limit", 3)
        emoji_use = platform_config.get("emoji_use", "minimal")
        tone_modifier = platform_config.get("tone_modifier", "")

        # Get pillar hashtags
        pillar_hashtags = pillar_config.get("hashtags", [])[:hashtag_limit]

        # Get signature phrases for variety
        signature_phrases = self.voice.get("tone", {}).get("signature_phrases", [])

        # Apply platform-specific compilation
        rules_applied = []
        content = ""

        if platform == "tiktok":
            content = self._compile_tiktok(seed, format_prefs, signature_phrases, emoji_use)
            rules_applied = ["hook_first", "under_60_seconds", f"emoji:{emoji_use}"]

        elif platform == "x":
            content = self._compile_x(seed, format_prefs, signature_phrases)
            rules_applied = ["single_insight", "concise", f"emoji:{emoji_use}"]

        elif platform == "instagram":
            content = self._compile_instagram(seed, format_prefs, signature_phrases, emoji_use)
            rules_applied = ["visual_storytelling", f"emoji:{emoji_use}"]

        return CompiledDraft(
            seed_name=seed.name,
            platform=platform,
            pillar=seed.pillar or "general",
            content=content,
            hashtags=pillar_hashtags,
            voice_rules_applied=rules_applied,
            compiled_at=datetime.now(timezone.utc).isoformat()
        )

    def _compile_tiktok(
        self,
        seed: ContentSeed,
        format_prefs: list,
        signature_phrases: list,
        emoji_use: str
    ) -> str:
        """
        Compile TikTok content with hook-first structure.

        Voice rules:
        - Hook first (attention-grabbing opener)
        - Under 60 seconds (concise)
        - Moderate emoji use
        - Soft CTA
        """
        # Extract the core message from seed
        core_message = self._get_core_message(seed)

        # Load platform templates from config
        from engine.config_loader import load_content_config
        content_config = load_content_config()
        tiktok_templates = content_config.get("platform_templates", {}).get("tiktok", {})

        # Build hook-first structure from config
        hooks = tiktok_templates.get("hooks", ["Here's what you need to know..."])
        ctas = tiktok_templates.get("ctas", ["Follow for more."])
        config_emoji = tiktok_templates.get("emoji", "")

        hook = random.choice(hooks) if hooks else "Here's what you need to know..."
        phrase = random.choice(signature_phrases) if signature_phrases else "Trust your practice."
        cta = random.choice(ctas) if ctas else "Follow for more."

        # Add emoji based on config
        emoji = ""
        if emoji_use == "moderate" and config_emoji:
            emoji = config_emoji

        content = f"""[HOOK]{emoji}
{hook}

[CONTENT]
{core_message}

[CLOSE]
{phrase}

[CTA]
{cta}
"""
        return content.strip()

    def _compile_x(
        self,
        seed: ContentSeed,
        format_prefs: list,
        signature_phrases: list
    ) -> str:
        """
        Compile X (Twitter) content as single insight.

        Voice rules:
        - Single insight (one sentence focus)
        - Concise and thoughtful
        - Minimal emoji
        - 2 hashtags max
        """
        core_message = self._get_core_message(seed)

        # Condense to single insight
        # Take first sentence or create one
        sentences = core_message.split(".")
        insight = sentences[0].strip() if sentences else core_message[:200]

        # Keep it tweet-length
        if len(insight) > 240:
            insight = insight[:237] + "..."

        return insight

    def _compile_instagram(
        self,
        seed: ContentSeed,
        format_prefs: list,
        signature_phrases: list,
        emoji_use: str
    ) -> str:
        """
        Compile Instagram content with visual storytelling focus.

        Voice rules:
        - Visual storytelling
        - Carousel or reel format suggestion
        - Community invite CTA
        - Moderate emoji
        """
        core_message = self._get_core_message(seed)
        phrase = random.choice(signature_phrases) if signature_phrases else "Excellence is a habit."

        # Load platform templates from config
        from engine.config_loader import load_content_config
        content_config = load_content_config()
        ig_templates = content_config.get("platform_templates", {}).get("instagram", {})

        config_emoji = ig_templates.get("emoji", "")
        ctas = ig_templates.get("ctas", ["Link in bio for more."])
        visual_prompt = ig_templates.get("visual_prompt", "[Suggest: relevant visual]")

        emoji = ""
        if emoji_use == "moderate" and config_emoji:
            emoji = config_emoji

        cta = random.choice(ctas) if ctas else "Link in bio for more."

        content = f"""[VISUAL]{emoji}
{visual_prompt}

[CAPTION]
{core_message}

{phrase}

[CTA]
{cta}
"""
        return content.strip()

    def _get_core_message(self, seed: ContentSeed) -> str:
        """Extract the core message from a seed, removing metadata."""
        lines = seed.raw_content.split("\n")
        content_lines = []

        for line in lines:
            # Skip metadata lines
            if line.lower().startswith(("pillar:", "theme:", "#")):
                continue
            if line.strip():
                content_lines.append(line.strip())

        return " ".join(content_lines) if content_lines else seed.raw_content[:200]

    def save_drafts(self, drafts: list[CompiledDraft]) -> list[Path]:
        """
        Save compiled drafts to the output directory.

        Returns list of created file paths.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = []

        for draft in drafts:
            filename = f"{draft.platform}-{draft.seed_name}.md"
            filepath = self.output_dir / filename

            content = f"""# {draft.platform.upper()} Draft: {draft.seed_name}

**Pillar:** {draft.pillar}
**Platform:** {draft.platform}
**Compiled:** {draft.compiled_at}
**Voice Rules:** {', '.join(draft.voice_rules_applied)}

---

{draft.content}

---

**Hashtags:** {' '.join(draft.hashtags)}
"""

            filepath.write_text(content, encoding="utf-8")
            saved_files.append(filepath)

        return saved_files

    def format_drafts_for_approval(self, drafts: list[CompiledDraft]) -> str:
        """Format drafts for display in approval prompt."""
        output = f"Compiled {len(drafts)} draft(s):\n\n"

        for i, draft in enumerate(drafts, 1):
            output += f"--- [{i}] {draft.platform.upper()}: {draft.seed_name} ---\n"
            output += f"Pillar: {draft.pillar}\n"
            output += f"Rules: {', '.join(draft.voice_rules_applied)}\n"
            # Show preview
            preview = draft.content[:200].replace('\n', ' ')
            output += f"Preview: {preview}...\n"
            output += f"Hashtags: {' '.join(draft.hashtags)}\n\n"

        return output


# Module-level convenience functions
_engine_instance: Optional[ContentEngine] = None


def get_content_engine() -> ContentEngine:
    """Get the shared ContentEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ContentEngine()
    return _engine_instance


def compile_content(seeds_directory: Optional[str] = None) -> list[CompiledDraft]:
    """
    Compile content seeds into platform-ready drafts.

    This is the primary interface for the pipeline integration.
    """
    engine = get_content_engine()
    return engine.compile_weekly_content(seeds_directory)


def save_content_drafts(drafts: list[CompiledDraft]) -> list[Path]:
    """Save approved drafts to output directory."""
    engine = get_content_engine()
    return engine.save_drafts(drafts)


def format_for_approval(drafts: list[CompiledDraft]) -> str:
    """Format drafts for approval display."""
    engine = get_content_engine()
    return engine.format_drafts_for_approval(drafts)
