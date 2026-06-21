import os
import sys
import chromadb
from dotenv import load_dotenv
load_dotenv()
from groq import Groq
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
GROQ_MODEL = "llama-3.3-70b-versatile"
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

def init_rag(verbose=False) -> dict:
    """It initializes the models and vector database. It is common to both FastAPI and CLI."""
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        if verbose: console.print("[bold red]GROQ_API_KEY not set in environment.[/bold red]")
        sys.exit(1)
    groq_client = Groq(api_key=groq_api_key)

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
        "groq_client": groq_client,
    }

def answer_query(query: str, state: dict) -> str:
    """Takes the query, retrieves from ChromaDB, generates response via Groq. Common to both API and CLI."""
    model = state["model"]
    collection = state["collection"]
    groq_client = state["groq_client"]

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
        user_message = f"Sources: {source_list}\n\nContext:\n{context}\n\nQuestion: {query}"
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating response from Groq: {e}"

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
                info_table.add_row("LLM Provider", "Groq")
                info_table.add_row("LLM Model", GROQ_MODEL)
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