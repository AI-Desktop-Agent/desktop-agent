import unicodedata

from langchain_core.tools import tool
from langgraph.types import interrupt

from packages.security.registry import secure_tool


MAX_QUESTION_LENGTH = 2000
MAX_OPTIONS = 20
MAX_OPTION_LENGTH = 200


def _contains_control_character(value: str) -> bool:
    return any(
        unicodedata.category(character).startswith("C")
        for character in value
    )


@secure_tool(risk="low")
@tool
async def ask_clarification(
    question: str,
    options: list[str] | None = None,
) -> dict:
    """Ask the user a bounded clarification question and wait for their answer.

    Use this when essential information is missing or the request has multiple
    reasonable choices. Do not use it to obtain security approval.
    """
    if not isinstance(question, str) or not question.strip():
        return {
            "success": False,
            "status": "invalid_question",
            "message": "Question must be a non-empty string.",
        }

    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return {
            "success": False,
            "status": "invalid_question",
            "message": "Question exceeds the maximum length.",
        }

    if _contains_control_character(question):
        return {
            "success": False,
            "status": "invalid_question",
            "message": "Question contains unsupported control characters.",
        }

    if options is None:
        options = []
    elif not isinstance(options, list):
        return {
            "success": False,
            "status": "invalid_options",
            "message": "Options must be a list of strings.",
        }

    if len(options) > MAX_OPTIONS:
        return {
            "success": False,
            "status": "invalid_options",
            "message": f"No more than {MAX_OPTIONS} options are supported.",
        }

    normalized_options = []
    for option in options:
        if not isinstance(option, str) or not option.strip():
            return {
                "success": False,
                "status": "invalid_options",
                "message": "Every option must be a non-empty string.",
            }

        option = option.strip()
        if len(option) > MAX_OPTION_LENGTH:
            return {
                "success": False,
                "status": "invalid_options",
                "message": "An option exceeds the maximum length.",
            }

        if _contains_control_character(option):
            return {
                "success": False,
                "status": "invalid_options",
                "message": "Options cannot contain control characters.",
            }

        if option.casefold() in {
            existing.casefold()
            for existing in normalized_options
        }:
            return {
                "success": False,
                "status": "invalid_options",
                "message": "Options must be unique.",
            }

        normalized_options.append(option)

    answer = interrupt(
        {
            "kind": "clarification",
            "prompt": question,
            "options": normalized_options,
        }
    )

    if not isinstance(answer, str) or not answer.strip():
        return {
            "success": False,
            "status": "invalid_response",
            "message": "Clarification response must be non-empty text.",
        }

    answer = answer.strip()
    if len(answer) > MAX_QUESTION_LENGTH or _contains_control_character(answer):
        return {
            "success": False,
            "status": "invalid_response",
            "message": "Clarification response is invalid.",
        }

    if normalized_options:
        selected_option = next(
            (
                option
                for option in normalized_options
                if option.casefold() == answer.casefold()
            ),
            None,
        )
        if selected_option is None:
            return {
                "success": False,
                "status": "invalid_response",
                "message": "Response must match one of the listed options.",
            }
        answer = selected_option

    return {
        "success": True,
        "status": "answered",
        "answer": answer,
    }
