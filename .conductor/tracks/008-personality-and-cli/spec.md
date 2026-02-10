# Spec: Personality System & Basic CLI

## 1. Context & Goal
Build the personality module loader (YAML files defining companion identity) and the basic CLI orchestrator that ties everything from Tracks 001-007 together into a working conversation loop. At the end of this track, you can launch Gwen and have your first conversation. This is the US-001 user story. References SRS.md Sections 3.11, 13, and 18 US-001.

## 2. Technical Approach
- Personality defined as YAML file with structured fields
- PersonalityLoader validates required fields and produces PersonalityModule dataclass
- CLI is a simple async input loop
- Orchestrator chains: Input -> TME -> Tier0 classify -> Context assembly (simplified) -> Tier 1 generate -> Display
- Context assembly is simplified for now (just system prompt + recent messages -- full version in Track 010)

## 3. Requirements
- [ ] data/personalities/gwen.yaml with complete Gwen personality definition
- [ ] PersonalityLoader: load_from_file(path) -> PersonalityModule, validates required fields
- [ ] PromptBuilder: builds system prompt from PersonalityModule + mode + optional compass section
- [ ] CLI main loop (gwen/ui/cli.py): async input -> process -> display
- [ ] Basic orchestrator (gwen/core/orchestrator.py): chains phases 1, 2, 3, 6 (simplified)
- [ ] gwen/__main__.py entry point: `python -m gwen` launches CLI
- [ ] First conversation works end-to-end (US-001)

## 4. Verification Plan
- [ ] gwen.yaml loads and validates correctly
- [ ] System prompt is generated with personality fields
- [ ] `python -m gwen` launches, accepts input, returns Gwen response
- [ ] Messages are classified by Tier 0 pipeline
- [ ] Basic conversation flows naturally
