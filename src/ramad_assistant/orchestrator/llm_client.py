"""Lightweight LLM Client for Gemini 2.0 Flash with Native Tool Calling and Multi-turn History."""
import logging
from typing import Any, Callable, Optional
import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 12.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        )

    async def chat(
        self,
        system_instruction: str,
        user_message: str,
        history: Optional[list[dict[str, Any]]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_executor: Optional[Callable[[str, dict[str, Any]], Any]] = None,
        max_tool_steps: int = 5,
    ) -> str:
        """
        Sends a conversation turn to Gemini 2.0 Flash, executing tools if requested by the model.
        Returns the final conversational text response.
        """
        if not self.api_key:
            return "⚠️ מפתח ה-API אינו מוגדר. אנא הגדר GEMINI_API_KEY."

        # Format system instruction
        payload: dict[str, Any] = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.4,
            },
        }

        # Format tools if provided
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        # Build contents from history + current message
        contents: list[dict[str, Any]] = []
        if history:
            for item in history:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": item.get("text", "")}]})

        contents.append({"role": "user", "parts": [{"text": user_message}]})
        payload["contents"] = contents

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for _ in range(max_tool_steps):
                    resp = await client.post(self.endpoint, json=payload)
                    if resp.status_code != 200:
                        logger.error(f"Gemini API error ({resp.status_code}): {resp.text}")
                        return "סליחה, אני חווה עומס תקשורת זמני מול השרת. אנא נסה שוב בעוד רגע."

                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if not candidates:
                        return "סליחה, לא התקבלה תשובה תקינה. אנא נסה שוב."

                    candidate = candidates[0]
                    content = candidate.get("content") or {}
                    parts = content.get("parts") or []
                    if not parts:
                        return "סליחה, תוכן התשובה ריק. אנא נסה שוב."

                    # Check for tool call in parts
                    first_part = parts[0]
                    function_call = first_part.get("functionCall")

                    if function_call and tool_executor:
                        fn_name = function_call.get("name", "")
                        fn_args = function_call.get("args") or {}
                        logger.info(f"Executing tool: {fn_name} with args: {fn_args}")

                        try:
                            fn_result = tool_executor(fn_name, fn_args)
                            if hasattr(fn_result, "__await__"):
                                fn_result = await fn_result
                        except Exception as e:
                            logger.error(f"Tool execution failed for {fn_name}: {e}")
                            fn_result = {"error": f"Tool execution failed: {str(e)}"}

                        # Append model functionCall part to conversation
                        contents.append({"role": "model", "parts": [first_part]})
                        # Append function response to conversation
                        contents.append({
                            "role": "function",
                            "parts": [{
                                "functionResponse": {
                                    "name": fn_name,
                                    "response": {"result": fn_result},
                                }
                            }],
                        })
                        payload["contents"] = contents
                        continue

                    # If no function call, we have the conversational text
                    reply_text = first_part.get("text", "").strip()
                    return reply_text

                return "הפעולה בוצעה, אך השיחה ארכה מספר שלבים רב מהרגיל."

        except httpx.TimeoutException:
            logger.warning("Gemini API call timed out.")
            return "סליחה, אני חווה עומס תקשורת זמני מול שרתי ה-AI. אנא נסה שוב בעוד רגע."
        except Exception as e:
            logger.error(f"Unexpected error in LLMClient: {e}", exc_info=True)
            return "סליחה, חלה שגיאה זמנית בעיבוד ההודעה. אנא נסה שוב."
