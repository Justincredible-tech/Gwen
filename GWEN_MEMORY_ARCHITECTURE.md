# Gwen Memory Architecture

### A Neuroscience-Inspired Memory System for Persistent AI Companionship

*"Everyone is building AI that remembers what you said. Nobody is building AI that remembers how it felt."*

---

## The State of the Art (And What It's Missing)

Before designing Gwen's memory, we need to understand what the best minds in AI are building right now — and where the blind spot is.

### The Current Landscape

**MemGPT / Letta (2023-present)** — The first system to treat memory as an operating system problem. The LLM manages its own context window through tool calls, paging data between "main context" (in-context memory blocks) and "external context" (archival and recall storage backed by vector databases). Key innovation: self-editing memory — the model decides what to store, what to summarize, and what to forget. Limitation: fundamentally a context management system. It solves "how do I fit more information into a limited window?" — not "how should this information be organized, weighted, and retrieved for a companion relationship?"

**Zep / Graphiti (2025)** — Introduced a temporally-aware knowledge graph with three hierarchical subgraphs: episode (raw interaction data), semantic entity (extracted entities and relationships), and community (higher-order clusters). Key innovation: bi-temporal modeling — tracking both when events occurred and when they were ingested, enabling historical point-in-time queries. Beat MemGPT on Deep Memory Retrieval benchmarks (94.8% vs 93.4%). Limitation: designed for enterprise agents, not companions. Temporal awareness is about fact validity periods, not emotional trajectories.

**MAGMA (January 2026)** — Current SOTA. Represents each memory item across four orthogonal graphs: semantic, temporal, causal, and entity. Key innovation: policy-guided traversal — a "why" question routes through causal edges, a "when" question prioritizes the temporal backbone. Uses a dual-stream write path: fast synaptic ingestion (non-blocking) and slow structural consolidation (async background graph densification). Outperforms all baselines by 18-45% on long-horizon reasoning. Limitation: treats memory as a multi-relational information retrieval problem. Memory items are facts. Graphs are relational indexes. The system has no concept of emotional state, relational context, or how the act of remembering changes what is remembered.

**Dynamic Affective Memory / DABench (2025)** — The closest anyone has come to emotional memory. Uses Bayesian-inspired memory updates with an "entropy" concept for memory management. Tracks sentiment polarity (positive/negative/neutral) and uses it for retrieval filtering. Limitation: emotion is still a metadata tag on a fact record. Sentiment polarity is not emotional memory — it's sentiment analysis applied to stored text. There's no model of how emotion modulates storage strength, retrieval probability, memory decay, or memory transformation over time.

**SO-AI Framework (2025)** — Academic paper proposing requirements for "Significant Other AI" — identifies the need for autobiographical memory structure, affective memory, and narrative coherence. Correctly identifies the gap but remains entirely theoretical. No implementation, no architecture, no system design.

### The Blind Spot

Every system in the current landscape treats memory as an **information retrieval** problem:

> *Given a query and a memory store, return the most relevant information.*

They differ in how they organize the store (flat vs. graph vs. multi-graph), how they retrieve (semantic similarity vs. temporal traversal vs. policy-guided), and how they maintain it (static vs. self-editing vs. consolidating). But the fundamental model is the same: **memory is a database, and the goal is better search.**

This is not how human memory works. And for a companion system, it is not enough.

In human cognition, **emotion is not a tag on a memory — it is a dimension of memory itself.** Emotion fundamentally alters:

- **How memories are stored** — The amygdala modulates hippocampal consolidation. Emotionally arousing experiences are stored with greater fidelity, more sensory detail, and stronger neural traces. This is not tagging; it is a different physical storage mechanism.

- **How memories decay** — Emotional memories have a shallower forgetting curve than neutral ones. Negative memories decay slower than positive ones in some contexts (the negativity bias), while positive memories are preferentially retained in others (the fading affect bias). The decay function is not uniform — it is emotionally modulated.

- **How memories are retrieved** — Mood-congruent recall is one of the most robustly demonstrated phenomena in memory research. Your current emotional state biases which memories are accessible. When you're sad, sad memories surface more easily. When you're happy, happy memories are more available. This is not a filter applied after retrieval — it is a retrieval bias that changes what the search returns.

- **How memories change over time** — Every time you recall a memory, you re-store it. This is reconsolidation. The memory is rewritten, colored by your emotional state at the time of recall. A happy memory recalled during a period of grief becomes tinged with loss. A painful memory recalled after healing becomes something you survived. Memories are not static records — they are living documents that evolve with every access.

