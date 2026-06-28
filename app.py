from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from contextlib import asynccontextmanager
from rag_chatbot import init_rag, answer_query, GROQ_MODEL

state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing RAG backend...")
    state.update(init_rag(verbose=False))
    print(f"RAG backend initialized successfully. Active model: {GROQ_MODEL}")
    yield
    print("Shutting down RAG backend...")

app = FastAPI(lifespan=lifespan, title="Frissonitte RAG API")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    low_confidence: bool

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/query", response_model=QueryResponse)
@limiter.limit("3/hour")
def query_endpoint(request: Request, req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        result = answer_query(req.query, state)
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            low_confidence=result["low_confidence"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
