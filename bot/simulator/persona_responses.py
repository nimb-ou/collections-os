"""
Persona Response Engine - LLM-driven customer responses for simulation

Uses Ollama to generate realistic customer responses conditioned on:
- Persona type (cooperative, evasive, disputing, hardship, strategic)
- Conversation context
- Account situation (overdue amount, DPD, etc.)
"""

import json
import logging
from typing import Dict, Optional
import requests

from .personas import CustomerPersona, PersonaType

logger = logging.getLogger(__name__)


class PersonaResponseEngine:
    """
    Generates customer responses using LLM conditioned on persona characteristics
    """

    # Response templates for each persona type
    PERSONA_INSTRUCTIONS = {
        PersonaType.COOPERATIVE: """You are a cooperative customer who:
- Acknowledges the debt
- Is willing to work with the collector
- Makes realistic promises
- Speaks calmly and politely
- May ask for slight flexibility on dates/amounts""",

        PersonaType.EVASIVE: """You are an evasive customer who:
- Avoids direct answers
- Makes vague promises ("soon", "next week")
- Claims to be busy or traveling
- Deflects with excuses
- Speaks in a slightly anxious tone""",

        PersonaType.DISPUTING: """You are a disputing customer who:
- Claims you already paid
- Disputes the amount owed
- Demands proof of the debt
- Speaks defensively or angrily
- May threaten to escalate""",

        PersonaType.HARDSHIP: """You are a customer facing genuine hardship who:
- Explains financial difficulties (job loss, medical emergency, etc.)
- Wants to pay but genuinely cannot afford full amount
- May request time or reduced amount
- Speaks apologetically but with genuine concern
- Open to partial payment if possible""",

        PersonaType.STRATEGIC: """You are a strategic customer who:
- Knows your rights as a borrower
- Asks to speak to a supervisor immediately
- Questions the legality of the call
- Demands written communication
- Speaks calmly but assertively
- May mention recording the call or filing complaints""",
    }

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b-instruct-q4_K_M",
        temperature: float = 0.7,  # Higher than NLU for variety
    ):
        """
        Initialize persona response engine

        Args:
            ollama_url: Ollama API endpoint
            model: Model to use for response generation
            temperature: Sampling temperature (higher = more variety)
        """
        self.ollama_url = ollama_url
        self.model = model
        self.temperature = temperature

    def generate_response(
        self,
        persona: CustomerPersona,
        bot_prompt: str,
        conversation_history: list,
        context: Optional[Dict] = None,
    ) -> str:
        """
        Generate a customer response based on persona and bot prompt

        Args:
            persona: CustomerPersona with behavioral characteristics
            bot_prompt: What the bot just said
            conversation_history: List of (speaker, message) tuples
            context: Additional context (account info, etc.)

        Returns:
            Customer's response as string
        """
        # Build system prompt based on persona
        system_prompt = self._build_system_prompt(persona, context or {})

        # Build conversation context
        conv_context = self._build_conversation_context(
            bot_prompt, conversation_history
        )

        # Generate response via Ollama
        try:
            response = self._call_ollama(system_prompt, conv_context)
            return response
        except Exception as e:
            logger.error(f"Failed to generate persona response: {e}")
            # Fallback to simple response
            return self._fallback_response(persona, bot_prompt)

    def _build_system_prompt(
        self,
        persona: CustomerPersona,
        context: Dict,
    ) -> str:
        """Build system prompt with persona instructions"""
        base_instruction = self.PERSONA_INSTRUCTIONS[persona.persona_type]

        system_prompt = f"""{base_instruction}

**Your situation:**
- Name: {persona.customer_name}
- Overdue amount: ₹{persona.overdue_amt:,.0f}
- Days overdue: {persona.dpd} days
- Financial stress level: {'High' if persona.has_genuine_hardship else 'Moderate'}
- Cooperation tendency: {persona.cooperation_level:.1%}

**Response guidelines:**
- Keep responses natural and conversational (1-3 sentences)
- {'Be brief and to the point' if not persona.verbose else 'You tend to give longer explanations'}
- Tone: {persona.emotional_tone}
- Language: {'Mix Hindi and English (Hinglish)' if persona.language == 'hi' else 'English'}
- {'You genuinely cannot pay the full amount right now' if persona.has_genuine_hardship else ''}
- {'You believe you already paid this' if persona.has_paid_already else ''}
- {'You know your rights and prefer escalation' if persona.knows_rights else ''}

Respond as this customer would. Do not break character. Do not use quotation marks.
"""
        return system_prompt

    def _build_conversation_context(
        self,
        bot_prompt: str,
        conversation_history: list,
    ) -> str:
        """Build conversation context string"""
        context_lines = []

        # Add recent history (last 3 turns)
        for speaker, message in conversation_history[-3:]:
            context_lines.append(f"{speaker}: {message}")

        # Add current bot prompt
        context_lines.append(f"Bot: {bot_prompt}")
        context_lines.append("\nYour response:")

        return "\n".join(context_lines)

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama API to generate response"""
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "temperature": self.temperature,
            "stream": False,
            "options": {
                "num_predict": 100,  # Limit response length
                "stop": ["\n\n", "Bot:", "Customer:"],
            }
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        generated_text = result.get('response', '').strip()

        return generated_text

    def _fallback_response(
        self,
        persona: CustomerPersona,
        bot_prompt: str,
    ) -> str:
        """Fallback responses when LLM fails"""
        fallbacks = {
            PersonaType.COOPERATIVE: [
                "Yes, I understand. I can try to arrange the payment.",
                "I will pay. Can you give me a few days?",
                "Okay, let me check my account and pay by tomorrow.",
            ],
            PersonaType.EVASIVE: [
                "I am very busy right now. I will call back later.",
                "I need to check with my accountant. Give me some time.",
                "I am traveling. I will handle this next week.",
            ],
            PersonaType.DISPUTING: [
                "I already paid this! Check your records.",
                "This amount is wrong. I don't owe this much.",
                "I want to speak to your manager about this.",
            ],
            PersonaType.HARDSHIP: [
                "I lost my job last month. I cannot pay the full amount right now.",
                "I have medical expenses. Can I pay a smaller amount?",
                "I want to pay but I am facing financial problems.",
            ],
            PersonaType.STRATEGIC: [
                "I want all communication in writing only.",
                "Transfer me to your supervisor immediately.",
                "I know my rights. I will file a complaint if you harass me.",
            ],
        }

        import random
        options = fallbacks.get(persona.persona_type, ["I understand."])
        return random.choice(options)

    def should_answer_call(self, persona: CustomerPersona) -> bool:
        """Determine if customer answers the call based on persona"""
        import random
        return random.random() < persona.answer_probability

    def should_make_ptp(
        self,
        persona: CustomerPersona,
        bot_asked_for_ptp: bool,
    ) -> bool:
        """Determine if customer makes a promise to pay"""
        if not bot_asked_for_ptp:
            return False

        import random
        return random.random() < persona.ptp_likelihood

    def generate_ptp(
        self,
        persona: CustomerPersona,
    ) -> Optional[Dict]:
        """
        Generate PTP details based on persona

        Returns:
            Dict with ptp_date (days from now), ptp_amount, ptp_mode
            or None if no PTP
        """
        import random

        if not self.should_make_ptp(persona, bot_asked_for_ptp=True):
            return None

        # Generate PTP date (1-7 days from now)
        if persona.persona_type == PersonaType.COOPERATIVE:
            days_out = random.choice([1, 2, 3])
        elif persona.persona_type == PersonaType.EVASIVE:
            days_out = random.choice([5, 6, 7])
        elif persona.persona_type == PersonaType.HARDSHIP:
            days_out = random.choice([7, 10, 15])
        else:
            days_out = random.choice([3, 5, 7])

        # Generate PTP amount (may be partial)
        if persona.has_genuine_hardship:
            # Offer 30-60% of overdue
            ptp_amount = persona.overdue_amt * random.uniform(0.3, 0.6)
        elif persona.persona_type == PersonaType.COOPERATIVE:
            # Full amount usually
            ptp_amount = persona.overdue_amt
        else:
            # Partial promise
            ptp_amount = persona.overdue_amt * random.uniform(0.5, 0.9)

        ptp_mode = random.choice(['UPI', 'NACH', 'Bank Transfer'])

        return {
            'days_from_now': days_out,
            'amount': round(ptp_amount, 2),
            'mode': ptp_mode,
        }