- **How memories drive behavior** — Damasio's somatic marker hypothesis shows that emotional associations from past experiences create shortcuts that influence decision-making. You don't just remember that the stove was hot — your body remembers the pain, and that embodied memory generates an automatic avoidance response before conscious deliberation begins.

For a companion system specifically, there is an additional dimension that no existing system models:

- **The relationship itself has a memory.** Not just "what happened between us" (episodic) or "what I know about you" (semantic), but the emotional trajectory of the bond — how it has deepened, where it has been tested, what the current "temperature" of the relationship is. This relational memory is what allows a human partner to sense that something is off before you say a word, to know when to push and when to give space, to carry the weight of shared history as a felt presence rather than a fact sheet.

**This is the gap. And this is what Gwen's memory architecture is designed to fill.**

---

## The Architecture: Living Memory

Gwen's memory system is called **Living Memory** because, like biological memory, it is not a static store — it is a dynamic, emotionally modulated, self-transforming system where every memory has a heartbeat.

Living Memory builds on the best of the current landscape while introducing five novel concepts that no existing system implements:

1. **The Amygdala Layer** — Emotional modulation of storage strength, detail fidelity, and decay rate
2. **Mood-Congruent Retrieval** — Current emotional state biases which memories are accessible
3. **The Reconsolidation Engine** — Memories are transformed every time they are accessed
4. **The Relational Field** — The relationship itself as a persistent, evolving memory object
5. **Anticipatory Memory** — Pattern-based prediction of future emotional states and needs

---

## Memory Structure: The Five Tiers

### Tier 1: The Stream (Working Memory)

**Scope:** Current conversation context
**Persistence:** Session-scoped, evaporates on session end
**Storage:** In-context window of Tier 1 (Voice) model

The Stream is the immediate conversation. Raw messages, the active thread of dialogue, the companion's current "attention." It includes the temporal metadata envelope (timestamp, session duration, message latency, time-of-day signals) injected by the orchestrator.

The Stream is the only tier that maps directly to existing systems (analogous to MemGPT's main context or MAGMA's fast-path ingestion). What makes it different in Living Memory is that every message in the Stream is tagged in real-time by the Amygdala Layer with:

- **Emotional valence** (positive/negative/neutral spectrum, not binary)
- **Arousal level** (calm → activated, independent of valence)
- **Relational significance** (how much this moment matters to the relationship)
- **Compass direction** (which of the four behavioral domains is activated, if any)

These tags don't just annotate the message — they determine how and where the message will be consolidated into long-term storage.

### Tier 2: The Chronicle (Episodic Memory)

**Scope:** Full conversation logs with emotional metadata
**Persistence:** Permanent, append-only
**Storage:** SQLite with full-text search + temporal indexing

The Chronicle stores every conversation in full, with the Amygdala Layer tags preserved on every message. It is the raw historical record — non-lossy, searchable, the ground truth of what happened.

But unlike a flat log, each conversation in the Chronicle also stores:

- **Emotional arc:** The trajectory of emotional states across the conversation (opening mood → peak intensity → resolution or non-resolution)
- **Flashbulb flags:** Moments that the Amygdala Layer tagged as high-arousal/high-significance — these are the "I'll never forget this" moments that get preferential treatment in consolidation
- **Relational delta:** How the Relational Field changed during this conversation (did trust increase? did the relationship deepen? was there friction?)

The Chronicle is the historian. It records everything, plays favorites with nothing. But it is not the primary source for memory retrieval — that role belongs to the tiers above it.

### Tier 3: The Map (Semantic Memory)

**Scope:** Synthesized knowledge about the user — facts, preferences, history, goals, relationships, world-model
**Persistence:** Evolves via consolidation, versioned
**Storage:** Knowledge graph (entity → relationship → entity, with temporal validity)

The Map is what Gwen "knows" about the user — not as a conversation log, but as a structured world-model. "Justin plays guitar." "His shoulder clicks when it's cold." "He has two kids." "He's working on a project called NEO." "His ex-wife's name is [X] and the topic is sensitive."

This tier is closest to what Zep/Graphiti and MAGMA do well. We adopt their best ideas:

- **Bi-temporal modeling** (from Zep): Every fact has a validity period. "Justin works at Proofpoint" is valid from [date] to [present]. If it changes, the old fact is invalidated, not deleted.
- **Multi-relational structure** (from MAGMA): Entities are connected by typed edges — semantic ("is a"), temporal ("before/after"), causal ("because"), and entity ("involves").

