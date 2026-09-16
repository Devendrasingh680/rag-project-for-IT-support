"""
FastAPI entrypoint. Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Then POST to /support with {"query": "..."} or open /docs for the Swagger UI.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agent import run_agent
from app import config

app = FastAPI(
    title="Enterprise IT Support & Troubleshooting Agent",
    description="RAG + agentic fallback: queries internal KB (Pinecone) first, "
                "falls back to live web search (Tavily) when internal knowledge is insufficient.",
    version="1.0.0",
)


class SupportRequest(BaseModel):
    query: str


class SupportResponse(BaseModel):
    query: str
    answer: str
    used_source: str        # "kb", "web", or "kb+web"
    kb_top_score: float
    sources: list[dict]


@app.get("/health")
def health():
    missing = [
        name for name, val in [
            ("PINECONE_API_KEY", config.PINECONE_API_KEY),
            ("GROQ_API_KEY", config.GROQ_API_KEY),
            ("TAVILY_API_KEY", config.TAVILY_API_KEY),
        ] if not val
    ]
    return {"status": "ok" if not missing else "missing_keys", "missing_keys": missing}


@app.post("/support", response_model=SupportResponse)
def support(request: SupportRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        result = run_agent(request.query)
    except Exception as e:
        # In production you'd log this with a request ID; kept simple for the assignment.
        raise HTTPException(status_code=500, detail=f"Agent failed: {str(e)}")

    return SupportResponse(
        query=request.query,
        answer=result["answer"],
        used_source=result["used_source"],
        kb_top_score=result["kb_top_score"],
        sources=result["sources"],
    )
