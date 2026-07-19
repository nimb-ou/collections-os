"""
Customer Persona Generator - Creates realistic customer personas for bot testing

Personas are calibrated to behavioral archetypes from synthgen:
- PRIME: Cooperative, likely to pay, answers calls
- SPORADIC: Sometimes cooperative, moderate payment likelihood
- STRESSED: Hardship cases, may dispute or avoid
- CHRONIC: Evasive, broken promises, low answer rate
- STRATEGIC: Intelligent avoiders, knows their rights
"""

import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class PersonaType(Enum):
    """Persona behavioral types"""
    COOPERATIVE = "cooperative"  # Willing to work with collector
    EVASIVE = "evasive"  # Avoids commitment, vague promises
    DISPUTING = "disputing"  # Claims already paid or disputes amount
    HARDSHIP = "hardship"  # Financial difficulty, genuine issues
    STRATEGIC = "strategic"  # Knows rights, demands escalation


@dataclass
class CustomerPersona:
    """Represents a synthetic customer persona for simulation"""
    account_id: str
    customer_name: str
    archetype: str  # PRIME, SPORADIC, STRESSED, CHRONIC, STRATEGIC
    persona_type: PersonaType
    language: str
    overdue_amt: float
    dpd: int

    # Behavioral parameters
    answer_probability: float  # P(picks up call)
    cooperation_level: float  # 0-1, affects response quality
    ptp_likelihood: float  # P(makes a promise to pay)
    ptp_keep_probability: float  # P(keeps the promise)

    # Response characteristics
    response_delay_seconds: float  # Simulated thinking time
    verbose: bool  # Long-winded vs brief responses
    emotional_tone: str  # calm, anxious, angry, apologetic

    # Context
    has_genuine_hardship: bool
    has_paid_already: bool  # Will claim payment
    knows_rights: bool  # Will ask for escalation/supervisor

    def __repr__(self):
        return (f"CustomerPersona({self.account_id}, {self.archetype}, "
                f"{self.persona_type.value}, coop={self.cooperation_level:.2f})")


