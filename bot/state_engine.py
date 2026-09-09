"""
Conversation State Engine
Finite-state dialog manager with compliance guardrails
"""

import logging
import yaml
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    FLOWS_DIR,
    MAX_TURNS,
    MAX_COLLECTION_ASKS,
    MAX_PTP_WINDOW_DAYS,
    RECORDING_DISCLOSURE_REQUIRED,
    PROHIBITED_PHRASES,
    DISPOSITIONS,
)
from nlu import extract_intent, INTENT_DEFINITIONS
from tts import get_prompt_bank

logger = logging.getLogger(__name__)


class ConversationState:
    """
    Manages conversation state and history.
    """

    def __init__(self, session_id: str, account_id: str, flow_type: str):
        """
        Initialize conversation state.

        Args:
            session_id: Unique session identifier
            account_id: Account ID being called
            flow_type: Flow type (pre_due_reminder, post_bounce_ptp, etc.)
        """
        self.session_id = session_id
        self.account_id = account_id
        self.flow_type = flow_type
        self.current_state = "start"
        self.turn_count = 0
        self.collection_ask_count = 0
        self.low_asr_count = 0
        self.started_at = datetime.now()

        # Conversation history
        self.history = []

        # Collected information
        self.slots = {}

        # Flags
        self.recording_disclosed = False
        self.identity_verified = False
        self.escalate_to_human = False
        self.call_ended = False

        # Disposition
        self.disposition = None
        self.disposition_reason = None

    def add_turn(self, speaker: str, text: str, intent: Optional[str] = None):
        """
        Add a turn to conversation history.

        Args:
            speaker: 'bot' or 'user'
            text: Spoken text
            intent: User intent (if speaker is user)
        """
        self.history.append({
            "turn": self.turn_count,
            "speaker": speaker,
            "text": text,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })

        if speaker == "user":
            self.turn_count += 1

    def get_context(self) -> Dict[str, Any]:
        """Get conversation context for NLU."""
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "flow_type": self.flow_type,
            "current_state": self.current_state,
            "turn_count": self.turn_count,
            "slots": self.slots,
            "recording_disclosed": self.recording_disclosed,
            "identity_verified": self.identity_verified,
        }

    def should_escalate(self) -> bool:
        """Check if conversation should be escalated to human."""
        return (
            self.escalate_to_human or
            self.turn_count >= MAX_TURNS or
            self.low_asr_count >= 2
        )


