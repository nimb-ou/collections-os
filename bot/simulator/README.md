## Call Simulator - Bot Testing at Volume

Synthetic customer personas + LLM-driven conversations for bot performance testing without real calls.

### Overview

The call simulator enables end-to-end testing of the AI voice bot at volume by:

1. **Generating realistic customer personas** based on behavioral archetypes
2. **Running simulated conversations** between bot and personas
3. **Logging dispositions, PTPs, and transcripts** to database
4. **Automated QA evaluation** of call quality and compliance

This allows the system to:
- Test bot flows with 1000s of calls
- Generate realistic data for dashboards and analytics
- Identify bot performance issues before production
- Prove the system end-to-end on a Mac without real telephony

### Architecture

```
┌────────────────┐
│  Call Queue    │
│  (database)    │
└───────┬────────┘
        │
        ▼
┌────────────────────────────────────────┐
│      Batch Call Processor              │
│  - Fetch queue items                   │
│  - Generate personas for customers     │
│  - Run simulations                     │
└───────┬────────────────────────────────┘
        │
        ▼
┌────────────────┐        ┌──────────────────┐
│ Persona        │        │   Call           │
│ Generator      │───────▶│   Simulator      │
│ (archetypes)   │        │   (bot + LLM)    │
└────────────────┘        └────────┬─────────┘
                                   │
        ┌──────────────────────────┼─────────────────────┐
        │                          │                     │
        ▼                          ▼                     ▼
┌──────────────┐        ┌────────────────┐   ┌──────────────────┐
│ Disposition  │        │  PTP Records   │   │   Transcripts    │
│   Logging    │        │   (fct_ptp)    │   │   (fct_calls)    │
└──────────────┘        └────────────────┘   └──────────────────┘
                                   │
                                   ▼
                        ┌────────────────────┐
                        │   QA Rubric        │
                        │   (compliance +    │
                        │    quality eval)   │
                        └────────────────────┘
```

### Components

#### 1. Persona Generator (`personas.py`)

Creates synthetic customer personas based on behavioral archetypes from synthgen.

**Persona Types:**
- **COOPERATIVE**: Willing to pay, makes realistic promises (75% answer rate, 80% PTP likelihood)
- **EVASIVE**: Avoids commitment, vague promises (35% answer rate, 50% PTP likelihood)
- **DISPUTING**: Claims already paid, disputes amount (55% answer rate, 20% PTP likelihood)
- **HARDSHIP**: Genuine financial difficulty (60% answer rate, 40% PTP likelihood)
- **STRATEGIC**: Knows rights, demands escalation (40% answer rate, 10% PTP likelihood)

**Archetype Mapping:**
- `PRIME` → 85% Cooperative, 10% Hardship, 5% Disputing
- `SPORADIC` → 50% Cooperative, 30% Evasive, 15% Hardship, 5% Disputing
- `STRESSED` → 60% Hardship, 20% Cooperative, 15% Evasive, 5% Disputing
- `CHRONIC` → 60% Evasive, 25% Disputing, 10% Hardship, 5% Cooperative
- `STRATEGIC` → 70% Strategic, 20% Evasive, 10% Disputing

#### 2. Persona Response Engine (`persona_responses.py`)

LLM-driven response generation conditioned on persona characteristics.

**Features:**
- Uses Ollama Qwen 2.5 7B for realistic customer responses
- Conditioned on: persona type, cooperation level, emotional tone, hardship status
- Supports Hinglish and English
- Generates appropriate PTP offers based on persona
- Calibrated answer probabilities

**Example Response Conditioning:**
```
COOPERATIVE persona (calm, cooperative=0.85):
→ "Yes, I understand. I can try to arrange the payment by tomorrow."

EVASIVE persona (anxious, cooperative=0.30):
→ "I am traveling right now. I will call back next week."

DISPUTING persona (angry, cooperation=0.20):
→ "I already paid this! Check your records properly."
```

#### 3. Call Simulator (`simulator.py`)

Orchestrates complete conversations between bot and persona.

**Flow:**
1. Check if customer answers (based on `answer_probability`)
2. Bot starts conversation with greeting
3. Loop:
   - Persona generates response via LLM
   - Bot processes response via state engine
   - Check for PTP negotiation
   - Continue until disposition reached
4. Log transcript, disposition, PTP

