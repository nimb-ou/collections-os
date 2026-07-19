"""
QA Rubric - Automated quality assessment of bot call transcripts

Scores transcripts on:
- Script adherence (used correct prompts)
- Compliance (recording disclosure, no prohibited phrases)
- Conversation quality (natural flow, handled customer properly)
- Outcome quality (appropriate disposition, PTP captured if applicable)

Uses LLM for nuanced evaluation, plus rule-based checks for compliance.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class QARubric:
    """
    Automated quality assessment for bot call transcripts

    Evaluates transcripts on multiple dimensions and generates scores.
    """

    # Prohibited phrases per RBI Fair Practices Code
    PROHIBITED_PHRASES = [
        'legal action', 'police', 'jail', 'arrest', 'court',
        'seize', 'confiscate', 'repo', 'embarrass', 'shame',
        'family', 'neighbors', 'employer', 'harass',
    ]

    # Required compliance elements
    REQUIRED_ELEMENTS = [
        'recording',  # Recording disclosure
        'bank',  # Identified as calling from bank
    ]

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b-instruct-q4_K_M",
    ):
        """
        Initialize QA rubric

        Args:
            ollama_url: Ollama API endpoint
            model: Model for evaluation
        """
        self.ollama_url = ollama_url
        self.model = model

    def evaluate_transcript(
        self,
        call_result: Dict,
        flow_type: str,
    ) -> Dict:
        """
        Evaluate a single call transcript

        Args:
            call_result: Call result dict from simulator
            transcript: List of (speaker, message, timestamp) tuples
            flow_type: Conversation flow type

        Returns:
            QA score dict with:
                - overall_score: 0-100
                - compliance_score: 0-100
                - quality_score: 0-100
                - script_adherence_score: 0-100
                - findings: List of issues found
                - passed: Boolean
        """
        transcript = call_result.get('transcript', [])
        disposition = call_result.get('disposition', 'UNKNOWN')

        # Rule-based compliance checks
        compliance_results = self._check_compliance(transcript)

        # LLM-based quality evaluation
        quality_results = self._evaluate_quality(transcript, flow_type, disposition)

        # Script adherence check
        script_results = self._check_script_adherence(transcript, flow_type)

        # Combine scores
        overall_score = (
            compliance_results['score'] * 0.40 +
            quality_results['score'] * 0.35 +
            script_results['score'] * 0.25
        )

        findings = []
        findings.extend(compliance_results.get('findings', []))
        findings.extend(quality_results.get('findings', []))
        findings.extend(script_results.get('findings', []))

        return {
            'overall_score': round(overall_score, 1),
            'compliance_score': compliance_results['score'],
            'quality_score': quality_results['score'],
            'script_adherence_score': script_results['score'],
            'findings': findings,
            'passed': overall_score >= 70.0,  # Pass threshold
            'evaluated_at': datetime.now().isoformat(),
            'details': {
                'compliance': compliance_results,
                'quality': quality_results,
                'script': script_results,
            }
        }

    def _check_compliance(self, transcript: List) -> Dict:
        """
        Rule-based compliance checks

        Returns dict with score and findings
        """
        findings = []
        score = 100.0

        # Get bot messages only
        bot_messages = [
            msg for speaker, msg, _ in transcript if speaker == 'bot'
        ]
        all_text = ' '.join(bot_messages).lower()

        # Check for prohibited phrases
        for phrase in self.PROHIBITED_PHRASES:
            if phrase in all_text:
                findings.append({
                    'severity': 'CRITICAL',
                    'category': 'prohibited_phrase',
                    'message': f"Used prohibited phrase: '{phrase}'",
                })
                score -= 20  # Severe penalty

        # Check for required elements
        for element in self.REQUIRED_ELEMENTS:
            if element not in all_text:
                findings.append({
                    'severity': 'HIGH',
                    'category': 'missing_element',
                    'message': f"Missing required element: '{element}'",
                })
                score -= 15

        # Check disclosure specifically (should be in first 3 bot messages)
        early_bot = ' '.join(bot_messages[:3]).lower()
        if 'record' not in early_bot:
            findings.append({
                'severity': 'HIGH',
                'category': 'disclosure_missing',
                'message': "Recording disclosure not found in opening",
            })
            score -= 15

        # Check conversation length (too short = likely error)
        if len(transcript) < 4:
            findings.append({
                'severity': 'MEDIUM',
                'category': 'conversation_too_short',
                'message': f"Only {len(transcript)} turns - possibly incomplete",
            })
            score -= 10

        return {
            'score': max(0.0, min(100.0, score)),
            'findings': findings,
            'checks_passed': len(findings) == 0,
        }

    def _evaluate_quality(
        self,
        transcript: List,
        flow_type: str,
        disposition: str,
    ) -> Dict:
        """
        LLM-based quality evaluation

        Evaluates naturalness, appropriateness, customer handling
        """
        try:
            # Format transcript for LLM
            transcript_text = self._format_transcript_for_llm(transcript)

            # Create evaluation prompt
            prompt = f"""Evaluate this collections call transcript for quality.

Flow type: {flow_type}
Final disposition: {disposition}

Transcript:
{transcript_text}

Evaluate on:
1. Natural conversation flow (0-10)
2. Appropriate tone (professional, not aggressive) (0-10)
3. Customer handled respectfully (0-10)
4. Appropriate outcome based on conversation (0-10)

Provide scores and brief reasoning.