class StateEngine:
    """
    Finite-state dialog engine.
    Coordinates conversation flow based on YAML flow definitions.
    """

    def __init__(self, flow_type: str):
        """
        Initialize state engine.

        Args:
            flow_type: Flow type to load
        """
        self.flow_type = flow_type
        self.flow_definition = None
        self.load_flow()
        self.prompt_bank = get_prompt_bank()

    def load_flow(self):
        """Load flow definition from YAML file."""
        flow_file = FLOWS_DIR / f"{self.flow_type}.yaml"

        if not flow_file.exists():
            raise FileNotFoundError(f"Flow definition not found: {flow_file}")

        try:
            with open(flow_file, "r", encoding="utf-8") as f:
                self.flow_definition = yaml.safe_load(f)

            logger.info(f"✓ Loaded flow definition: {self.flow_type}")

        except Exception as e:
            logger.error(f"Failed to load flow: {e}")
            raise

    def process_turn(
        self,
        state: ConversationState,
        user_input: str,
        asr_confidence: float,
    ) -> Tuple[str, bool]:
        """
        Process one conversation turn.

        Args:
            state: Current conversation state
            user_input: User's transcribed speech
            asr_confidence: ASR confidence score

        Returns:
            Tuple of (bot_response, should_continue)
        """
        # Check low ASR confidence
        if asr_confidence < 0.5:
            state.low_asr_count += 1
            if state.low_asr_count >= 2:
                state.escalate_to_human = True
                state.disposition = "ESCALATE_HUMAN"
                state.disposition_reason = "Low ASR confidence"
                return "I'm having trouble hearing you. Let me connect you to someone who can help.", False

        # Extract intent
        allowed_intents = INTENT_DEFINITIONS.get(state.current_state, ["unknown", "request_human"])
        intent_result = extract_intent(user_input, state.get_context(), allowed_intents)

        intent = intent_result["intent"]
        confidence = intent_result["confidence"]
        slots = intent_result.get("slots", {})

        # Add turn to history
        state.add_turn("user", user_input, intent)

        # Update slots
        state.slots.update(slots)

        # Handle special intents
        if intent == "request_human":
            state.escalate_to_human = True
            state.disposition = "CALLBACK_REQUEST"
            return "I'll connect you with one of our representatives. Please hold.", False

        if intent == "hang_up":
            state.call_ended = True
            state.disposition = "CONNECT_RPC"
            return "Thank you for your time. Goodbye.", False

        # Get current state definition
        current_state_def = self.flow_definition["states"].get(state.current_state)

        if not current_state_def:
            logger.error(f"State not found in flow: {state.current_state}")
            state.disposition = "TECHNICAL_ERROR"
            return "I'm experiencing a technical issue. Goodbye.", False

        # Find matching transition
        next_state, response_template = self._find_transition(current_state_def, intent)

        # Check compliance guardrails
        if not self._check_compliance(state, next_state, response_template):
            state.escalate_to_human = True
            state.disposition = "ESCALATE_HUMAN"
            state.disposition_reason = "Compliance violation"
            return "Let me transfer you to a representative.", False

        # Generate response
        bot_response = self._generate_response(response_template, state.slots)

        # Update state
        state.current_state = next_state
        state.add_turn("bot", bot_response)

        # Check if we're at end state
        if next_state == "end":
            state.call_ended = True
            if not state.disposition:
                state.disposition = "CONNECT_RPC"

        # Check if should continue
        should_continue = not (state.call_ended or state.should_escalate())

        return bot_response, should_continue

    def _find_transition(
        self,
        state_def: Dict[str, Any],
        intent: str,
    ) -> Tuple[str, str]:
        """
        Find matching state transition for intent.

        Args:
            state_def: State definition from flow
            intent: User intent

        Returns:
            Tuple of (next_state, response_template)
        """
        transitions = state_def.get("transitions", [])

        for transition in transitions:
            if transition["intent"] == intent:
                return transition["next_state"], transition["response"]

        # Default transition
        default = state_def.get("default_transition", {})
        return default.get("next_state", "end"), default.get("response", "I didn't understand. Goodbye.")

    def _generate_response(self, template: str, slots: Dict[str, str]) -> str:
        """
        Generate bot response from template.

        Args:
            template: Response template with {slot} placeholders
            slots: Slot values

        Returns:
            Filled template
        """
        try:
            return template.format(**slots)
        except KeyError as e:
            logger.warning(f"Missing slot in template: {e}")
            return template

    def _check_compliance(
        self,
        state: ConversationState,
        next_state: str,
        response: str,
    ) -> bool:
        """
        Check compliance guardrails.

        Args:
            state: Conversation state
            next_state: Next state
            response: Bot response

        Returns:
            True if compliant
        """
        # Check recording disclosure
        if RECORDING_DISCLOSURE_REQUIRED and not state.recording_disclosed:
            if next_state not in ["disclosure", "end"]:
                logger.warning("Recording not disclosed yet")
                return False

        # Check collection ask limit
        if "payment" in next_state.lower() or "collect" in response.lower():
            state.collection_ask_count += 1
            if state.collection_ask_count > MAX_COLLECTION_ASKS:
                logger.warning(f"Exceeded max collection asks ({MAX_COLLECTION_ASKS})")
                return False

        # Check prohibited phrases
        response_lower = response.lower()
        for phrase in PROHIBITED_PHRASES:
            if phrase in response_lower:
                logger.error(f"Prohibited phrase detected: '{phrase}'")
                return False

        return True

    def get_initial_response(self, account_info: Dict[str, Any]) -> str:
        """
        Get initial greeting for conversation.

        Args:
            account_info: Account information

        Returns:
            Initial bot response
        """
        initial_state_def = self.flow_definition["states"].get("start")
        if not initial_state_def:
            return "Hello, this is a call from the collections team."

        template = initial_state_def.get("entry_prompt", "Hello.")
        return self._generate_response(template, account_info)


def create_session(
    session_id: str,
    account_id: str,
    flow_type: str,
) -> Tuple[ConversationState, StateEngine]:
    """
    Create new conversation session.

    Args:
        session_id: Unique session ID
        account_id: Account ID
        flow_type: Flow type

    Returns:
        Tuple of (state, engine)
    """
    state = ConversationState(session_id, account_id, flow_type)
    engine = StateEngine(flow_type)

    logger.info(f"Created session {session_id} for account {account_id} (flow: {flow_type})")

    return state, engine
