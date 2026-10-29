import time

from pinecone import Pinecone, ServerlessSpec
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

from app.core.config import get_settings

settings = get_settings()

_embeddings = None
_vectorstore = None

EMBEDDING_DIMENSIONS = {
    "sentence-transformers/all-minilm-l6-v2": 384,
    "all-minilm-l6-v2": 384,
}


def get_embedding_dimension(model_name: str | None = None) -> int:
    name = (model_name or settings.embedding_model or "").strip().lower()

    if name in EMBEDDING_DIMENSIONS:
        return EMBEDDING_DIMENSIONS[name]

    raise ValueError(
        f"Unsupported embedding model: {name!r}. "
        "Configure a supported model and its dimension in EMBEDDING_DIMENSIONS."
    )


def get_embeddings():
    global _embeddings

    if _embeddings is None:
        model_name = settings.embedding_model

        if not model_name:
            raise RuntimeError("EMBEDDING_MODEL is missing from configuration")

        _embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    return _embeddings


def ensure_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing")

    if not settings.pinecone_index_name:
        raise RuntimeError("PINECONE_INDEX_NAME is missing")

    desired_dimension = get_embedding_dimension()
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index_name = settings.pinecone_index_name

    def get_existing_names():
        indexes = pc.list_indexes()

        if hasattr(indexes, "names"):
            return indexes.names()

        return [
            item.name if hasattr(item, "name") else item["name"]
            for item in indexes
        ]

    if index_name in get_existing_names():
        info = pc.describe_index(index_name)
        current_dimension = getattr(info, "dimension", None)

        if current_dimension is None and isinstance(info, dict):
            current_dimension = info.get("dimension")

        if current_dimension != desired_dimension:
            raise RuntimeError(
                f"Pinecone index '{index_name}' has dimension "
                f"{current_dimension}, but model "
                f"'{settings.embedding_model}' requires "
                f"{desired_dimension}. Use a new index with the "
                "correct dimension; the existing index was not deleted."
            )

        return pc.Index(index_name)

    pc.create_index(
        name=index_name,
        dimension=desired_dimension,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1",
        ),
    )

    while True:
        info = pc.describe_index(index_name)
        status = getattr(info, "status", {})
        ready = (
            status.get("ready", False)
            if isinstance(status, dict)
            else getattr(status, "ready", False)
        )

        if ready:
            break

        time.sleep(1)

    return pc.Index(index_name)


def get_vectorstore():
    global _vectorstore

    if _vectorstore is None:
        _vectorstore = PineconeVectorStore(
            index=ensure_index(),
            embedding=get_embeddings(),
            namespace=settings.pinecone_namespace,
        )

    return _vectorstore


def get_retriever():
    return get_vectorstore().as_retriever(search_kwargs={"k": settings.top_k})


def add_documents(chunks):
    if not chunks:
        return []

    return get_vectorstore().add_documents(chunks)
