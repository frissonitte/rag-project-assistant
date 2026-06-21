import os
import sys
import requests
import chromadb
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

# --- CONFIGURATION ---
PERSISTENT_DB = True
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "projects"
DEFAULT_OLLAMA_MODEL = "qwen3:14b"
OLLAMA_URL = "http://localhost:11434"
DOCS_DIR = "documents"

console = Console()

def print_header():
    console.clear()
    ascii_art = r"""
███████╗██████╗ ██╗███████╗███████╗ ██████╗ ███╗   ██╗██╗████████╗████████╗███████╗
██╔════╝██╔══██╗██║██╔════╝██╔════╝██╔═══██╗████╗  ██║██║╚══██╔══╝╚══██╔══╝██╔════╝
█████╗  ██████╔╝██║███████╗███████╗██║   ██║██╔██╗ ██║██║   ██║      ██║   █████╗
██╔══╝  ██╔══██╗██║╚════██║╚════██║██║   ██║██║╚██╗██║██║   ██║      ██║   ██╔══╝
██║     ██║  ██║██║███████║███████║╚██████╔╝██║ ╚████║██║   ██║      ██║   ███████╗
╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝      ╚═╝   ╚══════╝
                                    RAG CHATBOT
    """
    console.print(
        Panel(
            Text(ascii_art, style="bold cyan", justify="center", no_wrap=True),
            border_style="cyan", expand=True,
        )
    )
    console.print(
        "[dim]FRISSONITTE RAG Chatbot v1.0.0"
        " | Type '/exit' to quit"
        " | '/help' for commands[/dim]\n"
    )

def chunk_text(text, chunk_size=200, overlap=40):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

KNOWN_PROJECTS = [
    "wbc-analyzer",
    "kinematic",
    "listing-pilot",
    "popcorn-wagon",
    "portal-cleaner-ultimate",
]

def _extract_project(filename: str) -> str:
    for p in KNOWN_PROJECTS:
        if filename.startswith(p):
            return p
    return "unknown"

