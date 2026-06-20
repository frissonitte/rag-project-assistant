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
            Text(
                ascii_art,
                style="bold cyan",
                justify="center",
                no_wrap=True,
            ),
            border_style="cyan",
            expand=True,
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

def main():
    print_header()
    
    # 1. Check Ollama Status
    ollama_running, available_models = check_ollama()
    
    # Check default model
    active_model = DEFAULT_OLLAMA_MODEL
    if ollama_running:
        if active_model not in available_models and (active_model + ":latest") not in available_models:
            similar = [m for m in available_models if "qwen" in m.lower() or "llama" in m.lower()]
            if similar:
                active_model = similar[0]
                console.print(f"[yellow]Note: Configured model '{DEFAULT_OLLAMA_MODEL}' not found in Ollama. Using available model: '{active_model}'[/yellow]")
            elif available_models:
                active_model = available_models[0]
                console.print(f"[yellow]Note: Configured model '{DEFAULT_OLLAMA_MODEL}' not found. Falling back to: '{active_model}'[/yellow]")
            else:
                console.print(f"[red]Warning: No models found in your Ollama installation. Please pull a model (e.g. 'ollama pull qwen2.5:14b')[/red]")
    else:
        console.print("[bold red]⚠️ Ollama is not running on http://localhost:11434.[/bold red]")
        console.print("[yellow]The generation step (Step 5) will be mocked (showing retrieved documents only).[/yellow]\n")

    # 2. Load and index documents
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Load files
        task_load = progress.add_task(description="Reading documents from directory...", total=None)
        all_chunks, sources, projects = load_documents()
        progress.update(task_load, completed=True, description=f"Loaded {len(all_chunks)} chunks from {len(set(sources))} files.")
        
        if not all_chunks:
            console.print("[red]No document chunks found to index! Make sure documents directory contains .txt or .md files.[/red]")
            sys.exit(1)

        # Initialize SentenceTransformer
        task_model = progress.add_task(description="Initializing SentenceTransformer ('all-MiniLM-L6-v2')...", total=None)
        try:
            model = SentenceTransformer('all-MiniLM-L6-v2')
            progress.update(task_model, completed=True, description="SentenceTransformer model loaded.")
        except Exception as e:
            progress.update(task_model, completed=True, description=f"[red]Error loading model: {e}[/red]")
            sys.exit(1)
        
        # Initialize ChromaDB
        task_chroma = progress.add_task(description="Connecting to ChromaDB and indexing...", total=None)
        
        try:
            if PERSISTENT_DB:
                client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
                collection = client.get_or_create_collection(COLLECTION_NAME)
                
                # If collection is empty, index documents
                if collection.count() == 0:
                    progress.update(task_chroma, description=f"Embedding and indexing {len(all_chunks)} chunks...")
                    for i, chunk in enumerate(all_chunks):
                        embedding = model.encode(chunk).tolist()
                        metadata = {"source": sources[i], "project": projects[i]}
                        collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
                    progress.update(task_chroma, description=f"Created persistent index with {collection.count()} items.")
                else:
                    # Check if there are new source files not present in the index
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
                        progress.update(task_chroma, description=f"New files detected ({', '.join(new_files)}). Re-indexing...")
                        try:
                            client.delete_collection(COLLECTION_NAME)
                        except Exception:
                            pass
                        collection = client.create_collection(COLLECTION_NAME)
                        for i, chunk in enumerate(all_chunks):
                            embedding = model.encode(chunk).tolist()
                            metadata = {"source": sources[i], "project": projects[i]}
                            collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
                        progress.update(task_chroma, description=f"Indexed all files including new ones. Total: {collection.count()} chunks.")
                    else:
                        progress.update(task_chroma, description=f"Loaded existing persistent index with {collection.count()} items.")
            else:
                client = chromadb.Client()
                collection = client.create_collection(COLLECTION_NAME)
                progress.update(task_chroma, description=f"Embedding and indexing {len(all_chunks)} chunks in-memory...")
                for i, chunk in enumerate(all_chunks):
                    embedding = model.encode(chunk).tolist()
                    metadata = {"source": sources[i]}
                    collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
                progress.update(task_chroma, description=f"Created in-memory index with {collection.count()} items.")
                
            progress.update(task_chroma, completed=True, description="ChromaDB collection initialized successfully.")
        except Exception as e:
            progress.update(task_chroma, completed=True, description=f"[red]Error initializing ChromaDB: {e}[/red]")
            sys.exit(1)

    console.print("\n[bold green]Ready! You can start asking questions about your projects.[/bold green]\n")
    
    # 3. Chat loop
    while True:
        try:
            query = Prompt.ask("[bold magenta]User[/bold magenta]")
            
            if not query.strip():
                continue
                
            if query.strip().lower() == "/exit":
                console.print("[cyan]Goodbye![/cyan]")
                break
                
            if query.strip().lower() == "/help":
                table = Table(title="Available Commands")
                table.add_column("Command", style="cyan")
                table.add_column("Description", style="white")
                table.add_row("/exit", "Quit the application")
                table.add_row("/info", "Show database and model configuration info")
                table.add_row("/reindex", "Re-read documents folder and rebuild collection")
                console.print(table)
                continue
                
            if query.strip().lower() == "/info":
                info_table = Table(title="System Information")
                info_table.add_column("Property", style="yellow")
                info_table.add_column("Value", style="white")
                info_table.add_row("Documents Source", DOCS_DIR)
                info_table.add_row("Total Indexed Chunks", str(collection.count()))
                info_table.add_row("Embedding Model", "all-MiniLM-L6-v2")
                info_table.add_row("Chroma DB Mode", "Persistent" if PERSISTENT_DB else "In-Memory")
                info_table.add_row("Ollama Status", "Connected" if ollama_running else "Disconnected")
                info_table.add_row("Ollama LLM Model", active_model if ollama_running else "N/A")
                console.print(info_table)
                continue

            if query.strip().lower() == "/reindex":
                with console.status("[yellow]Re-indexing documents...[/yellow]"):
                    # Recheck Ollama status in case it started
                    ollama_running, available_models = check_ollama()
                    all_chunks, sources, projects = load_documents()
                    try:
                        client.delete_collection(COLLECTION_NAME)
                    except Exception:
                        pass
                    collection = client.create_collection(COLLECTION_NAME)
                    for i, chunk in enumerate(all_chunks):
                        embedding = model.encode(chunk).tolist()
                        metadata = {"source": sources[i], "project": projects[i]}
                        collection.add(ids=[str(i)], embeddings=[embedding], documents=[chunk], metadatas=[metadata])
                console.print(f"[green]Re-indexed {collection.count()} chunks successfully![/green]\n")
                continue

            # Step 4 — Retrieval
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
            where_filter = (
                {"project": {"$eq": detected_project}}
                if detected_project else None
            )

            with console.status("[cyan]Retrieving relevant context...[/cyan]"):
                query_emb = model.encode(query).tolist()
                query_kwargs = dict(
                    query_embeddings=[query_emb],
                    n_results=4,
                    include=["documents", "metadatas", "distances"],
                )
                if where_filter:
                    query_kwargs["where"] = where_filter
                results = collection.query(**query_kwargs)
                # If filtered query returns nothing, retry without the project filter
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

                # ChromaDB returns L2 distances; convert to cosine-like score (lower = more similar)
                # Filter by threshold: keep only chunks with distance < threshold
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
            distances = [d for _, d, _ in filtered]

            console.print("\n[bold cyan]📖 Retrieved Context Chunks:[/bold cyan]")
            if detected_project:
                console.print(f"[dim]🔍 Project filter active: {detected_project}[/dim]")
            if low_confidence:
                console.print("[bold yellow]⚠ Low confidence: no chunk passed similarity threshold. Answer may be unreliable.[/bold yellow]")
            for idx, (chunk, dist, meta) in enumerate(zip(context_chunks, distances, metadatas)):
                src_info = meta.get('source', 'Unknown') if meta else 'Unknown'
                score_label = f"distance={dist:.3f}"
                console.print(Panel(
                    Text(chunk.strip(), style="italic"),
                    title=f"Chunk {idx+1} | {src_info} | {score_label}",
                    border_style="cyan" if not low_confidence else "yellow",
                ))

            # Step 5 — Generation
            if not ollama_running:
                ollama_running, available_models = check_ollama()
                if ollama_running:
                    if DEFAULT_OLLAMA_MODEL in available_models:
                        active_model = DEFAULT_OLLAMA_MODEL
                    elif available_models:
                        active_model = available_models[0]

            if ollama_running:
                with console.status(f"[yellow]Generating answer using {active_model}...[/yellow]"):
                    try:
                        context = "\n\n".join(context_chunks)
                        source_list = ", ".join(
                            {m.get('source', 'unknown') for m in metadatas if m}
                        )
                        system_instruction = (
                            "You are an assistant that answers questions about the developer's own projects. "
                            "The context below comes from that project's documentation and source code.\n"
                            "Rules:\n"
                            "1. Answer using information present in the context, including reasonable direct inferences "
                            "(e.g. if a table lists architectures tested, you can state which ones were used).\n"
                            "2. If the context genuinely contains no relevant information, say exactly: "
                            "'I don't have this information.' and stop.\n"
                            "3. Do not invent facts not supported by the context.\n"
                            "4. Mention which project or file the information comes from.\n"
                            "5. Be concise and precise. Answer in the same language as the question."
                        )
                        prompt = (
                            f"{system_instruction}\n\n"
                            f"Sources: {source_list}\n\n"
                            f"Context:\n{context}\n\n"
                            f"Question: {query}\nAnswer:"
                        )
                        response = requests.post(
                            f"{OLLAMA_URL}/api/generate",
                            json={"model": active_model, "prompt": prompt, "stream": False},
                            timeout=60,
                        )
                        answer = response.json()['response']
                    except Exception as e:
                        answer = f"[red]Error generating response from Ollama: {e}[/red]"
            else:
                answer = (
                    "*[yellow]Ollama is offline. Here is the context that would be sent to the model:*\n\n"
                    f"**Question:** {query}\n\n"
                    f"**Context length:** {len(context_chunks)} chunks.*"
                )

            console.print("\n[bold green]🤖 Bot Answer:[/bold green]")
            console.print(Panel(Markdown(answer), border_style="green"))
            console.print("")

        except KeyboardInterrupt:
            console.print("\n[cyan]Goodbye![/cyan]")
            break
        except Exception as e:
            console.print(f"[red]An error occurred in the loop: {e}[/red]")

if __name__ == "__main__":
    main()