class PersonaGenerator:
    """
    Generates customer personas based on account data and archetypes

    Maps behavioral archetypes to persona types and calibrates probabilities
    to match realistic collection scenarios.
    """

    # Archetype → PersonaType mapping probabilities
    ARCHETYPE_PERSONA_DIST = {
        'PRIME': {
            PersonaType.COOPERATIVE: 0.85,
            PersonaType.HARDSHIP: 0.10,
            PersonaType.DISPUTING: 0.05,
            PersonaType.EVASIVE: 0.00,
            PersonaType.STRATEGIC: 0.00,
        },
        'SPORADIC': {
            PersonaType.COOPERATIVE: 0.50,
            PersonaType.EVASIVE: 0.30,
            PersonaType.HARDSHIP: 0.15,
            PersonaType.DISPUTING: 0.05,
            PersonaType.STRATEGIC: 0.00,
        },
        'STRESSED': {
            PersonaType.HARDSHIP: 0.60,
            PersonaType.COOPERATIVE: 0.20,
            PersonaType.EVASIVE: 0.15,
            PersonaType.DISPUTING: 0.05,
            PersonaType.STRATEGIC: 0.00,
        },
        'CHRONIC': {
            PersonaType.EVASIVE: 0.60,
            PersonaType.DISPUTING: 0.25,
            PersonaType.HARDSHIP: 0.10,
            PersonaType.COOPERATIVE: 0.05,
            PersonaType.STRATEGIC: 0.00,
        },
        'STRATEGIC': {
            PersonaType.STRATEGIC: 0.70,
            PersonaType.EVASIVE: 0.20,
            PersonaType.DISPUTING: 0.10,
            PersonaType.COOPERATIVE: 0.00,
            PersonaType.HARDSHIP: 0.00,
        },
    }

    # Persona type → behavioral parameters
    PERSONA_PARAMS = {
        PersonaType.COOPERATIVE: {
            'answer_prob': 0.75,
            'cooperation': (0.7, 0.95),
            'ptp_likelihood': 0.80,
            'ptp_keep_prob': 0.75,
            'tone': ['calm', 'apologetic'],
            'verbose': False,
        },
        PersonaType.EVASIVE: {
            'answer_prob': 0.35,
            'cooperation': (0.2, 0.5),
            'ptp_likelihood': 0.50,
            'ptp_keep_prob': 0.30,
            'tone': ['anxious', 'evasive'],
            'verbose': True,
        },
        PersonaType.DISPUTING: {
            'answer_prob': 0.55,
            'cooperation': (0.1, 0.4),
            'ptp_likelihood': 0.20,
            'ptp_keep_prob': 0.40,
            'tone': ['angry', 'defensive'],
            'verbose': True,
        },
        PersonaType.HARDSHIP: {
            'answer_prob': 0.60,
            'cooperation': (0.5, 0.8),
            'ptp_likelihood': 0.40,
            'ptp_keep_prob': 0.50,
            'tone': ['anxious', 'apologetic'],
            'verbose': True,
        },
        PersonaType.STRATEGIC: {
            'answer_prob': 0.40,
            'cooperation': (0.3, 0.6),
            'ptp_likelihood': 0.10,
            'ptp_keep_prob': 0.20,
            'tone': ['calm', 'assertive'],
            'verbose': False,
        },
    }

    def __init__(self, seed: Optional[int] = None):
        """Initialize persona generator with optional seed for reproducibility"""
        self.random = random.Random(seed)

    def generate_persona(
        self,
        account_id: str,
        customer_name: str,
        archetype: str,
        language: str,
        overdue_amt: float,
        dpd: int,
    ) -> CustomerPersona:
        """
        Generate a customer persona for a given account

        Args:
            account_id: Account identifier
            customer_name: Customer name
            archetype: Behavioral archetype (PRIME, SPORADIC, etc.)
            language: Preferred language (hi, en, etc.)
            overdue_amt: Overdue amount in rupees
            dpd: Days past due

        Returns:
            CustomerPersona with calibrated behavioral parameters
        """
        # Select persona type based on archetype
        persona_type = self._select_persona_type(archetype)

        # Get base parameters for this persona type
        params = self.PERSONA_PARAMS[persona_type]

        # Generate behavioral parameters
        answer_prob = params['answer_prob']
        cooperation = self.random.uniform(*params['cooperation'])
        ptp_likelihood = params['ptp_likelihood']
        ptp_keep_prob = params['ptp_keep_prob']

        # Adjust for DPD (higher DPD → lower cooperation, lower answer rate)
        dpd_factor = max(0.5, 1.0 - (dpd / 120.0))  # Decay cooperation
        answer_prob *= dpd_factor
        cooperation *= dpd_factor

        # Response characteristics
        response_delay = self.random.uniform(0.5, 2.5)
        verbose = params['verbose']
        tone = self.random.choice(params['tone'])

        # Context flags
        has_hardship = (persona_type == PersonaType.HARDSHIP or
                       (archetype == 'STRESSED' and self.random.random() < 0.3))
        has_paid = (persona_type == PersonaType.DISPUTING and
                   self.random.random() < 0.4)
        knows_rights = persona_type == PersonaType.STRATEGIC

        return CustomerPersona(
            account_id=account_id,
            customer_name=customer_name,
            archetype=archetype,
            persona_type=persona_type,
            language=language,
            overdue_amt=overdue_amt,
            dpd=dpd,
            answer_probability=min(0.95, answer_prob),
            cooperation_level=cooperation,
            ptp_likelihood=ptp_likelihood,
            ptp_keep_probability=ptp_keep_prob,
            response_delay_seconds=response_delay,
            verbose=verbose,
            emotional_tone=tone,
            has_genuine_hardship=has_hardship,
            has_paid_already=has_paid,
            knows_rights=knows_rights,
        )

    def _select_persona_type(self, archetype: str) -> PersonaType:
        """Select persona type based on archetype distribution"""
        if archetype not in self.ARCHETYPE_PERSONA_DIST:
            # Default for unknown archetypes
            return PersonaType.COOPERATIVE

        dist = self.ARCHETYPE_PERSONA_DIST[archetype]
        r = self.random.random()
        cumulative = 0.0

        for persona_type, prob in dist.items():
            cumulative += prob
            if r < cumulative:
                return persona_type

        # Fallback
        return PersonaType.COOPERATIVE

    def generate_batch_personas(
        self,
        accounts: List[Dict]
    ) -> Dict[str, CustomerPersona]:
        """
        Generate personas for a batch of accounts

        Args:
            accounts: List of account dicts with keys:
                     account_id, customer_name, archetype, language,
                     overdue_amt, dpd

        Returns:
            Dict mapping account_id to CustomerPersona
        """
        personas = {}
        for account in accounts:
            persona = self.generate_persona(
                account_id=account['account_id'],
                customer_name=account['customer_name'],
                archetype=account.get('archetype', 'PRIME'),
                language=account.get('language', 'en'),
                overdue_amt=account.get('overdue_amt', 0.0),
                dpd=account.get('dpd', 0),
            )
            personas[account['account_id']] = persona

        return personas
