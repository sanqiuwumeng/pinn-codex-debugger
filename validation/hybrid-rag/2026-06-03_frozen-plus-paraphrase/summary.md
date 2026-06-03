# Hybrid-RAG Frozen Plus Paraphrase Replay

- Date: `2026-06-03`
- Backend: `stdlib-concept-charngram-v1:rules-anchor+concept-lexicon+token-overlap+char-3gram`
- External package installation: none
- Frozen benchmark family routing: `9/9`
- Frozen benchmark expected top heading: `9/9`
- Frozen benchmark expected heading in top 5: `9/9`
- Paraphrase family routing: `9/9`
- Paraphrase expected top heading: `9/9`
- Paraphrase expected heading in top 5: `9/9`

## Comparison Notes

- Skill-only baseline score: `86/90` from the frozen blind suite summary.
- Rules-MCP deterministic family routing: `9/9` on frozen replay.
- Hybrid-RAG keeps the rules boundary for traceability and adds concept/char-ngram recall for paraphrases.
- Each ranked section records source SHA256, heading, line range, score parts, matched concepts, matched terms, and matched anchors.

## Known Limits

- This backend is deterministic lexical-semantic retrieval, not neural embedding retrieval.
- It is designed to validate recall and ordering before any package or model installation.
