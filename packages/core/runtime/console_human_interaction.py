import asyncio
import json
import re
import threading
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from packages.core.interfaces.human_interaction import HumanInteraction


class HumanInputUnavailable(RuntimeError):
    """Raised when clarification input cannot be collected."""


class ConsoleHumanInteraction(HumanInteraction):
    MAX_QUESTION_LENGTH = 2000
    MAX_OPTIONS = 20
    MAX_OPTION_LENGTH = 200
    MAX_ARGUMENTS_DISPLAY_LENGTH = 3000
    MAX_NESTING_DEPTH = 4
    MAX_COLLECTION_ITEMS = 20

    _SENSITIVE_KEY_PARTS = (
        "password",
        "passwd",
        "secret",
        "token",
        "apikey",
        "credential",
        "authorization",
        "cookie",
        "privatekey",
    )
    _SECRET_PATTERNS = (
        (
            re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"),
            r"\1[REDACTED]@",
        ),
        (
            re.compile(
                r"(?i)([?&](?:access_token|api_key|token|password|secret)=)"
                r"[^&#\s]+"
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}"),
            r"\1 [REDACTED]",
        ),
    )

    def __init__(self) -> None:
        self._prompt_lock = threading.Lock()

    @classmethod
    def _safe_terminal_text(cls, value: str, limit: int) -> str:
        for pattern, replacement in cls._SECRET_PATTERNS:
            value = pattern.sub(replacement, value)

        safe_chars = []
        for character in value[:limit]:
            if unicodedata.category(character).startswith("C"):
                safe_chars.append(f"\\u{ord(character):04x}")
            else:
                safe_chars.append(character)

        result = "".join(safe_chars)
        if len(value) > limit:
            result += "..."
        return result

    @classmethod
    def _is_sensitive_key(cls, key: object) -> bool:
        if not isinstance(key, str):
            return True

        normalized_key = "".join(
            character
            for character in key.lower()
            if character.isalnum()
        )
        return any(
            sensitive_part in normalized_key
            for sensitive_part in cls._SENSITIVE_KEY_PARTS
        )

    @classmethod
    def _safe_value(cls, value: Any, depth: int = 0) -> Any:
        if depth >= cls.MAX_NESTING_DEPTH:
            return "[nested value omitted]"

        if isinstance(value, Mapping):
            safe_mapping = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= cls.MAX_COLLECTION_ITEMS:
                    safe_mapping["..."] = "[additional values omitted]"
                    break

                display_key = (
                    cls._safe_terminal_text(key, 100)
                    if isinstance(key, str)
                    else f"<{type(key).__name__}>"
                )
                safe_mapping[display_key] = (
                    "[REDACTED]"
                    if cls._is_sensitive_key(key)
                    else cls._safe_value(item, depth + 1)
                )
            return safe_mapping

        if isinstance(value, (list, tuple)):
            safe_items = [
                cls._safe_value(item, depth + 1)
                for item in value[: cls.MAX_COLLECTION_ITEMS]
            ]
            if len(value) > cls.MAX_COLLECTION_ITEMS:
                safe_items.append("[additional values omitted]")
            return safe_items

        if isinstance(value, str):
            return cls._safe_terminal_text(value, 500)

        if value is None or isinstance(value, (bool, int, float)):
            return value

        return f"<{type(value).__name__}>"

    @classmethod
    def _format_arguments(cls, args: Mapping[str, object]) -> str:
        safe_args = cls._safe_value(args)
        rendered = json.dumps(safe_args, ensure_ascii=True, sort_keys=True)
        if len(rendered) > cls.MAX_ARGUMENTS_DISPLAY_LENGTH:
            return rendered[: cls.MAX_ARGUMENTS_DISPLAY_LENGTH - 3] + "..."
        return rendered

    def _read_line(self, prompt: str) -> str | None:
        with self._prompt_lock:
            try:
                return input(prompt)
            except (EOFError, KeyboardInterrupt):
                return None

    @classmethod
    def _normalize_options(
        cls,
        options: Sequence[str] | None,
    ) -> tuple[str, ...]:
        if options is None:
            return ()

        if isinstance(options, str):
            raise TypeError("options must be a sequence of option strings")

        normalized_options = []
        for option in options:
            if not isinstance(option, str) or not option.strip():
                raise ValueError("every option must be a non-empty string")
            normalized_options.append(option.strip())

        if len(normalized_options) > cls.MAX_OPTIONS:
            raise ValueError(
                f"no more than {cls.MAX_OPTIONS} options are supported"
            )

        return tuple(normalized_options)

    async def ask_clarification(
        self,
        question: str,
        options: Sequence[str] | None = None,
    ) -> str:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")

        safe_question = self._safe_terminal_text(
            question.strip(),
            self.MAX_QUESTION_LENGTH,
        )
        safe_options = self._normalize_options(options)

        if safe_options:
            print(safe_question)
            for index, option in enumerate(safe_options, start=1):
                safe_option = self._safe_terminal_text(
                    option,
                    self.MAX_OPTION_LENGTH,
                )
                print(f"  {index}. {safe_option}")

        while True:
            answer = await asyncio.to_thread(
                self._read_line,
                "Your answer> ",
            )

            if answer is None:
                raise HumanInputUnavailable(
                    "Could not collect the clarification response."
                )

            answer = answer.strip()
            if not answer:
                print("Please enter a response.")
                continue

            if not safe_options:
                return answer

            if answer.isdecimal():
                selected_index = int(answer) - 1
                if 0 <= selected_index < len(safe_options):
                    return safe_options[selected_index]

            for option in safe_options:
                if answer.casefold() == option.casefold():
                    return option

            print("Choose an option by number or enter one of the listed choices.")

    async def request_approval(
        self,
        tool_name: str,
        risk: str,
        args: Mapping[str, object],
        principal: str,
    ) -> bool:
        if not isinstance(args, Mapping):
            raise TypeError("approval arguments must be a mapping")

        print("\nSECURITY APPROVAL REQUIRED")
        print(f"Tool: {self._safe_terminal_text(tool_name, 200)}")
        print(f"Risk: {self._safe_terminal_text(risk, 50)}")
        print(f"User: {self._safe_terminal_text(principal, 200)}")
        print(f"Arguments: {self._format_arguments(args)}")
        print("Type 'approve' exactly to allow this action; anything else denies.")

        answer = await asyncio.to_thread(
            self._read_line,
            "Approval> ",
        )
        approved = answer is not None and answer.strip().casefold() == "approve"

        if not approved:
            print("Action denied.")

        return approved