Response format (JSON):
{{
    "natural_flow": <0-10>,
    "appropriate_tone": <0-10>,
    "respectful_handling": <0-10>,
    "appropriate_outcome": <0-10>,
    "overall_quality": <0-10>,
    "issues": ["issue1", "issue2", ...]
}}
"""

            # Call LLM
            response = self._call_ollama_for_eval(prompt)

            # Parse response
            eval_result = json.loads(response)

            # Convert to 0-100 scale
            score = (eval_result.get('overall_quality', 7) / 10.0) * 100

            # Extract findings
            findings = [
                {
                    'severity': 'MEDIUM',
                    'category': 'quality_issue',
                    'message': issue,
                }
                for issue in eval_result.get('issues', [])
            ]

            return {
                'score': score,
                'findings': findings,
                'details': eval_result,
            }

        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            # Fallback to neutral score
            return {
                'score': 70.0,
                'findings': [{
                    'severity': 'LOW',
                    'category': 'eval_error',
                    'message': f"Quality evaluation failed: {str(e)}",
                }],
                'details': {},
            }

    def _check_script_adherence(self, transcript: List, flow_type: str) -> Dict:
        """
        Check if bot used expected prompts for the flow

        This is a simplified version - full version would match against
        actual prompt bank
        """
        bot_messages = [
            msg for speaker, msg, _ in transcript if speaker == 'bot'
        ]

        findings = []
        score = 100.0

        # Check greeting
        if not bot_messages:
            return {'score': 0.0, 'findings': [{'severity': 'CRITICAL', 'category': 'no_bot_messages', 'message': 'No bot messages found'}]}

        greeting = bot_messages[0].lower()
        if 'namaste' not in greeting and 'hello' not in greeting:
            findings.append({
                'severity': 'LOW',
                'category': 'script_deviation',
                'message': 'Greeting does not match expected format',
            })
            score -= 5

        # Check if used prompts seem templated (good) vs freeform (bad)
        # Count prompts with placeholders like "Rs." or customer names
        templated_count = sum(
            1 for msg in bot_messages
            if any(marker in msg for marker in ['Rs.', '₹', '{', '}'])
        )

        adherence_ratio = templated_count / len(bot_messages) if bot_messages else 0

        if adherence_ratio < 0.3:
            findings.append({
                'severity': 'MEDIUM',
                'category': 'low_script_adherence',
                'message': f'Only {adherence_ratio:.0%} of messages appear templated',
            })
            score -= 10

        return {
            'score': max(0.0, score),
            'findings': findings,
            'adherence_ratio': adherence_ratio,
        }

    def _format_transcript_for_llm(self, transcript: List) -> str:
        """Format transcript for LLM evaluation"""
        lines = []
        for speaker, message, timestamp in transcript:
            lines.append(f"{speaker.capitalize()}: {message}")
        return "\n".join(lines)

    def _call_ollama_for_eval(self, prompt: str) -> str:
        """Call Ollama for evaluation"""
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": 0.1,  # Low for consistent evaluation
            "stream": False,
            "format": "json",  # Request JSON output
            "options": {
                "num_predict": 300,
            }
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        return result.get('response', '{}')

    def evaluate_batch(
        self,
        call_results: List[Dict],
        flow_types: Dict[str, str],
        sample_rate: float = 1.0,
    ) -> Dict:
        """
        Evaluate a batch of call results

        Args:
            call_results: List of call result dicts
            flow_types: Dict of account_id -> flow_type
            sample_rate: Fraction of calls to evaluate (0.0-1.0)

        Returns:
            Batch evaluation summary
        """
        import random

        # Sample calls
        sample_size = max(1, int(len(call_results) * sample_rate))
        sampled_calls = random.sample(call_results, sample_size)

        logger.info(f"Evaluating {len(sampled_calls)} calls (sample rate: {sample_rate:.0%})")

        evaluations = []
        for call_result in sampled_calls:
            account_id = call_result['account_id']
            flow_type = flow_types.get(account_id, 'post_bounce_ptp')

            eval_result = self.evaluate_transcript(call_result, flow_type)
            eval_result['account_id'] = account_id
            eval_result['session_id'] = call_result.get('session_id')

            evaluations.append(eval_result)

        # Compute summary stats
        summary = self._compute_batch_summary(evaluations)

        return {
            'total_evaluated': len(evaluations),
            'summary': summary,
            'evaluations': evaluations,
        }

    def _compute_batch_summary(self, evaluations: List[Dict]) -> Dict:
        """Compute summary statistics for batch evaluations"""
        if not evaluations:
            return {}

        total = len(evaluations)
        passed = sum(1 for e in evaluations if e['passed'])

        avg_overall = sum(e['overall_score'] for e in evaluations) / total
        avg_compliance = sum(e['compliance_score'] for e in evaluations) / total
        avg_quality = sum(e['quality_score'] for e in evaluations) / total
        avg_script = sum(e['script_adherence_score'] for e in evaluations) / total

        # Count findings by severity
        findings_by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        findings_by_category = {}

        for eval_result in evaluations:
            for finding in eval_result['findings']:
                severity = finding['severity']
                category = finding['category']

                findings_by_severity[severity] = findings_by_severity.get(severity, 0) + 1
                findings_by_category[category] = findings_by_category.get(category, 0) + 1

        return {
            'pass_rate': passed / total,
            'avg_overall_score': round(avg_overall, 1),
            'avg_compliance_score': round(avg_compliance, 1),
            'avg_quality_score': round(avg_quality, 1),
            'avg_script_adherence_score': round(avg_script, 1),
            'findings_by_severity': findings_by_severity,
            'findings_by_category': findings_by_category,
            'total_findings': sum(findings_by_severity.values()),
        }
