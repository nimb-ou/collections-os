"""
Natural Language Understanding using Ollama Qwen
JSON-constrained intent extraction and slot filling
NEVER free-generates compliance-sensitive content
"""

import logging
import json
import requests
from typing import Dict, Any, Optional, List

from config import (
    NLU_MODEL,
    NLU_ENDPOINT,
    NLU_TEMPERATURE,
    NLU_MAX_TOKENS,
    INTENT_CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


class NLUEngine:
    """
    NLU engine using Ollama Qwen for intent extraction.

    CRITICAL: LLM is used ONLY for understanding user input.
    It NEVER generates bot responses - those come from fixed prompts.
    """

    def __init__(
        self,
        model: str = NLU_MODEL,
        endpoint: str = NLU_ENDPOINT,
        temperature: float = NLU_TEMPERATURE,
    ):
        """
        Initialize NLU engine.

        Args:
            model: Ollama model name
            endpoint: Ollama API endpoint
            temperature: Sampling temperature (low for consistency)
        """
        self.model = model
        self.endpoint = endpoint
        self.temperature = temperature

        logger.info(f"Initializing NLU engine: {model} @ {endpoint}")

    def extract_intent(
        self,
        user_input: str,
        context: Dict[str, Any],
        allowed_intents: List[str],
    ) -> Dict[str, Any]:
        """
        Extract user intent from input.

        Args:
            user_input: User's spoken text (from STT)
            context: Conversation context (current state, account info)
            allowed_intents: List of valid intents for current state

        Returns:
            Dictionary with:
                - intent: Detected intent
                - confidence: Confidence score (0-1)
                - slots: Extracted slot values (dict)
        """
        # Build prompt for intent extraction
        prompt = self._build_intent_prompt(user_input, context, allowed_intents)

        try:
            # Call Ollama API
            response = requests.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "max_tokens": NLU_MAX_TOKENS,
                    "stream": False,
                },
                timeout=30,
            )
            response.raise_for_status()

            result_text = response.json().get("response", "")

            # Parse JSON response
            result = self._parse_json_response(result_text)

            # Validate intent
            intent = result.get("intent", "unknown")
            if intent not in allowed_intents:
                logger.warning(f"Invalid intent '{intent}', defaulting to 'unknown'")
                intent = "unknown"

            # Normalize confidence
            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            return {
                "intent": intent,
                "confidence": confidence,
                "slots": result.get("slots", {}),
            }

        except Exception as e:
            logger.error(f"NLU extraction failed: {e}")
            return {
                "intent": "error",
                "confidence": 0.0,
                "slots": {},
                "error": str(e),
            }

    def _build_intent_prompt(
        self,
        user_input: str,
        context: Dict[str, Any],
        allowed_intents: List[str],
    ) -> str:
        """
        Build prompt for intent extraction.

        Args:
            user_input: User input text
            context: Context dictionary
            allowed_intents: List of allowed intents

        Returns:
            Formatted prompt
        """
        prompt = f"""You are an intent classifier for a collections voice bot.

User said: "{user_input}"

Current context:
- State: {context.get('current_state', 'unknown')}
- Flow: {context.get('flow_type', 'unknown')}

Allowed intents for this state:
{json.dumps(allowed_intents, indent=2)}

Extract the user's intent and any relevant information (slots).

Respond ONLY with valid JSON in this exact format:
{{
  "intent": "<one of the allowed intents>",
  "confidence": <0.0 to 1.0>,
  "slots": {{
    "<slot_name>": "<slot_value>"
  }}
}}

Examples:

User: "Yes, my name is Rajesh Kumar"
{{"intent": "confirm_identity", "confidence": 0.9, "slots": {{"name": "Rajesh Kumar"}}}}

User: "I can pay 5000 rupees tomorrow"
{{"intent": "promise_to_pay", "confidence": 0.95, "slots": {{"amount": "5000", "date": "tomorrow"}}}}

User: "I already paid this"
{{"intent": "dispute_paid", "confidence": 0.9, "slots": {{}}}}

User: "I lost my job, I can't pay now"
{{"intent": "hardship", "confidence": 0.85, "slots": {{"reason": "job loss"}}}}

User: "Let me talk to a person"
{{"intent": "request_human", "confidence": 1.0, "slots": {{}}}}

Now extract intent from the user input above:
"""
        return prompt

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response from LLM.

        Args:
            response_text: Raw LLM response

        Returns:
            Parsed dictionary
        """
        try:
            # Try to find JSON in response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                logger.warning("No JSON found in LLM response")
                return {"intent": "unknown", "confidence": 0.0, "slots": {}}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return {"intent": "unknown", "confidence": 0.0, "slots": {}}

    def is_high_confidence(self, confidence: float) -> bool:
        """
        Check if confidence is above threshold.

        Args:
            confidence: Confidence score

        Returns:
            True if confidence is acceptable
        """
        return confidence >= INTENT_CONFIDENCE_THRESHOLD


# Intent definitions for different states
INTENT_DEFINITIONS = {
    "greeting": [
        "confirm_identity",
        "deny_identity",
        "request_human",
        "hang_up",
    ],
    "identity_verify": [
        "confirm_identity",
        "deny_identity",
        "provide_details",
        "request_human",
    ],
    "disclosure": [
        "acknowledge",
        "refuse_recording",
        "request_human",
    ],
    "purpose_explain": [
        "acknowledge",
        "dispute_debt",
        "already_paid",
        "request_details",
        "request_human",
    ],
    "payment_discussion": [
        "promise_to_pay",
        "request_time",
        "dispute_amount",
        "hardship",
        "partial_payment",
        "request_human",
    ],
    "ptp_capture": [
        "confirm_date",
        "confirm_amount",
        "change_date",
        "change_amount",
        "cannot_commit",
        "request_human",
    ],
    "closing": [
        "confirm",
        "question",
        "complaint",
        "request_human",
    ],
}


# Global NLU instance
_nlu_engine = None


def get_nlu_engine() -> NLUEngine:
    """Get global NLU engine instance."""
    global _nlu_engine
    if _nlu_engine is None:
        _nlu_engine = NLUEngine()
    return _nlu_engine


def extract_intent(
    user_input: str,
    context: Dict[str, Any],
    allowed_intents: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Convenience function for intent extraction.

    Args:
        user_input: User's text
        context: Context dictionary
        allowed_intents: List of allowed intents (or use context.current_state)

    Returns:
        Intent extraction result
    """
    engine = get_nlu_engine()

    if allowed_intents is None:
        current_state = context.get("current_state", "greeting")
        allowed_intents = INTENT_DEFINITIONS.get(current_state, ["unknown", "request_human"])

    return engine.extract_intent(user_input, context, allowed_intents)