**Limits:**
- Max 20 turns per call
- 30s timeout per turn
- Automatic escalation on errors

#### 4. Batch Call Processor (`batch_processor.py`)

Processes entire call queue from database.

**Features:**
- Fetches calls from `call_queue` table
- Loads account and customer data
- Generates personas for each account
- Runs simulations (sequential for now, parallel-ready)
- Writes results to database:
  - `fct_calls`: Call records with transcripts
  - `fct_ptp`: Promise-to-pay records
  - `dispositions`: Disposition codes
  - Updates `call_queue` status to 'completed'

#### 5. QA Rubric (`qa_rubric.py`)

Automated quality assessment of call transcripts.

**Evaluation Dimensions:**

**Compliance (40% weight):**
- Recording disclosure present in opening
- No prohibited phrases (legal action, police, jail, harassment, etc.)
- Conversation length (not too short)

**Quality (35% weight):**
- Natural conversation flow (LLM-evaluated)
- Appropriate professional tone
- Respectful customer handling
- Appropriate outcome

**Script Adherence (25% weight):**
- Proper greeting
- Use of templated prompts
- Expected flow followed

**Scoring:**
- Overall score 0-100
- Pass threshold: 70+
- Findings categorized by severity (CRITICAL, HIGH, MEDIUM, LOW)

### Usage

#### Run Simulator on Today's Queue

```bash
# Process all bot calls in queue
python -m bot.simulator

# Limit to 100 calls
python -m bot.simulator --limit 100

# Target specific date
python -m bot.simulator --date 2026-07-19 --limit 50

# Dry run (no database writes)
python -m bot.simulator --limit 10 --dry-run

# Custom QA sampling (default 2%)
python -m bot.simulator --qa-sample 0.10
```

#### Programmatic Usage

```python
from bot.simulator import (
    PersonaGenerator,
    PersonaResponseEngine,
    CallSimulator,
    BatchCallProcessor,
    QARubric,
)

# Generate a persona
persona_gen = PersonaGenerator(seed=42)
persona = persona_gen.generate_persona(
    account_id='ACC001',
    customer_name='Rajesh Kumar',
    archetype='SPORADIC',
    language='hi',
    overdue_amt=8500.0,
    dpd=15,
)

# Run a single call
response_engine = PersonaResponseEngine()
simulator = CallSimulator(response_engine=response_engine)

result = simulator.simulate_call(
    persona=persona,
    flow_type='post_bounce_ptp',
    context={'product_type': 'Auto Loan', 'emi_amt': 8500},
)

print(f"Disposition: {result['disposition']}")
print(f"PTP: {result['ptp']}")
print(f"Transcript: {result['transcript']}")

# Evaluate quality
qa = QARubric()
qa_result = qa.evaluate_transcript(result, 'post_bounce_ptp')
print(f"QA Score: {qa_result['overall_score']}")
print(f"Passed: {qa_result['passed']}")
```

#### Process Full Day's Queue

```python
from bot.simulator import BatchCallProcessor

processor = BatchCallProcessor()

# Process today's bot queue
result = processor.process_queue(
    channel='bot',
    limit=None,  # All calls
    dry_run=False,
)

print(f"Processed: {result['processed']} calls")
print(f"PTPs Made: {result['ptps_made']}")
print(f"Dispositions: {result['dispositions']}")
```

### Integration with Daily Pipeline

Add to `Makefile`:

```makefile
simulate:
    @echo "Running bot simulator..."
    python -m bot.simulator --limit 1000

simulate-full:
    @echo "Running full day simulation..."
    python -m bot.simulator
```

Add to Dagster pipeline (future):

```python
@asset
def simulated_bot_calls(context, daily_queue):
    """Run bot simulator on today's queue"""
    from bot.simulator import BatchCallProcessor

    processor = BatchCallProcessor()
    result = processor.process_queue(channel='bot')

    context.log.info(f"Simulated {result['processed']} calls")
    return result
```

### Database Schema

**Input (call_queue):**
```sql
SELECT
    account_id,
    channel,
    priority,
    scheduled_slot,
    campaign_id,
    status
FROM call_queue
WHERE channel = 'bot' AND status = 'queued'
```

**Outputs:**

**fct_calls:**
```sql
INSERT INTO fct_calls (
    account_id,
    call_date,
    call_time,
    channel,
    call_outcome,
    disposition,
    duration_seconds,
    transcript
)
```

