# Enterprise IT Support & Troubleshooting Agent

RAG + agentic fallback system. An agent receives a user's IT problem, searches a private
Pinecone vector index of internal IT policies/runbooks, and — only if that search is
judged insufficient — falls back to a live Tavily web search for recent patches/CVEs/error
codes not covered by internal docs. Built with FastAPI, LangGraph, Pinecone, Groq, Tavily.

## Architecture

```
POST /support {"query": "..."}
        │
        ▼
  retrieve_kb  ──────► Pinecone similarity search, top-5 chunks
        │
        ▼
  judge_sufficiency ──► hybrid check (see "Design Decisions" below)
        │
   ┌────┴────┐
   ▼         ▼
sufficient  insufficient
   │         │
   │         ▼
   │     web_search ──► Tavily live search
   │         │
   └────┬────┘
        ▼
  generate_answer ────► Groq LLM synthesizes answer + citations
        │
        ▼
     response
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in PINECONE_API_KEY, GROQ_API_KEY, TAVILY_API_KEY in .env

python -m app.ingest          # embeds sample_docs/ into Pinecone
uvicorn app.main:app --reload # starts the API on :8000
```

Test it:
```bash
curl -X POST localhost:8000/support -H "Content-Type: application/json" \
  -d '{"query": "My VPN keeps timing out, what do I do?"}'
```

Or open `localhost:8000/docs` for the interactive Swagger UI.

Run the eval set (checks routing, not answer quality — see below):
```bash
python -m tests.eval_set
```

## Design Decisions (things the assignment spec left open — be ready to explain these)

**1. How does the agent decide internal search "failed"?**

The spec says "if internal search fails, trigger web search" but doesn't say how failure
is detected. Three options exist:
- Pure similarity threshold — cheap and fast, but brittle. A single cutoff doesn't
  generalize across query phrasing.
- LLM-as-judge on every query — robust, but doubles latency/cost for every request,
  including the easy cases that clearly hit the KB.
- **Hybrid (what this project uses):** similarity score ≥0.80 → trust it and skip the
  judge; score <0.55 → skip straight to web without wasting an LLM call; score in
  between → ask the LLM to actually read the retrieved chunk and judge relevance.
  This means the extra LLM call only fires in the genuinely ambiguous zone, which is
  also where a pure-threshold approach is most likely to be wrong.

These thresholds (`config.py`) are reasonable starting points, not tuned on real data —
if you have actual usage data, you'd want to tune them against labeled examples instead
of eyeballing them.

**2. Chunking strategy**

Docs are chunked by `##` header (semantic sub-section) rather than fixed token windows.
A numbered troubleshooting procedure loses meaning if step 3 gets split into a different
chunk than steps 1-2. Fixed-size chunking is simpler but this domain punishes it.

Known limitation: a few chunks are just bare document titles (the text before the first
`##`) — they pass the length filter but carry little retrieval value. Harmless in
practice (they just rank low), but worth knowing rather than pretending the pipeline is
flawless.

**3. Why local embeddings instead of an embedding API?**

`sentence-transformers/all-MiniLM-L6-v2` runs locally and is free, versus paying per-call
for an embedding API. For a small IT-docs corpus this is more than accurate enough, and
it means embedding cost doesn't scale with query volume. Tradeoff: it's a smaller/older
model than something like OpenAI's `text-embedding-3`, so on more nuanced or
multi-language corpora it would underperform.

**4. Metadata-based filtering isn't wired into the query yet**

Docs are tagged with `system` (vpn/email/printer/accounts) and `doc_type` at ingest time,
but `retrieve_kb` doesn't currently filter by it — it always searches the full index.
For a real deployment you'd want the agent to infer the relevant system from the query
and filter Pinecone metadata before the similarity search, not just rely on embeddings
to find the right document among many. This is the most obvious "next step" if extending
the project.

**5. No write actions / no human-in-the-loop gating**

This agent only reads (KB search, web search) and answers — it doesn't reset passwords,
create tickets, or touch any system. That's a deliberate scope cut, not an oversight: a
real IT support agent that can *take actions* needs a tiered permission model (read-only
vs reversible-write vs destructive, with human confirmation on the last tier) before it's
safe to demo as "agentic." The `accounts__policy` sample doc includes an explicit
escalation rule (privileged account resets require Tier 2, no exceptions) specifically to
show the KB anticipates this — but the agent itself doesn't enforce it, because it has no
tools that could violate it. If you extend this to include actions, that permission
tiering is the part to build carefully, not an afterthought.

## What the eval set actually checks

`tests/eval_set.py` is not testing "is the answer good" (that's subjective and needs
human or LLM-graded rubrics). It checks the thing the assignment spec explicitly asks
for: does the agent correctly decide when to use KB vs. fall back to web? Three cases
are answerable from the sample docs, three are deliberately outside their scope
(CVEs, zero-days, stock price) to confirm the fallback actually triggers.

## Known gaps if you want to extend this

- Metadata filtering (point 4 above)
- Real eval of answer quality, not just routing
- Conversation memory (currently single-turn, no session state)
- Rate limiting / auth on the FastAPI endpoint before this touches real users
- The similarity thresholds are unvalidated guesses — tune them if you get real query logs
