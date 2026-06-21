from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from rag_chatbot import init_rag, answer_query

# Global state nesnesi
state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Upgrade the RAG infrastructure and update the state.
    print("Initializing RAG backend...")
    initialized_state = init_rag(verbose=False)
    state.update(initialized_state)
    print(f"RAG backend initialized successfully. Active model: {state.get('active_model')}")
    yield
    # Shutdown (If there is a DB connection or other thing to clean up, it's written here)
    print("Shutting down RAG backend...")

app = FastAPI(lifespan=lifespan, title="Frissonitte RAG API")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str

@app.post("/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    try:
        # Directly calling the refactored logic
        answer = answer_query(req.query, state)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))