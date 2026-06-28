"""Build ChromaDB index from documents/. Run once at Docker build time."""
import chromadb
from sentence_transformers import SentenceTransformer
from rag_chatbot import load_documents, CHROMA_DB_PATH, COLLECTION_NAME

model = SentenceTransformer('all-MiniLM-L6-v2')
all_chunks, sources, projects = load_documents()

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

if collection.count() == 0:
    for i, chunk in enumerate(all_chunks):
        embedding = model.encode(chunk).tolist()
        collection.add(
            ids=[str(i)],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{"source": sources[i], "project": projects[i]}],
        )

print(f"Index built: {collection.count()} chunks.")
