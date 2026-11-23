from __future__ import annotations

import io
import json
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands


# By zen (@wooher on dc), discord.gg/ail


Style = Literal["classic", "neko", "cozy", "gremlin"]
STYLES: tuple[Style, ...] = ("classic", "neko", "cozy", "gremlin")
DEFAULT_STYLE: Style = "classic"
DEFAULT_INTENSITY = 75

SLASH_COOLDOWN_USES = 3
SLASH_COOLDOWN_SECONDS = 10.0
PREFIX_COOLDOWN_USES = 3
PREFIX_COOLDOWN_SECONDS = 10.0
AUTO_COOLDOWN_SECONDS = 8.0
AUTO_MAX_INPUT_LENGTH = 1600
DISCORD_MESSAGE_LIMIT = 2000

CUSTOM_SWAPS: dict[str, str] = {}  # Example: {"computer": "computew"}
PROTECTED_TERMS: tuple[str, ...] = ()  # Example: ("MyServer", "Python")
SETTINGS_FILE = Path(__file__).with_name("uwu_settings.json")

# Transformation probabilities (each is multiplied by intensity)
SWAP_CHANCE = 0.90
PHONETIC_CHANCE = 0.95
NY_CHANCE = 0.27
TH_CHANCE = 0.13
STUTTER_CHANCE = 0.10
TILDE_CHANCE = 0.34
PARTICLE_CHANCE = 0.14
FACE_CHANCE = 0.24
EMOJI_CHANCE = 0.20


@dataclass(slots=True)
class UwuConfig:
    intensity: float = 0.75
    style: Style = DEFAULT_STYLE
    faces: bool = True
    stutters: bool = True
    phonetics: bool = True
    word_swaps: bool = True
    tildes: bool = True
    particles: bool = True
    emojis: bool = False
    seed: int | None = None
    custom_swaps: dict[str, str] = field(default_factory=dict)
    protected_terms: tuple[str, ...] = ()

    def __post_init__(self):
        if not 0 <= self.intensity <= 1:
            raise ValueError("intensity must be between 0 and 1")
        if self.style not in STYLES:
            raise ValueError(f"style must be one of {STYLES}")


@dataclass(slots=True)
class DecorationBudget:
    faces: int = 0
    emojis: int = 0