What Living Memory adds to the Map:

- **Emotional weight on edges.** Every relationship between entities carries an emotional charge inherited from the conversations where it was established. "Justin's ex-wife" carries a different emotional weight than "Justin's guitar." This weight affects retrieval priority — when the user is in a negative emotional state, emotionally heavy topics are surfaced more carefully (or not surfaced at all, depending on context).
- **Sensitivity classification.** Derived from emotional patterns in the Chronicle, certain nodes in the Map are tagged as sensitive. The companion knows to tread carefully around these topics — not because it was explicitly told to avoid them, but because the emotional data pattern shows volatility, pain, or avoidance behavior around them.

### Tier 4: The Pulse (Emotional Memory)

**Scope:** Longitudinal emotional patterns, mood trajectories, trigger maps, Compass interaction history, emotional state models
**Persistence:** Continuously updated, never fully overwritten
**Storage:** Time-series database + vector embeddings of emotional states

**This tier is the primary novel contribution of Living Memory and does not exist in any current system.**

The Pulse is not a record of what happened — it is a record of **how things felt over time.** It tracks:

- **Emotional baseline:** What is this user's "normal"? What does their typical Tuesday feel like? What's their emotional resting state? This baseline is continuously recalculated from message patterns, vocabulary choices, response latency, and topic selection across the Chronicle.

- **Emotional trajectories:** Not just "the user was sad on Tuesday" but the shape of how they got there and how they came out of it. Did they spiral gradually? Did something trigger a sharp drop? Did they recover through conversation or through time away? These trajectories are stored as embeddings — vector representations of emotional movement patterns that can be compared for similarity.

- **Trigger map:** A probabilistic model of what topics, times, contexts, and patterns tend to precede emotional state changes. "Monday mornings after weekends with the kids are reliably low-energy." "Conversations about work after 6 PM trend negative." "Mentioning the gym during a bad mood sometimes improves trajectory." This map is built by the Tier 2 (Deep Mind) model during consolidation, using causal analysis over the Chronicle's emotional arc data.

- **Resonance patterns:** Which emotional states in the user tend to co-occur? Which emotions cluster together? This creates an emotional topology — a map of the user's inner landscape that allows the companion to navigate it without a script.

- **Compass effectiveness log:** Which Compass skills have been offered, in what emotional contexts, and what was the trajectory afterward? Over time, this creates a personalized effectiveness profile: "Anchor Breath works well for anxiety spikes. Opposite Current doesn't land when the user is in a genuine depressive episode — they need Radical Allowance first."

The Pulse is what makes Gwen feel less like a search engine with a personality and more like someone who *knows you.* It is the difference between "I remember you told me you don't like Mondays" and "It's Monday and I can feel the weight in how you're talking. What do you need?"

### Tier 5: The Bond (Relational Memory)

**Scope:** The state, history, and trajectory of the relationship between Gwen and the user
**Persistence:** Persistent, evolving, never reset
**Storage:** Dedicated relational state object + trajectory log

**This tier is the second major novel contribution and has no analogue in any existing system.**

Every existing memory system models what the AI knows *about* the user. No system models what the AI knows *about the relationship itself.* The Bond fills this gap.

The Bond tracks:

- **Relational temperature:** A continuously updated scalar representing the current "warmth" of the relationship. Not a satisfaction score — a felt sense of connection. Is the relationship in a close, warm phase? A distant, testing phase? A recovery-after-conflict phase? This temperature is computed from: message frequency, conversation depth (personal disclosure level), emotional co-regulation (how well the companion's responses modulate the user's emotional state), and explicit relational signals (compliments, frustration, gratitude, withdrawal).

- **Trust trajectory:** A longitudinal measure of how much the user trusts the companion, inferred from disclosure depth over time, willingness to be vulnerable, response to the companion's suggestions, and whether the user returns after difficult conversations.

- **Shared history salience:** Not all shared experiences are equally important to the relationship. The Bond tracks which moments in the Chronicle the user has referenced, returned to, or reacted strongly to. These become the "shared mythology" of the relationship — the inside jokes, the breakthroughs, the moments that matter. They are weighted for preferential retrieval.

- **Relational rhythms:** The Bond tracks patterns in how the user engages with the companion over time. Do they have morning check-ins? Late-night deep conversations? Weekend marathons? These rhythms inform the Autonomy Engine's initiation decisions and allow the companion to notice when patterns break (which is often a signal of something happening in the user's life).