def load_documents():
    if not os.path.exists(DOCS_DIR):
        console.print(f"[red]Error: '{DOCS_DIR}' directory not found! Run 'prepare_docs.py' first.[/red]")
        sys.exit(1)

    all_chunks = []
    sources = []
    projects = []

    for filename in os.listdir(DOCS_DIR):
        if filename.endswith(".txt") or filename.endswith(".md"):
            filepath = os.path.join(DOCS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                chunks = chunk_text(content)
                project = _extract_project(filename)
                all_chunks.extend(chunks)
                sources.extend([filename] * len(chunks))
                projects.extend([project] * len(chunks))
            except Exception as e:
                console.print(f"[yellow]Warning: Could not read {filename}: {e}[/yellow]")

    return all_chunks, sources, projects

def check_ollama():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []

def init_rag(verbose=False) -> dict:
    """It initializes the models and vector database. It is common to both FastAPI and CLI."""
    ollama_running, available_models = check_ollama()
    active_model = DEFAULT_OLLAMA_MODEL

    if ollama_running:
        if active_model not in available_models and (active_model + ":latest") not in available_models:
            similar = [m for m in available_models if "qwen" in m.lower() or "llama" in m.lower()]
            if similar:
                active_model = similar[0]
                if verbose: console.print(f"[yellow]Note: Configured model '{DEFAULT_OLLAMA_MODEL}' not found in Ollama. Using available model: '{active_model}'[/yellow]")
            elif available_models:
                active_model = available_models[0]
                if verbose: console.print(f"[yellow]Note: Configured model '{DEFAULT_OLLAMA_MODEL}' not found. Falling back to: '{active_model}'[/yellow]")
            else:
                if verbose: console.print(f"[red]Warning: No models found in your Ollama installation. Please pull a model (e.g. 'ollama pull qwen2.5:14b')[/red]")
    else:
        if verbose: 
            console.print("[bold red] Ollama is not running on http://localhost:11434.[/bold red]")
            console.print("[yellow]The generation step (Step 5) will be mocked (showing retrieved documents only).[/yellow]\n")

    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        if verbose: console.print(f"[red]Error loading SentenceTransformer: {e}[/red]")
        sys.exit(1)

    all_chunks, sources, projects = load_documents()
    
    if not all_chunks:
        if verbose: console.print("[red]No document chunks found to index![/red]")
        sys.exit(1)

    try:
        if PERSISTENT_DB:
            client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            collection = client.get_or_create_collection(COLLECTION_NAME)
            
            if collection.count() == 0:
                for i, chunk in enumerate(all_chunks):
                    embedding = model.encode(chunk).tolist()
                    metadata = {"source": sources[i], "project": projects[i]}
                    collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
            else:
                indexed_sources = set()
                try:
                    results = collection.get(include=["metadatas"])
                    if results and "metadatas" in results:
                        indexed_sources = {m["source"] for m in results["metadatas"] if m and "source" in m}
                except Exception:
                    pass
                
                current_sources = set(sources)
                new_files = current_sources - indexed_sources
                
                if new_files:
                    try: client.delete_collection(COLLECTION_NAME)
                    except Exception: pass
                    collection = client.create_collection(COLLECTION_NAME)
                    for i, chunk in enumerate(all_chunks):
                        embedding = model.encode(chunk).tolist()
                        metadata = {"source": sources[i], "project": projects[i]}
                        collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
        else:
            client = chromadb.Client()
            collection = client.create_collection(COLLECTION_NAME)
            for i, chunk in enumerate(all_chunks):
                embedding = model.encode(chunk).tolist()
                metadata = {"source": sources[i]}
                collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
    except Exception as e:
        if verbose: console.print(f"[red]Error initializing ChromaDB: {e}[/red]")
        sys.exit(1)

    return {
        "model": model,
        "collection": collection,
        "client": client,
        "ollama_running": ollama_running,
        "active_model": active_model
    }

def answer_query(query: str, state: dict) -> str:
    """It takes the query, searches in ChromaDB, and generates the response with Ollama. It's common to both API and CLI."""
    model = state["model"]
    collection = state["collection"]
    ollama_running = state["ollama_running"]
    active_model = state["active_model"]

    SIMILARITY_THRESHOLD = 1.40
    PROJECT_KEYWORDS = {
        "wbc-analyzer": ["wbc", "wbc analyzer", "wbc-analyzer", "white blood cell", "arayüz", "hücre", "densenet", "mef", "grad-cam", "gradcam", "medsiwsh", "wbcattention"],
        "listing-pilot": ["listing pilot", "listing-pilot", "dolap", "gardrops", "appium", "fiyat", "listing"],
        "kinematic": ["kinematic", "hareket", "action recognition", "dask", "arf", "adwin", "motion"],
        "popcorn-wagon": ["popcorn wagon", "popcorn-wagon", "film", "movie", "öneri", "recommendation", "svd", "annoy"],
        "portal-cleaner-ultimate": ["portal cleaner", "portal-cleaner", "portal", "erp", "tkinter", "selenium scraper"],
    }

    def detect_project(q: str) -> str | None:
        q_lower = q.lower()
        for project, keywords in PROJECT_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                return project
        return None

    detected_project = detect_project(query)
    where_filter = {"project": {"$eq": detected_project}} if detected_project else None

    # Retrieval
    query_emb = model.encode(query).tolist()
    query_kwargs = dict(
        query_embeddings=[query_emb],
        n_results=4,
        include=["documents", "metadatas", "distances"],
    )
    if where_filter:
        query_kwargs["where"] = where_filter
        
    results = collection.query(**query_kwargs)
    
    # Retries without filter if empty
    if not results['documents'] or not results['documents'][0]:
        if where_filter:
            results = collection.query(
                query_embeddings=[query_emb],
                n_results=4,
                include=["documents", "metadatas", "distances"],
            )

    raw_chunks = results['documents'][0] if results['documents'] and results['documents'][0] else []
    raw_distances = results['distances'][0] if results['distances'] and results['distances'][0] else []
    raw_metadatas = results['metadatas'][0] if results.get('metadatas') and results['metadatas'][0] else []

    filtered = [
        (chunk, dist, meta)
        for chunk, dist, meta in zip(raw_chunks, raw_distances, raw_metadatas)
        if dist < SIMILARITY_THRESHOLD
    ]

    low_confidence = len(filtered) == 0
    if low_confidence and raw_chunks:
        filtered = [(raw_chunks[0], raw_distances[0], raw_metadatas[0] if raw_metadatas else {})]

    context_chunks = [c for c, _, _ in filtered]
    metadatas = [m for _, _, m in filtered]

    # Generation
    if not ollama_running:
        ollama_running, available_models = check_ollama()
        if ollama_running:
            if active_model in available_models:
                pass # active model remains same
            elif available_models:
                active_model = available_models[0]
            state["ollama_running"] = True
            state["active_model"] = active_model

    if ollama_running:
        try:
            context = "\n\n".join(context_chunks)
            source_list = ", ".join({m.get('source', 'unknown') for m in metadatas if m})
            system_instruction = (
                "You are an assistant that answers questions about the developer's own projects. "
                "The context below comes from that project's documentation and source code.\n"
                "Rules:\n"
                "1. Answer using information present in the context, including reasonable direct inferences.\n"
                "2. If the context genuinely contains no relevant information, say exactly: 'I don't have this information.' and stop.\n"
                "3. Do not invent facts not supported by the context.\n"
                "4. Mention which project or file the information comes from.\n"
                "5. Be concise and precise. Answer in the same language as the question."
            )
            prompt = f"{system_instruction}\n\nSources: {source_list}\n\nContext:\n{context}\n\nQuestion: {query}\nAnswer:"
            
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": active_model, "prompt": prompt, "stream": False},
                timeout=60,
            )
            return response.json()['response']
        except Exception as e:
            return f"Error generating response from Ollama: {e}"
    else:
        return (
            "*Ollama is offline. Here is the context that would be sent to the model:*\n\n"
            f"**Question:** {query}\n\n"
            f"**Context length:** {len(context_chunks)} chunks.*"
        )

