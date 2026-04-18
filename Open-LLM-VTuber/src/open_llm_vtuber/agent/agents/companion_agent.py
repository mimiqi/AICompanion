"""CompanionAgent - extends BasicMemoryAgent with Character Card V2 + long-term memory.

Design notes:

- We subclass `BasicMemoryAgent` to keep all of OLV's hard-won LLM /
  MCP / tool-calling / sentence pipeline behaviour. Only the parts we
  actually need to customize are overridden:
    * `__init__` accepts a Character Card V2 path + a long-term memory
      store, and rebuilds the system prompt from the card.
    * `_to_messages` injects the few-shot example dialogue (once) and
      prepends ChromaDB-recalled memories before the user turn.
    * `_add_message` mirrors the entry into the long-term store so the
      next turn can recall it.

- The long-term store is an `Optional[MemoryStore]`. When `None` the
  agent behaves identically to `BasicMemoryAgent` (still useful for
  M2-3 before ChromaDB is wired in at M3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from loguru import logger

from .basic_memory_agent import BasicMemoryAgent
from ..input_types import BatchInput
from ..memory import MemoryStore
from ..persona import CharacterCardV2Loader
from ...config_manager import TTSPreprocessorConfig
from ...mcpp.tool_executor import ToolExecutor
from ...mcpp.tool_manager import ToolManager
from ..stateless_llm.stateless_llm_interface import StatelessLLMInterface


class CompanionAgent(BasicMemoryAgent):
    """Personality- and memory-augmented agent."""

    def __init__(
        self,
        llm: StatelessLLMInterface,
        live2d_model,
        character_card_path: str,
        *,
        user_name: str = "User",
        memory_store: Optional[MemoryStore] = None,
        memory_top_k: int = 4,
        short_term_window: int = 8,
        tts_preprocessor_config: Optional[TTSPreprocessorConfig] = None,
        faster_first_response: bool = True,
        segment_method: str = "pysbd",
        use_mcpp: bool = False,
        interrupt_method: Literal["system", "user"] = "user",
        tool_prompts: Optional[Dict[str, str]] = None,
        tool_manager: Optional[ToolManager] = None,
        tool_executor: Optional[ToolExecutor] = None,
        mcp_prompt_string: str = "",
    ) -> None:
        self._card_loader = CharacterCardV2Loader(
            Path(character_card_path), user_name=user_name
        )
        rendered_system = self._card_loader.build_system_prompt()

        super().__init__(
            llm=llm,
            system=rendered_system,
            live2d_model=live2d_model,
            tts_preprocessor_config=tts_preprocessor_config,
            faster_first_response=faster_first_response,
            segment_method=segment_method,
            use_mcpp=use_mcpp,
            interrupt_method=interrupt_method,
            tool_prompts=tool_prompts,
            tool_manager=tool_manager,
            tool_executor=tool_executor,
            mcp_prompt_string=mcp_prompt_string,
        )

        self._memory_store = memory_store
        self._memory_top_k = max(0, int(memory_top_k))
        self._short_term_window = max(0, int(short_term_window))
        self._few_shot_injected = False

        logger.info(
            f"CompanionAgent ready - card='{self._card_loader.card.name}' "
            f"long_term_memory={'on' if memory_store else 'off'} "
            f"top_k={self._memory_top_k} window={self._short_term_window}"
        )

    @property
    def first_message(self) -> str:
        """Expose the card's first_mes so the host can play it on connect."""
        return self._card_loader.build_initial_greeting()

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        super().set_memory_from_history(conf_uid, history_uid)
        self._few_shot_injected = bool(self._memory)

    def _trim_short_term(self) -> None:
        """Keep only the most recent N turns in the short-term buffer."""
        if self._short_term_window <= 0:
            return
        max_messages = self._short_term_window * 2
        if len(self._memory) > max_messages:
            dropped = len(self._memory) - max_messages
            self._memory = self._memory[-max_messages:]
            logger.debug(
                f"CompanionAgent: trimmed {dropped} old messages "
                f"(window={self._short_term_window})"
            )

    def _build_recall_block(self, query_text: str) -> Optional[Dict[str, str]]:
        """Query long-term store and return a synthetic system message."""
        if not self._memory_store or self._memory_top_k <= 0 or not query_text:
            return None

        try:
            records = self._memory_store.query(query_text, top_k=self._memory_top_k)
        except Exception as exc:
            logger.warning(f"CompanionAgent: memory recall failed - {exc}")
            return None

        if not records:
            return None

        rendered = "\n".join(f"- {rec.render()}" for rec in records)
        return {
            "role": "system",
            "content": (
                "Relevant past context (long-term memory):\n"
                f"{rendered}\n"
                "Treat this as background knowledge; do not quote it verbatim."
            ),
        }

    def _maybe_inject_few_shot(self) -> None:
        if self._few_shot_injected:
            return
        few_shot = self._card_loader.build_few_shot_messages()
        if few_shot:
            self._memory = few_shot + self._memory
            logger.debug(
                f"CompanionAgent: injected {len(few_shot)} few-shot turns from card"
            )
        self._few_shot_injected = True

    def _to_messages(self, input_data: BatchInput) -> List[Dict[str, Any]]:
        self._maybe_inject_few_shot()
        self._trim_short_term()

        messages = super()._to_messages(input_data)

        recall = self._build_recall_block(self._to_text_prompt(input_data))
        if recall and messages:
            insert_at = max(0, len(messages) - 1)
            messages.insert(insert_at, recall)
        elif recall:
            messages.append(recall)

        return messages

    def _add_message(
        self,
        message: Union[str, List[Dict[str, Any]]],
        role: str,
        display_text=None,
        skip_memory: bool = False,
    ) -> None:
        super()._add_message(message, role, display_text, skip_memory)

        if skip_memory or not self._memory_store:
            return

        text_content = ""
        if isinstance(message, list):
            for item in message:
                if item.get("type") == "text":
                    text_content += item["text"] + " "
            text_content = text_content.strip()
        elif isinstance(message, str):
            text_content = message

        if not text_content:
            return

        try:
            self._memory_store.add(
                text_content,
                role=role,
                metadata={
                    "character": self._card_loader.card.name,
                },
            )
        except Exception as exc:
            logger.warning(f"CompanionAgent: failed to write long-term memory - {exc}")
