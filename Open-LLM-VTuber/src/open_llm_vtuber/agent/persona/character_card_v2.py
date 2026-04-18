"""Character Card V2 loader.

Parses JSON files following the SillyTavern Character Card V2 spec:
https://github.com/malfoyslastname/character-card-spec-v2

The parsed card is rendered into a system prompt that can be plugged
into Open-LLM-VTuber's existing agent pipeline. The renderer also
exposes the card's `mes_example` field in a chat-completion-friendly
format so the host agent can prepend it as few-shot context messages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


_PLACEHOLDER_USER = "{{user}}"
_PLACEHOLDER_CHAR = "{{char}}"


@dataclass
class CharacterCardV2:
    """Holds the resolved fields of a Character Card V2 file.

    Only the fields actually used to build the system prompt are
    materialized. Unknown / extension fields are preserved in `extra`
    so downstream tools can reach them if needed.
    """

    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    creator_notes: str = ""
    tags: List[str] = field(default_factory=list)
    alternate_greetings: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_example_dialogue(self) -> bool:
        return bool(self.mes_example.strip())


class CharacterCardV2Loader:
    """Load a Character Card V2 JSON file and render it into prompts."""

    def __init__(self, card_path: str | Path, *, user_name: str = "User") -> None:
        self._path = Path(card_path)
        if not self._path.is_file():
            raise FileNotFoundError(
                f"Character card not found at: {self._path.resolve()}"
            )
        self._user_name = user_name
        self._raw: Dict[str, Any] = json.loads(
            self._path.read_text(encoding="utf-8")
        )
        self._card = self._extract_card(self._raw)
        logger.info(
            f"CharacterCardV2: loaded '{self._card.name}' from {self._path.name}"
        )

    @staticmethod
    def _extract_card(raw: Dict[str, Any]) -> CharacterCardV2:
        """Resolve V2 'data' wrapper or fall back to V1 flat layout."""
        spec = raw.get("spec")
        if spec == "chara_card_v2" and isinstance(raw.get("data"), dict):
            data = raw["data"]
        else:
            data = raw

        def _get(key: str, default: str = "") -> str:
            value = data.get(key, default)
            return value if isinstance(value, str) else default

        return CharacterCardV2(
            name=_get("name") or "Companion",
            description=_get("description"),
            personality=_get("personality"),
            scenario=_get("scenario"),
            first_mes=_get("first_mes"),
            mes_example=_get("mes_example"),
            system_prompt=_get("system_prompt"),
            post_history_instructions=_get("post_history_instructions"),
            creator_notes=_get("creator_notes"),
            tags=list(data.get("tags") or []),
            alternate_greetings=list(data.get("alternate_greetings") or []),
            extra={
                k: v
                for k, v in data.items()
                if k
                not in {
                    "name",
                    "description",
                    "personality",
                    "scenario",
                    "first_mes",
                    "mes_example",
                    "system_prompt",
                    "post_history_instructions",
                    "creator_notes",
                    "tags",
                    "alternate_greetings",
                }
            },
        )

    @property
    def card(self) -> CharacterCardV2:
        return self._card

    def _substitute(self, text: str) -> str:
        if not text:
            return ""
        return (
            text.replace(_PLACEHOLDER_USER, self._user_name).replace(
                _PLACEHOLDER_CHAR, self._card.name
            )
        )

    def build_system_prompt(self) -> str:
        """Render the card into a single system-prompt string.

        Order matches SillyTavern's default rendering: a custom
        `system_prompt` (if present) overrides the default header,
        then description / personality / scenario follow.
        """
        sections: List[str] = []

        if self._card.system_prompt:
            sections.append(self._substitute(self._card.system_prompt))
        else:
            sections.append(
                f"You are {self._card.name}, an AI companion talking with "
                f"{self._user_name}. Stay in character at all times."
            )

        if self._card.description:
            sections.append(
                "## Character Description\n" + self._substitute(self._card.description)
            )

        if self._card.personality:
            sections.append(
                "## Personality\n" + self._substitute(self._card.personality)
            )

        if self._card.scenario:
            sections.append("## Scenario\n" + self._substitute(self._card.scenario))

        if self._card.post_history_instructions:
            sections.append(
                "## Additional Instructions\n"
                + self._substitute(self._card.post_history_instructions)
            )

        return "\n\n".join(s for s in sections if s.strip())

    def build_few_shot_messages(self) -> List[Dict[str, str]]:
        """Convert mes_example into chat completion few-shot messages.

        SillyTavern uses the `<START>` separator between distinct
        example dialogues. Each block then has lines like::

            {{user}}: hello
            {{char}}: hi there

        We split on `<START>` and parse each speaker block. Lines that
        don't start with the user/char prefix are appended to the prior
        block as continuation text.
        """
        if not self._card.has_example_dialogue:
            return []

        messages: List[Dict[str, str]] = []
        blocks = [
            b.strip()
            for b in self._substitute(self._card.mes_example).split("<START>")
            if b.strip()
        ]

        char_prefix = f"{self._card.name}:"
        user_prefix = f"{self._user_name}:"

        for block in blocks:
            current_role: Optional[str] = None
            current_buffer: List[str] = []
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue

                role, content = self._classify_line(
                    stripped, char_prefix=char_prefix, user_prefix=user_prefix
                )
                if role is None:
                    if current_role is not None:
                        current_buffer.append(stripped)
                    continue

                if current_role and current_buffer:
                    messages.append(
                        {
                            "role": current_role,
                            "content": "\n".join(current_buffer).strip(),
                        }
                    )

                current_role = role
                current_buffer = [content] if content else []

            if current_role and current_buffer:
                messages.append(
                    {
                        "role": current_role,
                        "content": "\n".join(current_buffer).strip(),
                    }
                )

        return messages

    @staticmethod
    def _classify_line(
        line: str, *, char_prefix: str, user_prefix: str
    ) -> Tuple[Optional[str], str]:
        for prefix, role in (
            (char_prefix, "assistant"),
            (user_prefix, "user"),
        ):
            if line.startswith(prefix):
                return role, line[len(prefix) :].strip()
        return None, line

    def build_initial_greeting(self) -> str:
        """Return the first_mes (a.k.a. the character's opening line)."""
        return self._substitute(self._card.first_mes)