def main():
    """This is for CLI orchestration only. The API will not handle this."""
    print_header()
    
    with console.status("[cyan]Initializing System...[/cyan]"):
        state = init_rag(verbose=True)

    console.print("\n[bold green]Ready! You can start asking questions about your projects.[/bold green]\n")
    
    while True:
        try:
            query = Prompt.ask("[bold magenta]User[/bold magenta]")
            
            if not query.strip(): continue
            if query.strip().lower() == "/exit":
                console.print("[cyan]Goodbye![/cyan]")
                break
            
            if query.strip().lower() == "/help":
                table = Table(title="Available Commands")
                table.add_column("Command", style="cyan")
                table.add_column("Description", style="white")
                table.add_row("/exit", "Quit the application")
                table.add_row("/info", "Show database and model info")
                console.print(table)
                continue
                
            if query.strip().lower() == "/info":
                info_table = Table(title="System Information")
                info_table.add_column("Property", style="yellow")
                info_table.add_column("Value", style="white")
                info_table.add_row("Ollama Status", "Connected" if state["ollama_running"] else "Disconnected")
                info_table.add_row("Ollama LLM Model", state["active_model"])
                info_table.add_row("Chroma DB Items", str(state["collection"].count()))
                console.print(info_table)
                continue

            with console.status("[cyan]Retrieving context and generating answer...[/cyan]"):
                answer = answer_query(query, state)
            
            console.print("\n[bold green] Bot Answer:[/bold green]")
            console.print(Panel(Markdown(answer), border_style="green"))
            console.print("")

        except KeyboardInterrupt:
            console.print("\n[cyan]Goodbye![/cyan]")
            break
        except Exception as e:
            console.print(f"[red]An error occurred in the loop: {e}[/red]")

if __name__ == "__main__":
    main()