class Uwuifier:
    SWAPS = {
        "hello": "hewwo", "hey": "hewwo", "hi": "hai",
        "friend": "fwiend", "friends": "fwiends",
        "small": "smol", "little": "wittle", "cute": "kawaii",
        "love": "wuv", "loves": "wuvs", "please": "pwease",
        "really": "weawwy", "very": "vewy", "sorry": "sowwy",
        "thanks": "fanks", "thank": "fank", "what": "wat", "why": "wai",
        "this": "dis", "that": "dat", "there": "dewe",
        "they": "dey", "them": "dem", "the": "da",
        "because": "becuz", "okay": "oki", "ok": "oki",
        "no": "nu", "yes": "yus", "you": "chu", "your": "ur",
        "you're": "ur", "good": "gud", "great": "gweat",
        "right": "wight", "pretty": "pwetty", "happy": "happi",
        "amazing": "amazwing", "beautiful": "bootiful",
        "hug": "huggie", "sweet": "sweetie", "everyone": "evewyone",
    }

    STYLE_SWAPS = {
        "classic": {},
        "neko": {"hello": "nyello", "cat": "kitty", "cats": "kitties"},
        "cozy": {"friend": "bestie", "friends": "besties"},
        "gremlin": {"hello": "HEWWO", "no": "NUUU", "yes": "YUSSS"},
    }

    FACES = {
        "neutral": ("uwu", "owo", ":3", "^w^"),
        "question": ("owo?", "uwu?", "(・`ω´・)?"),
        "excited": ("OwO!", "(≧▽≦)", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧"),
        "sad": ("QwQ", "T_T", "unu"),
        "love": ("uwu", "♡", "(づ｡◕‿‿◕｡)づ"),
        "laugh": ("x3", "hehe~", ">:3"),
        "greeting": ("uwu", "(＾▽＾)", "^w^"),
        "thanks": ("uwu", "(｡♥‿♥｡)"),
        "apology": ("unu", "(｡•́︿•̀｡)"),
        "command": ("uwu", ":3"),
    }

    EXTRA_FACES = {
        "classic": (),
        "neko": ("ฅ^•ﻌ•^ฅ", "(=^･ω･^=)"),
        "cozy": ("(づ◡﹏◡)づ", "(*´꒳`*)"),
        "gremlin": (">:3", "(¬‿¬)"),
    }

    EMOJIS = {
        "neutral": ("🌸", "✨"), "question": ("🤔", "🐾"),
        "excited": ("🎉", "✨"), "sad": ("🥺", "💧"),
        "love": ("💖", "💕"), "laugh": ("😂", "✨"),
        "greeting": ("👋", "🌸"), "thanks": ("🙏", "💖"),
        "apology": ("🥺",), "command": ("✨",),
    }

    PARTICLES = {
        "classic": (), "neko": ("nya", "nyan", "meow"),
        "cozy": ("hehe", "eep"), "gremlin": ("rawr", ">:3"),
    }

    PROTECTED = re.compile(
        r"(?P<ticks>`+)(?!`)[^\n]*?(?P=ticks)(?!`)"
        r"|\[[^\]\n]+\]\((?:\\.|[^)\n])+\)"
        r"|\|\|[^\n]*?\|\|"
        r"|<@!?\d+>|<@&\d+>|<\#\d+>"
        r"|<a?:[\w]+:\d+>"
        r"|<t:\d+(?::[tTdDfFR])?>"
        r"|<https?://[^>\s]+>"
        r"|https?://[^\s<>]+"
        r"|www\.[^\s<>]+"
        r"|[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}"
        r"|(?<!\w)@(?:everyone|here|[\w.\-]+)"
        r"|(?<!\w)\{\{[\w.]+\}\}"
        r"|&(?:\#\d+|[a-zA-Z]+);",
        re.IGNORECASE,
    )
    WORD = re.compile(r"(?<!\w)[A-Za-z]+(?:['’][A-Za-z]+)?(?!\w)")
    SENTENCES = re.compile(r"(?<=[.!?])(?=[ \t]+)")
    FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")

    def __init__(self, config: UwuConfig | None = None):
        self.config = config or UwuConfig()
        self.rng = random.Random(self.config.seed)
        self.swaps = {
            **self.SWAPS,
            **self.STYLE_SWAPS[self.config.style],
            **{k.casefold(): v for k, v in self.config.custom_swaps.items()},
        }
        terms = [re.escape(t) for t in self.config.protected_terms if t]
        pattern = "|".join(sorted(terms, key=len, reverse=True))
        self.protect_terms = (
            re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE)
            if terms else None
        )

    def chance(self, probability: float) -> bool:
        return self.rng.random() < min(1.0, max(0.0, probability * self.config.intensity))

    @staticmethod
    def keep_case(old: str, new: str) -> str:
        if old.isupper():
            return new.upper()
        if old.istitle():
            return new[:1].upper() + new[1:]
        return new

    def mood(self, text: str) -> str:
        clean = self.PROTECTED.sub("", text).strip()
        words = re.findall(r"[a-z]+", clean.lower())
        if not words:
            return "neutral"
        tokens, first = set(words), words[0]
        if clean.rstrip(' \t"\'”)]}').endswith("?"):
            return "question"
        if clean.count("!") >= 2 or first in {"wow", "omg", "yay", "awesome"}:
            return "excited"
        for mood, vocab in (
            ("laugh", {"lol", "lmao", "haha", "hehe", "rofl"}),
            ("apology", {"sorry", "apologize", "apologies"}),
            ("sad", {"sad", "cry", "crying", "lonely", "upset", "hurt"}),
            ("thanks", {"thank", "thanks", "grateful", "appreciate"}),
            ("love", {"love", "adorable", "cute", "kiss", "hug", "sweet"}),
        ):
            if tokens & vocab:
                return mood
        if first in {"hi", "hello", "hey", "hiya", "morning", "evening"}:
            return "greeting"
        if first in {"please", "stop", "go", "tell", "send", "make"}:
            return "command"
        return "neutral"

    def transform_word(self, word: str, mood: str) -> str:
        if len(word) > 1 and word.isupper():
            return word
        new = word
        multiplier = 0.7 if mood in {"sad", "apology", "command"} else 1.0
        if (self.config.word_swaps and word.casefold() in self.swaps
                and self.chance(SWAP_CHANCE * multiplier)):
            new = self.keep_case(new, self.swaps[word.casefold()])
        if (self.config.phonetics and len(new) > 1
                and self.chance(PHONETIC_CHANCE * multiplier)):
            base, lower = new, new.lower()
            lower = re.sub(r"[rl]", "w", lower)
            if self.chance(NY_CHANCE * multiplier):
                lower = re.sub(r"n(?=[aeiou])", "ny", lower)
            if self.chance(TH_CHANCE * multiplier):
                lower = re.sub(r"^th(?=[aeiou])", "d", lower)
            new = self.keep_case(base, lower)
        if (self.config.stutters and len(new) >= 3
                and self.chance(STUTTER_CHANCE * multiplier)):
            new = f"{new[0]}-{new}"
        return new

    def transform_safe(self, text: str, mood: str) -> tuple[str, bool]:
        spans = [(m.start(), m.end()) for m in self.PROTECTED.finditer(text)]
        if self.protect_terms:
            spans.extend((m.start(), m.end()) for m in self.protect_terms.finditer(text))
        spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
        output, position, had_words = [], 0, False
        for start, end in spans:
            if start < position:
                continue
            plain = text[position:start]
            had_words |= bool(self.WORD.search(plain))
            output.append(self.WORD.sub(lambda m: self.transform_word(m.group(), mood), plain))
            output.append(text[start:end])
            position = end
        plain = text[position:]
        had_words |= bool(self.WORD.search(plain))
        output.append(self.WORD.sub(lambda m: self.transform_word(m.group(), mood), plain))
        return "".join(output), had_words

    def transform_sentence(self, text: str, budget: DecorationBudget) -> str:
        front = len(text) - len(text.lstrip(" \t"))
        back = len(text.rstrip(" \t"))
        before, body, after = text[:front], text[front:back], text[back:]
        if not body:
            return text
        mood = self.mood(body)
        result, had_words = self.transform_safe(body, mood)
        if not had_words:
            return text
        if self.config.tildes and self.chance(TILDE_CHANCE) and not result.endswith(("~", "?")):
            result += "~"
        particles = self.PARTICLES[self.config.style]
        if self.config.particles and particles and self.chance(PARTICLE_CHANCE):
            result += " " + self.rng.choice(particles)
        if self.config.faces and budget.faces < 1 and self.chance(FACE_CHANCE):
            choices = self.FACES[mood] + self.EXTRA_FACES[self.config.style]
            result += " " + self.rng.choice(choices)
            budget.faces += 1
        if self.config.emojis and budget.emojis < 1 and self.chance(EMOJI_CHANCE):
            result += " " + self.rng.choice(self.EMOJIS[mood])
            budget.emojis += 1
        return before + result + after

    def transform_line(self, line: str) -> str:
        if not line.strip():
            return line

        if line.lstrip().startswith(("!", "/", "$", ".", "?")):
            return line
        if line.startswith(("    ", "\t")):
            return line
        budget = DecorationBudget()
        return "".join(
            self.transform_sentence(sentence, budget)
            for sentence in self.SENTENCES.split(line)
        )

    def uwuify(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if not text or self.config.intensity == 0:
            return text
        output, fence = [], None
        for line in text.splitlines(keepends=True):
            if line.endswith("\r\n"):
                body, newline = line[:-2], "\r\n"
            elif line.endswith(("\r", "\n")):
                body, newline = line[:-1], line[-1]
            else:
                body, newline = line, ""
            match = self.FENCE.match(body)
            if fence:
                output.append(line)
                if (match and match.group(1)[0] == fence[0]
                        and len(match.group(1)) >= fence[1]
                        and not match.group(2).strip()):
                    fence = None
                continue
            if match:
                fence = (match.group(1)[0], len(match.group(1)))
                output.append(line)
                continue
            output.append(self.transform_line(body) + newline)
        return "".join(output)


def make_uwu(
    text: str, *, style: Style = DEFAULT_STYLE,
    intensity: int = DEFAULT_INTENSITY, emojis: bool = False,
    seed: int | None = None,
) -> str:
    return Uwuifier(UwuConfig(
        intensity=intensity / 100,
        style=style,
        emojis=emojis,
        seed=seed,
        custom_swaps=CUSTOM_SWAPS,
        protected_terms=PROTECTED_TERMS,
    )).uwuify(text)


class UwuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_settings: dict[str, dict] = {}
        self.last_auto: dict[int, float] = {}
        self.message_menu = app_commands.ContextMenu(
            name="UwUify Message", callback=self.menu_uwu
        )
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.guild_settings = data
        except (OSError, ValueError):
            self.guild_settings = {}

    async def cog_load(self):
        self.bot.tree.add_command(self.message_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(
            self.message_menu.name, type=discord.AppCommandType.message
        )

    def settings(self, guild_id: int | None) -> dict:
        item = self.guild_settings.get(str(guild_id) if guild_id else "DM", {})
        return item if isinstance(item, dict) else {}

    def save(self):
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = SETTINGS_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(self.guild_settings, indent=2), encoding="utf-8")
        temp.replace(SETTINGS_FILE)

    def _uwuify(
        self, text: str, guild_id: int | None, *,
        style: Style | None = None, intensity: int | None = None,
        emojis: bool = True,
    ) -> str:
        """One path for server defaults and per-command overrides."""
        cfg = self.settings(guild_id)
        return make_uwu(
            text,
            style=style if style is not None else cfg.get("style", DEFAULT_STYLE),
            intensity=(intensity if intensity is not None
                       else cfg.get("intensity", DEFAULT_INTENSITY)),
            emojis=emojis,
        )

    @staticmethod
    def _as_file(text: str) -> discord.File:
        return discord.File(io.BytesIO(text.encode("utf-8")), filename="uwu.txt")

    @staticmethod
    async def send_result(
        interaction: discord.Interaction, result: str, *, private: bool = False
    ):
        safe = discord.AllowedMentions.none()
        if len(result) <= DISCORD_MESSAGE_LIMIT:
            await interaction.response.send_message(
                result or "(empty)", ephemeral=private,
                allowed_mentions=safe, suppress_embeds=True,
            )
        else:
            await interaction.response.send_message(
                "The UwU text is attached because it exceeds Discord's message limit.",
                file=UwuCog._as_file(result), ephemeral=private,
                allowed_mentions=safe,
            )

    @app_commands.command(name="uwu", description="Convert text into UwU speech.")
    @app_commands.describe(
        text="Text to convert", style="Optional personality",
        intensity="0-100; higher means more UwU", private="Only show you the result",
    )
    @app_commands.checks.cooldown(SLASH_COOLDOWN_USES, SLASH_COOLDOWN_SECONDS)
    async def uwu(
        self, interaction: discord.Interaction, text: str,
        style: Style | None = None,
        intensity: app_commands.Range[int, 0, 100] | None = None,
        private: bool = False,
    ):
        result = self._uwuify(
            text, interaction.guild_id, style=style, intensity=intensity
        )
        await self.send_result(interaction, result, private=private)

    async def menu_uwu(self, interaction: discord.Interaction, message: discord.Message):
        if not message.content:
            await interaction.response.send_message(
                "This message has no text I can convert.", ephemeral=True
            )
            return
        result = self._uwuify(message.content, interaction.guild_id)
        await self.send_result(interaction, result, private=True)

    @commands.command(name="uwuify")
    @commands.cooldown(
        PREFIX_COOLDOWN_USES, PREFIX_COOLDOWN_SECONDS, commands.BucketType.user
    )
    async def prefix_uwu(self, ctx: commands.Context, *, text: str):
        guild_id = ctx.guild.id if ctx.guild else None
        result = self._uwuify(text, guild_id)
        kwargs = {
            "mention_author": False,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if len(result) <= DISCORD_MESSAGE_LIMIT:
            await ctx.reply(result, **kwargs)
        else:
            await ctx.reply(file=self._as_file(result), **kwargs)

    @app_commands.command(name="uwusettings", description="Set this server's UwU defaults.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        style="Default personality", intensity="Default intensity, 0 to 100"
    )
    async def uwusettings(
        self, interaction: discord.Interaction,
        style: Style, intensity: app_commands.Range[int, 0, 100],
    ):
        current = self.guild_settings.setdefault(str(interaction.guild_id), {})
        current["style"] = style
        current["intensity"] = intensity
        self.save()
        await interaction.response.send_message(
            f"Defaults updated: **{style}**, **{intensity}/100**.", ephemeral=True
        )

    @app_commands.command(
        name="uwuauto", description="Enable or disable automatic UwU replies in this channel."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def uwuauto(self, interaction: discord.Interaction, enabled: bool):
        current = self.guild_settings.setdefault(str(interaction.guild_id), {})
        channels = set(current.get("auto_channels", []))
        channel_id = str(interaction.channel_id)
        if enabled:
            channels.add(channel_id)
        else:
            channels.discard(channel_id)
        current["auto_channels"] = sorted(channels)
        self.save()
        await interaction.response.send_message(
            f"Auto UwU replies {'enabled' if enabled else 'disabled'} here.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot or message.webhook_id:
            return
        cfg = self.settings(message.guild.id)
        if str(message.channel.id) not in cfg.get("auto_channels", []):
            return
        if (not message.content
                or message.content.lstrip().startswith(("!", "/", ".", "$", "?"))):
            return
        if len(message.content) > AUTO_MAX_INPUT_LENGTH:
            return
        now = time.monotonic()
        if now - self.last_auto.get(message.channel.id, 0) < AUTO_COOLDOWN_SECONDS:
            return
        result = self._uwuify(message.content, message.guild.id)
        if not result or result == message.content or len(result) > DISCORD_MESSAGE_LIMIT:
            return
        self.last_auto[message.channel.id] = now
        try:
            await message.reply(
                result, mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                suppress_embeds=True,
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UwuCog(bot))