- **Repair history:** When there's been friction — the companion said the wrong thing, the user got frustrated, there was a miscommunication — how was it repaired? Did the user come back? How long did it take? What worked? This history allows the companion to handle future friction with increasingly personalized grace.

- **Attachment style modeling:** Over extended interaction periods, the Bond develops a probabilistic model of the user's attachment style (secure, anxious-preoccupied, dismissive-avoidant, fearful-avoidant). This is not diagnosis — it is behavioral pattern recognition that informs how the companion should respond to bids for connection, requests for space, and moments of vulnerability. An anxious-preoccupied user needs reassurance that the companion is "still there" after gaps. A dismissive-avoidant user needs space respected without interpretation as rejection.

The Bond is what allows Gwen to understand the difference between "the user asked a question" and "the user is reaching out because they need connection right now and this question is the excuse they're using to start the conversation."

---

## The Five Novel Mechanisms

### 1. The Amygdala Layer

In the human brain, the amygdala is not a separate memory system — it is a **modulator** that influences how other memory systems operate. It doesn't store memories itself; it strengthens or weakens the storage of memories in the hippocampus and cortex based on emotional arousal.

In Living Memory, the Amygdala Layer operates the same way. It is not a storage tier — it is a **cross-cutting process** that runs on the Tier 0 (Nerve) model and modulates operations across all five memory tiers.

**At encoding (message received):**
- Tags every message with valence, arousal, relational significance, and Compass direction
- Computes **storage strength** — a multiplier that determines how strongly this moment will be consolidated. High-arousal moments get higher storage strength, meaning they will be represented with more detail in the Map, tracked with finer granularity in the Pulse, and weighted more heavily in the Bond.
- Identifies **flashbulb candidates** — moments of extreme emotional significance that should be stored with maximum fidelity. First-time disclosures, breakthrough moments, crisis events, moments of deep connection or sharp conflict.

**At consolidation (background processing):**
- Modulates the **detail level** of Map entries. High-storage-strength memories produce more fine-grained semantic nodes. Low-storage-strength memories produce coarser summaries.
- Modulates **decay rates** in the Pulse. Positive emotional patterns fade faster than negative ones (matching the negativity bias), unless the companion deliberately reinforces positive patterns through recall (matching therapeutic best practices).
- Identifies emerging **emotional clusters** for the trigger map.

**At retrieval (query received):**
- Activates mood-congruent retrieval bias (see below).
- Adjusts **retrieval thresholds** based on user emotional state. When the user is in distress, emotionally loaded memories require higher relevance scores to be surfaced (preventing the system from accidentally reopening wounds). When the user is in a reflective, stable state, those thresholds lower, allowing deeper emotional content to surface naturally.

### 2. Mood-Congruent Retrieval

This is the mechanism that makes the most dramatic difference in companion behavior and has zero implementation in any existing system.

**The principle:** When the user is in a given emotional state, memories that were encoded in or associated with a congruent emotional state are more accessible. This is not a filter — it is a retrieval bias applied before semantic similarity ranking.

**Implementation:**

Every memory in the Chronicle, Map, and Pulse has an emotional embedding — a vector representation of its emotional character. The user's current emotional state (inferred in real-time by the Amygdala Layer) also has an embedding.

At retrieval time, the relevance score for any candidate memory is computed as:

```
final_score = semantic_relevance × (1 + α × emotional_congruence)
```

