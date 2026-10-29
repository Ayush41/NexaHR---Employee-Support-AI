# Ingestion file test
from app.services.ingestion import load_file, chunk_documents
from pathlib import Path 


docs = load_file(Path("data\sample_kb\company_hr_handbook.md"))
chunked_docs = chunk_documents(docs)

print(chunked_docs)

print(len(chunked_docs))

# # Load info test

# from app.core.config import get_settings

# settings = get_settings()

# print(f"App Name: {settings.app_name}") 
# print(f"Openai API: {settings.openai_api_key}")

