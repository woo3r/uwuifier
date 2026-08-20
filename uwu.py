import re
import random
import os
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class SpeechType(Enum):
    NEUTRAL = auto()
    QUESTION = auto()
    EXCITED = auto()
    COMMAND = auto()
    GREETING = auto()
    GRATITUDE = auto()
    APOLOGY = auto()
    SAD = auto()
    AFFECTIONATE = auto()
    LAUGHTER = auto()


@dataclass(slots=True)
class UwuConfig:
    intensity: float = 0.90

    faces: bool = True
    stutters: bool = True
    word_swaps: bool = True
    phonetics: bool = True
    tildes: bool = True

    preserve_commands: bool = True
    command_prefixes: tuple[str, ...] = ("!", "?", ".", "/", "$", "-")

    seed: Optional[int] = None


class Uwuifier:
    """
    Discord-aware, context-sensitive UwU text transformer.

    Designed to preserve:
      - Discord user mentions
      - role mentions
      - channel mentions
      - custom emojis
      - Discord timestamps
      - slash commands / configured command prefixes
      - URLs
      - email addresses
      - inline code
      - fenced code blocks
      - markdown links
      - spoilers

    Transformations dynamically vary based on detected speech type.
    """


    PROTECTED_RE = re.compile(
        r"""
        ```[\s\S]*?```                         | # fenced code
        `[^`\n]*`                              | # inline code

        <@!?\d+>                               | # user mention
        <@&\d+>                                | # role mention
        <\#\d+>                                | # channel mention
        <a?:[A-Za-z0-9_]+:\d+>                 | # custom emoji
        <t:\d+(?::[tTdDfFR])?>                 | # Discord timestamp

        https?://[^\s<]+                       | # URL
        www\.[^\s<]+                           | # URL without protocol

        [A-Za-z0-9._%+-]+
        @[A-Za-z0-9.-]+\.[A-Za-z]{2,}          | # email

        \[[^\]]+\]\([^)]+\)                    | # markdown link
        \|\|.*?\|\|                              # Discord spoiler
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")

    SENTENCE_SPLIT_RE = re.compile(
        r"(?<=[.!?])(?=\s+)|(?=\n)"
    )

    # Context detection

    GREETINGS = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "howdy",
        "morning",
        "afternoon",
        "evening",
        "sup",
        "yo",
    }

    GRATITUDE_WORDS = {
        "thanks",
        "thank",
        "thx",
        "ty",
        "appreciate",
        "grateful",
    }

    APOLOGY_WORDS = {
        "sorry",
        "apologies",
        "apologize",
        "apologise",
        "my bad",
    }

    SAD_WORDS = {
        "sad",
        "upset",
        "hurt",
        "cry",
        "crying",
        "depressed",
        "unhappy",
        "unfortunately",
        "miss",
        "lonely",
        "terrible",
    }

    AFFECTION_WORDS = {
        "love",
        "lovely",
        "cute",
        "adorable",
        "sweet",
        "beautiful",
        "pretty",
        "hug",
        "kiss",
        "darling",
    }

    LAUGHTER_WORDS = {
        "lol",
        "lmao",
        "lmfao",
        "haha",
        "hahaha",
        "hehe",
        "hehehe",
        "rofl",
    }

    COMMAND_STARTERS = {
        "do",
        "make",
        "give",
        "tell",
        "show",
        "send",
        "stop",
        "go",
        "come",
        "look",
        "listen",
        "check",
        "open",
        "close",
        "run",
        "please",
        "let",
        "try",
        "remember",
        "wait",
    }

    EXCITED_STARTERS = {
        "wow",
        "omg",
        "whoa",
        "woah",
        "yay",
        "yayy",
        "holy",
        "awesome",
        "amazing",
    }

    # UwU vocabulary

    WORD_SWAPS = {
        "hello": "hewwo",
        "hey": "hewwo",
        "hi": "hai",
        "friend": "fwiend",
        "friends": "fwiends",
        "small": "smol",
        "little": "wittle",
        "cute": "kawaii",
        "love": "wuv",
        "loves": "wuvs",
        "lovely": "wuvwy",
        "please": "pwease",
        "really": "weawwy",
        "very": "vewy",
        "sorry": "sowwy",
        "thanks": "fanks",
        "thank": "fank",
        "what": "wat",
        "why": "wai",
        "this": "dis",
        "that": "dat",
        "there": "dewe",
        "they": "dey",
        "them": "dem",
        "the": "da",
        "because": "becuz",
        "okay": "oki",
        "ok": "oki",
        "no": "nu",
        "yes": "yus",
        "you": "chu",
        "your": "ur",
        "you're": "ur",
        "youre": "ur",
        "good": "gud",
    }

    INTERJECTIONS = {
        "wow": ("waow", "wowie", "owo"),
        "oh": ("ohh", "owo"),
        "aww": ("awww", "awww~"),
        "yes": ("yus", "yush"),
        "yeah": ("yea", "yus"),
        "no": ("nu", "nuuu"),
        "haha": ("hehe", "ehehe"),
        "lol": ("hehe", "lawl"),
        "omg": ("omg", "owo"),
    }

    FACES = {
        SpeechType.NEUTRAL: (
            "uwu",
            "owo",
            ":3",
            "^w^",
            "(◕‿◕)",
        ),
        SpeechType.QUESTION: (
            "owo?",
            "uwu?",
            "(・`ω´・)?",
            "(•ิ_•ิ)?",
        ),
        SpeechType.EXCITED: (
            "OwO!",
            "UwU!",
            "(≧▽≦)",
            "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
            ">:3",
        ),
        SpeechType.GREETING: (
            "uwu",
            "owo",
            "(＾▽＾)",
            "^w^",
        ),
        SpeechType.GRATITUDE: (
            "uwu",
            "(｡♥‿♥｡)",
            "(≧▽≦)",
        ),
        SpeechType.APOLOGY: (
            "unu",
            "uwu",
            "(｡•́︿•̀｡)",
        ),
        SpeechType.SAD: (
            "QwQ",
            "T_T",
            "unu",
            "(｡•́︿•̀｡)",
        ),
        SpeechType.AFFECTIONATE: (
            "uwu",
            "♡",
            "(｡♥‿♥｡)",
            "(づ｡◕‿‿◕｡)づ",
        ),
        SpeechType.LAUGHTER: (
            "x3",
            "hehe~",
            ">:3",
            "(≧▽≦)",
        ),
        SpeechType.COMMAND: (
            "uwu",
            ":3",
        ),
    }

    def __init__(self, config: Optional[UwuConfig] = None):
        self.config = config or UwuConfig()

        if not 0.0 <= self.config.intensity <= 1.0:
            raise ValueError("intensity must be between 0.0 and 1.0")

        self.random = random.Random(self.config.seed)

    # Probability

    def chance(self, base_probability: float, multiplier: float = 1.0) -> bool:
        probability = (
            base_probability
            * self.config.intensity
            * multiplier
        )

        return self.random.random() < max(0.0, min(probability, 1.0))

    # Case handling

    @staticmethod
    def preserve_case(original: str, replacement: str) -> str:
        if original.isupper():
            return replacement.upper()

        if original.istitle():
            return replacement.capitalize()

        return replacement

    # Discord command protection

    def is_command(self, text: str) -> bool:
        if not self.config.preserve_commands:
            return False

        stripped = text.lstrip()

        return any(
            stripped.startswith(prefix)
            for prefix in self.config.command_prefixes
        )

    # Speech classification

    def detect_speech_type(self, text: str) -> SpeechType:
        clean = text.strip()

        if not clean:
            return SpeechType.NEUTRAL

        lower = clean.lower()

        words = re.findall(r"[a-z']+", lower)
        word_set = set(words)

        first_word = words[0] if words else ""

        # Strong structural signals
        if clean.endswith("?"):
            return SpeechType.QUESTION

        if (
            clean.count("!") >= 2
            or first_word in self.EXCITED_STARTERS
            or self._uppercase_ratio(clean) >= 0.65
        ):
            return SpeechType.EXCITED

        # Semantic categories
        if word_set & self.LAUGHTER_WORDS:
            return SpeechType.LAUGHTER

        if self._contains_phrase(lower, self.APOLOGY_WORDS):
            return SpeechType.APOLOGY

        if word_set & self.SAD_WORDS:
            return SpeechType.SAD

        if word_set & self.GRATITUDE_WORDS:
            return SpeechType.GRATITUDE

        if word_set & self.AFFECTION_WORDS:
            return SpeechType.AFFECTIONATE

        if first_word in self.GREETINGS:
            return SpeechType.GREETING

        if first_word in self.COMMAND_STARTERS:
            return SpeechType.COMMAND

        return SpeechType.NEUTRAL

    @staticmethod
    def _contains_phrase(text: str, values: set[str]) -> bool:
        return any(value in text for value in values)

    @staticmethod
    def _uppercase_ratio(text: str) -> float:
        letters = [char for char in text if char.isalpha()]

        if len(letters) < 4:
            return 0.0

        uppercase = sum(char.isupper() for char in letters)

        return uppercase / len(letters)

    # Speech-specific transformation strength

    @staticmethod
    def speech_multiplier(speech_type: SpeechType) -> float:
        return {
            SpeechType.NEUTRAL: 1.0,
            SpeechType.QUESTION: 0.90,
            SpeechType.EXCITED: 1.25,
            SpeechType.COMMAND: 0.75,
            SpeechType.GREETING: 1.10,
            SpeechType.GRATITUDE: 1.05,
            SpeechType.APOLOGY: 0.80,
            SpeechType.SAD: 0.70,
            SpeechType.AFFECTIONATE: 1.20,
            SpeechType.LAUGHTER: 1.15,
        }[speech_type]

    # Word transformations

    def transform_word(
        self,
        word: str,
        speech_type: SpeechType,
    ) -> str:
        multiplier = self.speech_multiplier(speech_type)

        result = word

        if self.config.word_swaps:
            result = self.apply_word_swap(
                result,
                multiplier,
            )

        if self.config.phonetics:
            result = self.apply_phonetics(
                result,
                multiplier,
            )

        if self.config.stutters:
            result = self.apply_stutter(
                result,
                speech_type,
                multiplier,
            )

        return result

    def apply_word_swap(
        self,
        word: str,
        multiplier: float,
    ) -> str:
        lower = word.lower()

        if lower in self.INTERJECTIONS:
            if self.chance(0.78, multiplier):
                replacement = self.random.choice(
                    self.INTERJECTIONS[lower]
                )
                return self.preserve_case(word, replacement)

        replacement = self.WORD_SWAPS.get(lower)

        if replacement and self.chance(0.92, multiplier):
            return self.preserve_case(word, replacement)

        return word

    def apply_phonetics(
        self,
        word: str,
        multiplier: float,
    ) -> str:
        if len(word) <= 1:
            return word

        # Preserve acronyms:
        # API, HTTP, JSON, SQL, CPU, etc.
        if word.isupper() and len(word) > 1:
            return word

        original = word
        result = word.lower()

        # R/L -> W
        if self.chance(1.0, multiplier):
            result = re.sub(r"[rl]", "w", result)

        # N + vowel -> NY + vowel
        if self.chance(0.42, multiplier):
            result = re.sub(
                r"n([aeiou])",
                r"ny\1",
                result,
            )

        # Word-start TH variants
        if self.chance(0.18, multiplier):
            result = re.sub(
                r"^th(?=[aeiou])",
                "d",
                result,
            )

        # "-ove" -> "-uv"
        if self.chance(0.25, multiplier):
            result = re.sub(
                r"ove\b",
                "uv",
                result,
            )

        # "-er" -> "-ew"
        if len(result) >= 5 and self.chance(0.14, multiplier):
            result = re.sub(
                r"er\b",
                "ew",
                result,
            )

        return self.preserve_case(original, result)

    def apply_stutter(
        self,
        word: str,
        speech_type: SpeechType,
        multiplier: float,
    ) -> str:
        if len(word) < 3:
            return word

        if not word[0].isalpha():
            return word

        # Commands and sad/apologetic.
        probability = {
            SpeechType.EXCITED: 0.15,
            SpeechType.AFFECTIONATE: 0.13,
            SpeechType.GREETING: 0.12,
            SpeechType.LAUGHTER: 0.10,
            SpeechType.NEUTRAL: 0.13,
            SpeechType.QUESTION: 0.07,
            SpeechType.GRATITUDE: 0.07,
            SpeechType.COMMAND: 0.04,
            SpeechType.APOLOGY: 0.035,
            SpeechType.SAD: 0.03,
        }[speech_type]

        if not self.chance(probability, multiplier):
            return word

        first = word[0]

        repetitions = (
            2
            if self.chance(0.10, multiplier)
            else 1
        )

        prefix = "-".join(first for _ in range(repetitions))

        return f"{prefix}-{word}"

    # Segment processing

    def transform_unprotected(
        self,
        text: str,
        speech_type: SpeechType,
    ) -> str:
        return self.WORD_RE.sub(
            lambda match: self.transform_word(
                match.group(0),
                speech_type,
            ),
            text,
        )

    def transform_preserving_discord(
        self,
        text: str,
        speech_type: SpeechType,
    ) -> str:
        result = []
        last_end = 0

        for match in self.PROTECTED_RE.finditer(text):
            before = text[last_end:match.start()]

            result.append(
                self.transform_unprotected(
                    before,
                    speech_type,
                )
            )

            result.append(match.group(0))
            last_end = match.end()

        result.append(
            self.transform_unprotected(
                text[last_end:],
                speech_type,
            )
        )

        return "".join(result)

    # Sentence-level styling

    def stylize_sentence(
        self,
        text: str,
        speech_type: SpeechType,
    ) -> str:
        multiplier = self.speech_multiplier(speech_type)

        result = text.rstrip()

        if not result:
            return text

        if self.config.tildes:
            tilde_probability = {
                SpeechType.AFFECTIONATE: 0.72,
                SpeechType.GREETING: 0.62,
                SpeechType.EXCITED: 0.60,
                SpeechType.LAUGHTER: 0.68,
                SpeechType.NEUTRAL: 0.58,
                SpeechType.GRATITUDE: 0.55,
                SpeechType.QUESTION: 0.35,
                SpeechType.COMMAND: 0.04,
                SpeechType.APOLOGY: 0.03,
                SpeechType.SAD: 0.02,
            }[speech_type]

            if self.chance(tilde_probability, multiplier):
                if re.search(r"[.!]$", result):
                    result += "~"
                elif not result.endswith(("?", "~")):
                    result += "~"

        if self.config.faces:
            result = self.add_face(
                result,
                speech_type,
                multiplier,
            )

        trailing_space = text[len(text.rstrip()):]

        return result + trailing_space

    def add_face(
        self,
        text: str,
        speech_type: SpeechType,
        multiplier: float,
    ) -> str:
        face_probability = {
            SpeechType.EXCITED: 0.30,
            SpeechType.AFFECTIONATE: 0.30,
            SpeechType.GREETING: 0.22,
            SpeechType.LAUGHTER: 0.22,
            SpeechType.GRATITUDE: 0.18,
            SpeechType.QUESTION: 0.15,
            SpeechType.NEUTRAL: 0.20,
            SpeechType.APOLOGY: 0.10,
            SpeechType.SAD: 0.10,
            SpeechType.COMMAND: 0.06,
        }[speech_type]

        if not self.chance(face_probability, multiplier):
            return text

        face = self.random.choice(
            self.FACES[speech_type]
        )

        return f"{text} {face}"

    # Line processing

    def transform_line(self, line: str) -> str:
        if not line.strip():
            return line

        # Don't touch Discord/bot commands.
        if self.is_command(line):
            return line

        # Avoid transforming pure protected Discord content.
        stripped = line.strip()

        if self.PROTECTED_RE.fullmatch(stripped):
            return line

        speech_type = self.detect_speech_type(line)

        transformed = self.transform_preserving_discord(
            line,
            speech_type,
        )

        return self.stylize_sentence(
            transformed,
            speech_type,
        )

    # Public API

    def uwuify(self, text: str) -> str:
        """
        UwUify Discord message content while preserving Discord-specific
        syntax and adapting transformations to the detected speech style.
        """

        if not text:
            return text

        # Entire bot commands stay untouched.
        if self.is_command(text):
            return text

        # Protect multiline code fences before line processing.
        output = []
        last_end = 0

        for match in re.finditer(r"```[\s\S]*?```", text):
            normal_text = text[last_end:match.start()]

            output.append(
                self._process_normal_text(normal_text)
            )

            output.append(match.group(0))

            last_end = match.end()

        output.append(
            self._process_normal_text(text[last_end:])
        )

        return "".join(output)

    def _process_normal_text(self, text: str) -> str:
        if not text:
            return text

        # Keep exact newlines intact.
        lines = text.splitlines(keepends=True)

        output = []

        for line in lines:
            newline = ""

            if line.endswith("\r\n"):
                body = line[:-2]
                newline = "\r\n"

            elif line.endswith("\n"):
                body = line[:-1]
                newline = "\n"

            else:
                body = line

            output.append(
                self.transform_line(body) + newline
            )

        return "".join(output)


def main() -> int:
    """Small stdin/stdout bridge used by the Discord bot service."""
    source = sys.stdin.read()
    if not source:
        return 0

    try:
        intensity = float(os.environ.get("UWUIFIER_INTENSITY", "0.90"))
    except ValueError:
        intensity = 0.90
    intensity = max(0.0, min(intensity, 1.0))

    seed_value = os.environ.get("UWUIFIER_SEED")
    try:
        seed = int(seed_value) if seed_value else None
    except ValueError:
        seed = None

    output = Uwuifier(UwuConfig(intensity=intensity, seed=seed)).uwuify(source)
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