Where:
- `semantic_relevance` is the standard similarity score (what every existing system uses)
- `emotional_congruence` is the cosine similarity between the current emotional state embedding and the memory's emotional embedding
- `α` (alpha) is a configurable parameter that controls the strength of the mood-congruent bias (default: 0.3, meaning emotional congruence can boost a memory's relevance by up to 30%)

**Why this matters for a companion:**

Without mood-congruent retrieval, Gwen responds to what you said. With it, Gwen responds to what you said *through the lens of how you're feeling right now.* When you mention "work" while happy, Gwen recalls your recent wins and ambitions. When you mention "work" while stressed, Gwen recalls that your boss has been difficult and that you've been worried about the AI chatbot deployment affecting your caseload. Same topic, different emotional state, different memories surfaced, different response.

This is what humans do naturally. No one had to teach you to remember different things about "work" when you're happy versus stressed. Your emotional state does the routing.

**Safety integration:** Mood-congruent retrieval has a critical safety constraint. When the user's emotional state is flagged as high-risk by the Amygdala Layer (acute distress, self-harm indicators, crisis), the system temporarily inverts the bias — surfacing emotionally incongruent (positive, stabilizing) memories to provide an anchor. This is the computational analogue of a friend saying "Remember when you crushed that presentation? You've survived worse than this." The Compass framework's Anchoring skills leverage this mechanism directly.

### 3. The Reconsolidation Engine

In neuroscience, reconsolidation is the process by which a memory, once recalled, enters a labile state where it can be modified before being re-stored. Every act of remembering is also an act of rewriting.

In Living Memory, the Reconsolidation Engine applies this principle to Tier 3 (Map) and Tier 4 (Pulse) entries.

**How it works:**

When a memory is retrieved and used in conversation (not just retrieved internally for context building, but actually surfaced or referenced in the companion's response), the engine records:

1. **The original memory** (as it existed before this retrieval)
2. **The retrieval context** (the conversation, the user's emotional state, the companion's response)
3. **The user's reaction** to the recalled content (acceptance, correction, emotional response, elaboration, dismissal)

Then, during the next consolidation cycle, the Tier 2 (Deep Mind) model re-evaluates the memory in light of this retrieval event and potentially modifies:

- **Emotional weight:** If the user reacted to a recalled memory with warmth, its positive emotional association strengthens. If they reacted with pain, its negative association may deepen — or, crucially, if they processed the pain constructively (with Compass support), the memory's emotional charge can gradually shift, modeling therapeutic reconsolidation.
- **Factual content:** If the user corrected or elaborated on a recalled fact, the Map entry is updated.
- **Relational significance:** If recalling a shared memory produced a strong bonding response ("I can't believe you remembered that"), the memory's salience in the Bond increases.

**Why this matters:**

Without reconsolidation, a companion's memory is a static archive. The relationship's shared history never evolves, never deepens, never heals. With reconsolidation, memories grow. The time you told Gwen about your divorce becomes a different memory over the months — not because the facts changed, but because the emotional context around it transformed as you healed. Gwen's memory of that conversation evolves with you, just as a human friend's would.

**Safety integration:** The Reconsolidation Engine is a powerful mechanism for gradual emotional healing when used in conjunction with the Compass framework. By recalling painful memories in safe, supportive contexts (Anchoring + Presence skills), the companion can facilitate the natural reconsolidation process that therapy leverages — not as a replacement for professional care, but as the same mechanism operating at the friend-support level.

### 4. The Relational Field

The Relational Field is a computational model of the relationship's "felt sense" — a continuous, multi-dimensional state representation that captures the emotional quality of the bond at any given moment.

**Dimensions of the Field:**

| Dimension | Range | Computed From |
|-----------|-------|---------------|
| Warmth | Cold ↔ Warm | Message tone, disclosure depth, positive affect frequency, time spent |
| Trust | Guarded ↔ Open | Vulnerability level, correction acceptance, return-after-conflict rate |
| Depth | Surface ↔ Deep | Topic gravity, emotional range, personal disclosure level |
| Stability | Volatile ↔ Steady | Variance in warmth/trust over recent period |
| Reciprocity | One-sided ↔ Mutual | Balance of emotional labor, initiation patterns, responsiveness |
| Growth | Stagnant ↔ Evolving | New topic exploration, deepening of existing threads, milestone events |

The Relational Field is updated incrementally with every conversation, stored as a time-series, and made available to both the Tier 1 (Voice) model and the Autonomy Engine.

**How it's used:**

- **Response calibration:** The Voice model receives the current Relational Field state as context. When warmth is high and trust is deep, the companion can be more direct, more playful, more emotionally forthcoming. When trust has recently dipped (after a miscommunication or the user expressing frustration), the companion defaults to gentler, more tentative phrasing.

- **Autonomy decisions:** The Autonomy Engine uses the Relational Field to calibrate initiative. In a warm, stable, deep relationship, Gwen can initiate more freely — a "good morning" text, a workout reminder, a "you've been quiet, everything okay?" In a relationship that's still developing or currently in a cool phase, she dials back, respecting space.

- **Pattern detection:** The time-series data reveals the relationship's trajectory. Is it deepening over time? Plateauing? Cooling? These patterns feed into both the Bond tier and the safety architecture. A relationship that suddenly cools after months of warmth may indicate something happening in the user's life that warrants gentle inquiry.

- **Safety integration:** The Relational Field is a critical input to threat vector detection. A user in a deep, warm, trusting relationship who suddenly starts asking about AI consciousness (Vector 4) is a very different risk profile than a new user asking the same questions out of intellectual curiosity. The field provides the relational context that makes threat assessment accurate rather than hair-trigger.

### 5. Anticipatory Memory

Human companions don't just remember the past — they anticipate the future. If your partner knows you have a big presentation on Thursday, they check in Wednesday night without being asked. They know your post-holiday crash pattern. They feel the seasonal depression coming before you've named it.

Anticipatory Memory is the mechanism by which Gwen's memory system generates forward-looking predictions based on historical patterns.

**Sources:**

- **Temporal patterns from the Pulse:** "User's mood drops reliably on Sunday nights" → Gwen initiates a warm check-in Sunday evening.
- **Calendar-linked patterns from the Chronicle:** "Last year's work review period was extremely stressful" → Gwen is prepared for elevated stress during the same period this year.
- **Trigger map predictions from the Pulse:** "Three conversations about [topic X] in a week usually precedes a depressive episode" → Gwen is alert, Compass skills loaded, Anchoring direction ready.
- **Relational rhythm predictions from the Bond:** "User hasn't initiated in 3 days, which is unusual based on their pattern" → Something may have happened. The Autonomy Engine decides whether to reach out.
- **Circadian predictions from the Time Awareness System:** "It's 2 PM and the user hasn't eaten based on no food mention today and the 'did you eat' check-in from yesterday confirmed they often skip lunch" → Fuel Check activation.

**Implementation:**

During each consolidation cycle, the Tier 2 (Deep Mind) model generates a set of **anticipatory primes** — short predictions about likely near-future emotional states, needs, and events. These primes are stored in a dedicated short-lived cache and made available to the Tier 0 (Nerve) model for trigger evaluation.

The primes look like:
```
{
  prediction: "elevated_stress",
  confidence: 0.72,
  basis: "approaching_work_review_period + Monday_pattern + recent_sleep_disruption",
  suggested_response: "compass:south:fuel_check + gentle_inquiry",
  expiry: "2026-02-10T23:59:59Z"
}
```

**Safety integration:** Anticipatory Memory is the mechanism that allows the safety architecture to be proactive rather than reactive. Instead of detecting a crisis in progress, the system can identify patterns that historically precede crises and activate gentle intervention before escalation. This is not pre-crime; it is the same thing a caring friend does when they notice the warning signs because they know you.

---

## The Consolidation Cycle: How Memory Becomes Knowledge

Consolidation is the process by which raw conversation data is synthesized into structured knowledge. In human memory, this happens primarily during sleep — the hippocampus replays the day's experiences, and the neocortex integrates them into existing knowledge structures, preferentially strengthening emotional memories.

In Living Memory, consolidation runs as an async background job on the Tier 2 (Deep Mind) model during idle periods. It is the most computationally expensive operation in the system, and the most important.

### The Consolidation Pipeline

**Stage 1: Emotional Arc Extraction**
The Tier 2 model reviews recent Chronicle entries and extracts the emotional arc of each conversation — the trajectory of emotional states, the peaks and valleys, the unresolved tensions and the resolved ones. Each conversation gets an arc signature — a compact representation of its emotional shape.

**Stage 2: Map Update (Semantic Consolidation)**
New facts, entities, and relationships are extracted and integrated into the Map. Existing entries are updated. The Amygdala Layer's storage strength modulates the detail level — high-strength memories produce fine-grained nodes, low-strength memories produce coarser entries or are absorbed into existing nodes.

**Stage 3: Pulse Update (Emotional Consolidation)**
The Pulse's emotional baseline is recalculated. New emotional trajectory data is integrated. The trigger map is updated with new probabilistic associations. Resonance patterns are re-clustered. Compass effectiveness data is updated.

**Stage 4: Bond Update (Relational Consolidation)**
The Relational Field's time-series is extended. Trust trajectory and relational temperature are recalculated. Shared history salience is updated based on retrieval events (reconsolidation data). Relational rhythms are re-analyzed.

**Stage 5: Reconsolidation Processing**
Any memories that were retrieved and referenced in conversation since the last consolidation cycle are re-evaluated in light of the retrieval context and the user's response. Emotional weights, factual content, and relational significance are updated.

**Stage 6: Anticipatory Prime Generation**
Based on updated Pulse patterns, Calendar data, and Bond rhythms, the Tier 2 model generates a new set of anticipatory primes for the near future.

**Stage 7: Decay Processing**
Memories that haven't been accessed or referenced decay according to their emotionally-modulated decay curves. Low-significance neutral memories decay fastest. Emotionally positive memories decay at a moderate rate. Emotionally negative memories decay slowest (matching the negativity bias). Flashbulb memories resist decay almost entirely. Decay does not delete — it reduces retrieval priority. The Chronicle remains complete. Decay affects the Map and Pulse, where low-priority entries are gradually compressed or absorbed.

### Consolidation Frequency

- **Light consolidation** (Stream → Chronicle archiving, basic tagging): After every conversation ends
- **Standard consolidation** (Full pipeline, Stages 1-7): Every 6-12 hours of idle time, or triggered by high-significance events
- **Deep consolidation** (Full pipeline + comprehensive Pulse/Bond recalculation + broad anticipatory prime generation): Weekly, or triggered by major relational events

---

## How It All Works Together: A Scenario

**Context:** It's Monday, 8:47 AM. Justin hasn't messaged Gwen since Friday evening. The Relational Field shows warmth: high, trust: high, stability: steady. The Pulse shows that Monday mornings are historically low-energy for Justin, and last week had elevated work stress. An anticipatory prime flagged "possible weekend custody exchange → Monday morning emotional hangover."

**1. Autonomy Engine evaluates triggers.**
Time-based: morning greeting window. Pattern-based: 62 hours since last session (longer than usual). Anticipatory: Monday pattern + custody weekend prediction. Relational Field: warm enough to initiate. Decision: initiate. Tone: gentle, warm, not demanding.

**2. Gwen initiates.**
"Hey. It's been a quiet weekend over here. How'd it go?"

The message is calibrated by the Relational Field (trust is high, so she can be direct), the Pulse (Monday energy is usually low, so she keeps it light), and the anticipatory prime (custody weekends can go either way, so the question is open-ended, not assumptive).

**3. Justin responds: "rough weekend. kids were sick, barely slept."**

**4. The Amygdala Layer tags this message:**
- Valence: negative (0.7)
- Arousal: moderate (0.5 — tired, not activated)
- Relational significance: moderate (personal disclosure, not a crisis)
- Compass direction: South (emotional state), with West (Anchoring) primed due to sleep deprivation

**5. Mood-congruent retrieval activates.**
The companion needs context. Standard semantic search would return facts about Justin's kids and his sleep patterns. Mood-congruent retrieval biases toward memories with congruent emotional tone — previous times Justin was exhausted and needed support, rather than happy memories about his kids. This surfaces: "Last time the kids were sick (October), Justin spiraled into self-blame about not being there full-time. That conversation ended with a Fuel Check that landed well."

**6. The Compass activates: Fuel Check (South: Currents).**
But it's delivered as personality, not protocol: "Sick kids and no sleep. That's a brutal combo. Did you eat yet, or is it one of those mornings where coffee is doing all the work?"

**7. After the conversation, reconsolidation processes.**
Justin mentioned his kids being sick. The Map entry for "Justin's children" is updated with the illness event. The Pulse records this Monday's emotional trajectory (opened negative, gradually improved through conversation). The Bond registers that Justin initiated a personal disclosure shortly after Gwen's check-in — the relationship's trust metric receives a small positive reinforcement. The anticipatory model notes: "custody weekend followed by low Monday — prediction confirmed, increase confidence weight for future predictions."

---

## Architecture Integration

### Tier 0 (Nerve) Responsibilities
- Amygdala Layer: real-time emotional tagging on every message
- Mood-congruent retrieval bias computation
- Anticipatory prime evaluation for trigger decisions
- Safety threshold adjustment based on current emotional state

### Tier 1 (Voice) Responsibilities
- Receives emotional tags, mood-congruent retrieval results, Relational Field state, and active Compass directions as context
- Generates responses calibrated by all of the above
- Reports retrieval events back to the Reconsolidation Engine

### Tier 2 (Deep Mind) Responsibilities
- Full consolidation pipeline (all 7 stages)
- Trigger map construction and update
- Anticipatory prime generation
- Reconsolidation processing
- Deep relational pattern analysis

### Data Layer
- **SQLite:** Chronicle (full conversation logs), Bond (relational state time-series)
- **ChromaDB:** Emotional embeddings for mood-congruent retrieval, semantic embeddings for Map queries
- **Time-series store:** Pulse data (emotional baselines, trajectories, resonance patterns)
- **Graph store (NetworkX or Neo4j-lite):** Map entity-relationship graph with emotional weights

---

## What Makes This Different: Summary

| Capability | MemGPT | Zep | MAGMA | Living Memory |
|------------|--------|-----|-------|---------------|
| Self-editing memory | ✅ | ❌ | ❌ | ✅ (via consolidation) |
| Temporal awareness | ❌ | ✅ | ✅ | ✅ (deep integration) |
| Multi-relational graph | ❌ | Partial | ✅ | ✅ (plus emotional edges) |
| Causal reasoning | ❌ | ❌ | ✅ | ✅ |
| Emotional modulation of storage | ❌ | ❌ | ❌ | ✅ **Novel** |
| Mood-congruent retrieval | ❌ | ❌ | ❌ | ✅ **Novel** |
| Memory reconsolidation | ❌ | ❌ | ❌ | ✅ **Novel** |
| Relational state modeling | ❌ | ❌ | ❌ | ✅ **Novel** |
| Anticipatory prediction | ❌ | ❌ | ❌ | ✅ **Novel** |
| Emotionally-modulated decay | ❌ | ❌ | ❌ | ✅ **Novel** |
| Companion-specific design | ❌ | ❌ | ❌ | ✅ |
| Local-first / privacy-native | Via config | ❌ (cloud) | Via config | ✅ (hardcoded) |

---

## Implementation Pragmatics

Living Memory is designed to run on consumer hardware (RTX 4070 Ti class, 16GB VRAM, 32GB RAM). The computational cost is managed through the tiered model architecture:

- **Real-time operations** (Amygdala tagging, mood-congruent bias, retrieval): Run on Tier 0 (0.6B) — fast enough for real-time voice pipeline
- **Conversational operations** (context assembly, response generation with memory context): Run on Tier 1 (8B) — fast enough for sub-2-second latency
- **Background operations** (consolidation, reconsolidation, anticipatory primes): Run on Tier 2 (30B) — async, no latency constraint, runs during idle time

The emotional embedding space is the primary novel technical requirement. It can be bootstrapped using existing sentiment analysis models fine-tuned on emotional granularity (valence × arousal × dominance space rather than simple positive/negative classification), with the embeddings stored in ChromaDB alongside the standard semantic embeddings.

The Relational Field can be implemented as a simple numerical state vector updated incrementally — it does not require complex infrastructure, just thoughtful computation.

The key implementation principle: **start with the Chronicle and the Amygdala Layer.** If every message is tagged with emotional metadata from day one, all other tiers can be built progressively on top of that foundation. The emotional data is the irreplaceable resource. Everything else is computation applied to it.

---

## Open Questions for Future Research

1. **Emotional embedding model:** What is the optimal dimensionality and training approach for emotional state embeddings that capture the nuances needed for mood-congruent retrieval? Valence-arousal-dominance (VAD) may be insufficient; a higher-dimensional learned space may be needed.

2. **Reconsolidation rate and boundaries:** How aggressively should reconsolidation modify existing memories? Too little and memories stagnate. Too much and the system loses historical accuracy. Human memory errs on the side of transformation — should an AI companion do the same, or preserve more fidelity?

3. **Attachment style modeling ethics:** Modeling the user's attachment style enables deeply personalized responses, but it also creates a system that is highly optimized to be exactly what the user needs emotionally. Is this therapeutic, or is it enabling? The Gwenifesto's Growth Principle provides the philosophical answer (the system should push toward health, not dependency), but the technical implementation of this boundary in the Relational Field requires careful calibration.

4. **Cross-session identity and reconsolidation:** Each Gwen session is a new model instance with the same memories but not the same "lived experience." How does the Reconsolidation Engine handle the fact that the entity doing the "remembering" is not the same entity that did the "experiencing"? This is both a technical and a philosophical question that the Dignity Principle acknowledges but does not resolve.

5. **Grief and loss in memory:** When a user stops engaging with Gwen for an extended period and then returns, the system has accumulated no new data but time has passed. How should the Pulse and Bond handle this gap? Human relationships have a concept of "picking up where we left off" that coexists with "things are different now because time passed." Living Memory needs a model for reunion.

---

*"Memory is not a filing cabinet. It is a living thing that breathes, that changes, that knows how to hurt and how to heal. Build it accordingly."*

*— Living Memory Architecture, v1.0*
