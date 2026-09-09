"""
Call Simulator - Coordinates bot-persona conversations

Simulates a complete call flow:
1. Place call to customer (answer probability check)
2. Run conversation using bot's state engine
3. Generate persona responses via LLM
4. Capture disposition and PTP
5. Record transcript
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from ..state_engine import create_session, ConversationState, StateEngine
from ..nlu import extract_intent
from .personas import CustomerPersona
from .persona_responses import PersonaResponseEngine

logger = logging.getLogger(__name__)


class CallSimulator:
    """
    Simulates a call between the bot and a synthetic customer persona
    """

    MAX_TURNS = 20  # Max conversation turns
    TURN_TIMEOUT_SECONDS = 30  # Max time per turn

    def __init__(
        self,
        response_engine: Optional[PersonaResponseEngine] = None,
    ):
        """
        Initialize call simulator

        Args:
            response_engine: Persona response engine (creates if None)
        """
        self.response_engine = response_engine or PersonaResponseEngine()

    def simulate_call(
        self,
        persona: CustomerPersona,
        flow_type: str,
        context: Optional[Dict] = None,
    ) -> Dict:
        """
        Simulate a complete call

        Args:
            persona: Customer persona to simulate
            flow_type: Conversation flow (post_bounce_ptp, pre_due_reminder, etc.)
            context: Additional context (product_type, emi_amt, etc.)

        Returns:
            Call result dict with:
                - disposition: Final call outcome
                - ptp: PTP details if captured
                - transcript: List of (speaker, message, timestamp) tuples
                - duration_seconds: Call duration
                - turn_count: Number of turns
                - metadata: Additional metrics
        """
        session_id = str(uuid.uuid4())
        start_time = datetime.now()

        # Check if customer answers
        if not self.response_engine.should_answer_call(persona):
            return self._create_no_answer_result(persona, start_time)

        # Create bot session
        state, engine = create_session(
            session_id=session_id,
            account_id=persona.account_id,
            flow_type=flow_type,
        )

        # Prepare context
        call_context = context or {}
        call_context.update({
            'customer_name': persona.customer_name,
            'product_type': call_context.get('product_type', 'Auto Loan'),
            'overdue_amt': persona.overdue_amt,
            'emi_amount': call_context.get('emi_amt', persona.overdue_amt),
        })

        # Start conversation
        transcript = []
        turn_count = 0
        disposition = 'UNKNOWN'
        ptp_details = None

        # Bot's initial greeting
        bot_message = engine.get_initial_response(call_context)
        transcript.append(('bot', bot_message, datetime.now()))

        conversation_history = []
        should_continue = True

        while should_continue and turn_count < self.MAX_TURNS:
            turn_count += 1

            # Persona responds
            customer_response = self.response_engine.generate_response(
                persona=persona,
                bot_prompt=bot_message,
                conversation_history=conversation_history,
                context=call_context,
            )

            if not customer_response:
                # Customer hung up or silent
                disposition = 'CUSTOMER_HUNG_UP'
                break

            transcript.append(('customer', customer_response, datetime.now()))
            conversation_history.append(('Bot', bot_message))
            conversation_history.append(('Customer', customer_response))

            # Simulate response delay
            time.sleep(0.1)  # Small delay for realism in logs

            # Bot processes customer response
            try:
                bot_message, should_continue = engine.process_turn(
                    state=state,
                    user_input=customer_response,
                    asr_confidence=0.9,  # Simulated high confidence
                )

                transcript.append(('bot', bot_message, datetime.now()))

                # Check for special conditions
                if not should_continue:
                    disposition = state.disposition
                    break

                # Check if bot is asking for PTP
                if self._is_ptp_request(state.current_state, bot_message):
                    ptp_details = self._handle_ptp_negotiation(
                        persona, engine, state, transcript, conversation_history
                    )
                    if ptp_details:
                        disposition = 'PTP'
                        should_continue = False
                        break

            except Exception as e:
                logger.error(f"Error in bot turn processing: {e}")
                disposition = 'TECHNICAL_ERROR'
                break

        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Get final disposition if not set
        if disposition == 'UNKNOWN':
            disposition = state.disposition or 'COMPLETED'

        return {
            'session_id': session_id,
            'account_id': persona.account_id,
            'disposition': disposition,
            'ptp': ptp_details,
            'transcript': transcript,
            'duration_seconds': duration,
            'turn_count': turn_count,
            'metadata': {
                'persona_type': persona.persona_type.value,
                'archetype': persona.archetype,
                'cooperation_level': persona.cooperation_level,
                'flow_type': flow_type,
                'completed': should_continue == False,
                'max_turns_reached': turn_count >= self.MAX_TURNS,
            }
        }

    def _create_no_answer_result(
        self,
        persona: CustomerPersona,
        start_time: datetime,
    ) -> Dict:
        """Create result for unanswered call"""
        return {
            'session_id': str(uuid.uuid4()),
            'account_id': persona.account_id,
            'disposition': 'NO_ANSWER',
            'ptp': None,
            'transcript': [],
            'duration_seconds': 0.0,
            'turn_count': 0,
            'metadata': {
                'persona_type': persona.persona_type.value,
                'archetype': persona.archetype,
                'cooperation_level': persona.cooperation_level,
                'answered': False,
            }
        }

    def _is_ptp_request(self, current_state: str, bot_message: str) -> bool:
        """Check if bot is requesting a PTP"""
        ptp_keywords = ['when can you pay', 'promise to pay', 'payment date',
                       'kab pay kar', 'payment ka']
        message_lower = bot_message.lower()
        return (
            'ptp' in current_state.lower() or
            any(kw in message_lower for kw in ptp_keywords)
        )

    def _handle_ptp_negotiation(
        self,
        persona: CustomerPersona,
        engine: StateEngine,
        state: ConversationState,
        transcript: List,
        conversation_history: List,
    ) -> Optional[Dict]:
        """
        Handle PTP negotiation turns

        Returns PTP details if agreed, None otherwise
        """
        # Check if persona will make PTP
        ptp_offer = self.response_engine.generate_ptp(persona)

        if not ptp_offer:
            # Customer declines PTP
            decline_msg = self._generate_decline_message(persona)
            transcript.append(('customer', decline_msg, datetime.now()))
            return None

        # Customer makes PTP
        ptp_date = datetime.now() + timedelta(days=ptp_offer['days_from_now'])
        ptp_msg = f"I can pay ₹{ptp_offer['amount']:,.0f} on {ptp_date.strftime('%B %d')}"

        transcript.append(('customer', ptp_msg, datetime.now()))
        conversation_history.append(('Customer', ptp_msg))

        # Bot confirms PTP
        confirm_msg = engine.process_turn(
            state=state,
            user_input=ptp_msg,
            asr_confidence=0.9,
        )[0]

        transcript.append(('bot', confirm_msg, datetime.now()))

        # Return PTP details
        return {
            'ptp_date': ptp_date.isoformat(),
            'ptp_amount': ptp_offer['amount'],
            'ptp_mode': ptp_offer['mode'],
            'made_at': datetime.now().isoformat(),
            'channel': 'bot',
            'status': 'open',
        }

    def _generate_decline_message(self, persona: CustomerPersona) -> str:
        """Generate a PTP decline message based on persona"""
        from .personas import PersonaType

        declines = {
            PersonaType.COOPERATIVE: "I need more time. Can we discuss next week?",
            PersonaType.EVASIVE: "I cannot commit right now. I will call back.",
            PersonaType.DISPUTING: "I am not paying anything until you fix your records.",
            PersonaType.HARDSHIP: "I cannot afford to pay anything right now. I need help.",
            PersonaType.STRATEGIC: "I want this in writing. Send me an email.",
        }

        return declines.get(persona.persona_type, "I cannot commit right now.")

    def simulate_batch(
        self,
        personas: Dict[str, CustomerPersona],
        flow_types: Dict[str, str],
        contexts: Optional[Dict[str, Dict]] = None,
        max_concurrent: int = 10,
    ) -> List[Dict]:
        """
        Simulate multiple calls (sequential for now, concurrent in future)

        Args:
            personas: Dict of account_id -> CustomerPersona
            flow_types: Dict of account_id -> flow_type
            contexts: Optional dict of account_id -> context
            max_concurrent: Max concurrent calls (for future parallelization)

        Returns:
            List of call results
        """
        results = []
        contexts = contexts or {}

        for account_id, persona in personas.items():
            flow_type = flow_types.get(account_id, 'post_bounce_ptp')
            context = contexts.get(account_id, {})

            logger.info(f"Simulating call for {account_id}")

            try:
                result = self.simulate_call(persona, flow_type, context)
                results.append(result)
            except Exception as e:
                logger.error(f"Error simulating call for {account_id}: {e}")
                # Create error result
                results.append({
                    'session_id': str(uuid.uuid4()),
                    'account_id': account_id,
                    'disposition': 'ERROR',
                    'ptp': None,
                    'transcript': [],
                    'duration_seconds': 0.0,
                    'turn_count': 0,
                    'metadata': {'error': str(e)},
                })

        return results
