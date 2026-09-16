"""
LangGraph agent implementing:
    query -> retrieve_kb -> judge_sufficiency -> [generate_answer | web_search -> generate_answer]

Design decision on "did internal search fail?" (see README for full justification):
We use a HYBRID sufficiency check, not a single threshold and not an LLM call every time:
    - score >= SIMILARITY_CONFIDENT_THRESHOLD  -> trust it, skip the LLM judge (cheap, fast)
    - score <  SIMILARITY_REJECT_THRESHOLD     -> don't bother judging, go straight to web (cheap, fast)
    - in between                               -> ambiguous, ask the LLM to judge relevance (costs one extra call,
                                                    but this zone is exactly where pure-threshold approaches break)
This means most queries resolve without an extra LLM call, but borderline
cases (which are the ones that actually cause wrong answers) get a real check.
"""
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END
from groq import Groq
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from tavily import TavilyClient

from app import config


# ---------- State ----------

class AgentState(TypedDict):
    query: str
    kb_results: list[dict]          # retrieved chunks + scores + metadata
    kb_top_score: float
    kb_sufficient: Optional[bool]   # None until judged
    web_results: list[dict]
    used_source: str                # "kb" | "web" | "kb+web"
    answer: str
    sources: list[dict]             # citations shown to the user


# ---------- Lazy-initialized clients (avoid loading models/keys at import time) ----------

_embedding_model = None
_pinecone_index = None
_groq_client = None
_tavily_client = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _embedding_model


def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        pc = Pinecone(api_key=config.PINECONE_API_KEY)
        _pinecone_index = pc.Index(config.PINECONE_INDEX_NAME)
    return _pinecone_index


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


def get_tavily_client():
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=config.TAVILY_API_KEY)
    return _tavily_client


# ---------- Nodes ----------

def retrieve_kb(state: AgentState) -> AgentState:
    """Query Pinecone for the top-k most relevant chunks."""
    model = get_embedding_model()
    index = get_pinecone_index()

    query_vec = model.encode(state["query"]).tolist()
    results = index.query(vector=query_vec, top_k=config.TOP_K, include_metadata=True)

    kb_results = [
        {
            "text": match["metadata"].get("text", ""),
            "source_file": match["metadata"].get("source_file", "unknown"),
            "title": match["metadata"].get("title", ""),
            "score": match["score"],
        }
        for match in results.get("matches", [])
    ]
    top_score = kb_results[0]["score"] if kb_results else 0.0

    return {**state, "kb_results": kb_results, "kb_top_score": top_score}


def judge_sufficiency(state: AgentState) -> AgentState:
    """
    Decide whether the KB results actually answer the query.
    Hybrid logic: only calls the LLM in the ambiguous middle zone.
    """
    score = state["kb_top_score"]

    if score >= config.SIMILARITY_CONFIDENT_THRESHOLD:
        return {**state, "kb_sufficient": True}

    if score < config.SIMILARITY_REJECT_THRESHOLD:
        return {**state, "kb_sufficient": False}

    # Ambiguous zone -> ask the LLM to actually check relevance
    client = get_groq_client()
    context = "\n\n".join(r["text"] for r in state["kb_results"][:3])
    prompt = f"""A user asked: "{state['query']}"

Here is the top retrieved context from the internal knowledge base:
---
{context}
---

Does this context contain enough information to directly and accurately answer the user's question?
Answer with exactly one word: YES or NO."""

    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=5,
    )
    verdict = response.choices[0].message.content.strip().upper()
    return {**state, "kb_sufficient": verdict.startswith("YES")}


def route_after_judgment(state: AgentState) -> Literal["generate_answer", "web_search"]:
    return "generate_answer" if state["kb_sufficient"] else "web_search"


def web_search(state: AgentState) -> AgentState:
    """Fallback: search the live web via Tavily for recent patches/error codes."""
    client = get_tavily_client()
    response = client.search(
        query=f"{state['query']} error fix",
        max_results=5,
        search_depth="advanced",
    )
    web_results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in response.get("results", [])
    ]
    return {**state, "web_results": web_results}


def generate_answer(state: AgentState) -> AgentState:
    """Synthesize the final answer from whichever source(s) were used, with citations."""
    client = get_groq_client()

    if state.get("web_results"):
        context_blocks = [f"[WEB: {r['title']}] {r['content']}" for r in state["web_results"]]
        used_source = "kb+web" if state["kb_results"] else "web"
        sources = [{"type": "web", "title": r["title"], "url": r["url"]} for r in state["web_results"]]
    else:
        context_blocks = [f"[KB: {r['title']}] {r['text']}" for r in state["kb_results"]]
        used_source = "kb"
        sources = [{"type": "kb", "title": r["title"], "file": r["source_file"]} for r in state["kb_results"]]

    context = "\n\n".join(context_blocks)
    prompt = f"""You are an enterprise IT support assistant. Answer the user's question using ONLY the context below.
Be concise and give concrete steps. If the context is from the web, mention that it may reflect a recent
patch or advisory rather than internal policy. Always cite which source (KB doc name or web URL) a claim came from.

User question: {state['query']}

Context:
{context}

Answer:"""

    response = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500,
    )
    answer = response.choices[0].message.content.strip()

    return {**state, "answer": answer, "used_source": used_source, "sources": sources}


# ---------- Graph assembly ----------

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieve_kb", retrieve_kb)
    graph.add_node("judge_sufficiency", judge_sufficiency)
    graph.add_node("web_search", web_search)
    graph.add_node("generate_answer", generate_answer)

    graph.set_entry_point("retrieve_kb")
    graph.add_edge("retrieve_kb", "judge_sufficiency")
    graph.add_conditional_edges(
        "judge_sufficiency",
        route_after_judgment,
        {"generate_answer": "generate_answer", "web_search": "web_search"},
    )
    graph.add_edge("web_search", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


_compiled_graph = None


def get_agent():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_agent(query: str) -> AgentState:
    agent = get_agent()
    initial_state: AgentState = {
        "query": query,
        "kb_results": [],
        "kb_top_score": 0.0,
        "kb_sufficient": None,
        "web_results": [],
        "used_source": "",
        "answer": "",
        "sources": [],
    }
    return agent.invoke(initial_state)
