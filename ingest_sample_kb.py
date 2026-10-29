import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings
from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents

settings = get_settings()

folder = Path(settings.sample_kb_dir)
files = [p for p in folder.iterdir() if p.is_file()]

all_docs = []
for path in files:
    all_docs.extend(load_file(path))
chunks = chunk_documents(all_docs)
ids = add_documents(chunks)
print(f"Indexed {len(files)} files -> {len(chunks)} chunks -> {len(ids)} Pinecone vectors")