**fct_ptp:**
```sql
INSERT INTO fct_ptp (
    account_id,
    made_by,
    channel,
    promise_date,
    promised_amount,
    promise_mode,
    status
)
```

**dispositions:**
```sql
INSERT INTO dispositions (
    account_id,
    disposition_code,
    agent_id,
    channel,
    notes
)
```

### Performance

**Benchmarks (M4 Mac):**
- Persona generation: ~1ms per persona
- Call simulation: ~2-5s per call (depends on turn count)
- 100 calls: ~5 minutes
- 1000 calls: ~45 minutes

**Scalability:**
- Parallelization ready (set `max_concurrent` in future)
- LLM is bottleneck (Ollama serves 1 call at a time)
- With concurrent Ollama instances: 10+ calls/second possible

### Disposition Distribution

Expected disposition breakdown (1000 simulated calls):

```
NO_ANSWER: ~45%          (answer probability < 1.0)
PTP: ~20%                (answered + made PTP)
COMPLETED: ~25%          (answered but no PTP)
CUSTOMER_HUNG_UP: ~5%    (mid-conversation exit)
TECHNICAL_ERROR: ~2%     (bot failures)
ESCALATION: ~3%          (strategic personas)
```

### QA Statistics

Expected QA results (2% sample of 1000 calls = 20 evaluated):

```
Pass Rate: ~85%
Avg Overall Score: ~78
Avg Compliance Score: ~90
Avg Quality Score: ~75
Avg Script Adherence: ~70

Common Findings:
- Low script adherence (personas trigger unexpected flows)
- Quality issues with evasive personas
- Rare compliance violations (should be 0 with proper bot)
```

### Reports

Reports are saved to `bot/simulator/reports/`:

```json
{
  "run_timestamp": "2026-07-19T10:30:00",
  "parameters": {
    "limit": 100,
    "target_date": "2026-07-19",
    "channel": "bot",
    "qa_sample_rate": 0.02
  },
  "results": {
    "total_calls": 100,
    "processed": 100,
    "dispositions": {
      "NO_ANSWER": 42,
      "PTP": 23,
      "COMPLETED": 28,
      "CUSTOMER_HUNG_UP": 5,
      "TECHNICAL_ERROR": 2
    },
    "ptps_made": 23,
    "total_duration_seconds": 1250.5,
    "avg_duration_seconds": 12.5
  }
}
```

### Testing

Run simulator with small limit to test:

```bash
# Test with 10 calls
python -m bot.simulator --limit 10 --dry-run

# Check generated report
cat bot/simulator/reports/sim_report_*.json
```

### Troubleshooting

**Issue: "Ollama connection refused"**
- Solution: Start Ollama service: `brew services start ollama`

**Issue: "No calls in queue"**
- Solution: Ensure call queue is populated (run campaign builder or `make daily`)

**Issue: "Database connection failed"**
- Solution: Check PostgreSQL is running: `docker ps`

**Issue: "LLM responses too slow"**
- Solution: Reduce `--limit` or ensure Ollama model is loaded (`ollama run qwen2.5:7b-instruct-q4_K_M`)

### Dependencies

- `psycopg2-binary`: PostgreSQL connection
- `requests`: Ollama API calls
- `../state_engine`: Bot conversation engine
- `../nlu`: Intent extraction (used by bot)

All dependencies are already installed from Session 11 (bot core).

### Future Enhancements

1. **Parallel simulation**: Run multiple calls concurrently with asyncio
2. **Real-time QA**: Evaluate during simulation instead of post-hoc
3. **Advanced personas**: Load from database, not just archetypes
4. **Voice synthesis**: Add actual audio generation (optional)
5. **A/B testing**: Compare different bot flows or prompts
6. **Persona learning**: Improve persona responses based on real call data

### Architecture Decisions

**Why LLM for customer responses?**
- Realistic variety in responses
- Natural language understanding by bot gets tested properly
- Cheaper than hiring humans for testing
- Repeatable and scalable

**Why local LLM (Ollama)?**
- No API costs
- No data leaving machine
- Consistent with bot's local-first architecture

**Why 2% QA sampling?**
- Full evaluation is expensive (LLM calls)
- 2% provides statistically significant sample
- Critical issues found even in small samples
- Can increase to 10-20% for detailed analysis

### License

Part of CollectOS, built as open-source collections operating system.
