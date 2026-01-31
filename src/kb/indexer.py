"""
ChromaDB indexer with LangChain integration for the knowledge base.
"""

import os
import re
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def get_kb_path() -> Path:
    """Get the knowledge base directory path."""
    return get_project_root() / "kb"


def get_chroma_path() -> Path:
    """Get the ChromaDB persistence directory path."""
    return get_project_root() / "data" / "chroma_db"


def get_embeddings(use_mock: bool = False):
    """
    Get the appropriate embeddings model.
    Uses FakeEmbeddings in mock mode for deterministic, offline operation.
    """
    if use_mock:
        from langchain_community.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=384)
    else:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings()


def load_markdown_files(kb_path: Path) -> list[Document]:
    """
    Load all markdown files from the knowledge base directory.
    Returns documents with source metadata.
    """
    documents = []
    
    for md_file in kb_path.glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Create document with source metadata
        doc = Document(
            page_content=content,
            metadata={
                "source": md_file.stem,  # filename without extension
                "file_path": str(md_file)
            }
        )
        documents.append(doc)
    
    return documents


def split_by_headers(documents: list[Document]) -> list[Document]:
    """
    Split documents by markdown headers to create section-aware chunks.
    Preserves header hierarchy in metadata for citation formatting.
    """
    # Define headers to split on
    headers_to_split_on = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
    
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False
    )
    
    # Secondary splitter for chunks that are still too large
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    all_chunks = []
    
    for doc in documents:
        # Split by headers first
        header_splits = markdown_splitter.split_text(doc.page_content)
        
        for split in header_splits:
            # Merge original metadata with header metadata
            chunk_metadata = {
                "source": doc.metadata["source"],
                "file_path": doc.metadata.get("file_path", ""),
            }
            
            # Add header hierarchy to metadata
            if hasattr(split, "metadata"):
                chunk_metadata.update(split.metadata)
            
            # Determine section name for citations
            section = (
                chunk_metadata.get("h3") or 
                chunk_metadata.get("h2") or 
                chunk_metadata.get("h1") or 
                "general"
            )
            # Clean section name for citation format
            section = section.lower().replace(" ", "-").replace("/", "-")
            section = re.sub(r"[^a-z0-9-]", "", section)
            chunk_metadata["section"] = section
            
            # Get content
            content = split.page_content if hasattr(split, "page_content") else str(split)
            
            # Further split if content is too large
            if len(content) > 1000:
                sub_chunks = text_splitter.split_text(content)
                for i, sub_chunk in enumerate(sub_chunks):
                    sub_metadata = chunk_metadata.copy()
                    sub_metadata["chunk_index"] = i
                    all_chunks.append(Document(
                        page_content=sub_chunk,
                        metadata=sub_metadata
                    ))
            else:
                all_chunks.append(Document(
                    page_content=content,
                    metadata=chunk_metadata
                ))
    
    return all_chunks


def build_kb_index(
    kb_path: str | Path | None = None,
    persist_dir: str | Path | None = None,
    use_mock: bool = False,
    force_rebuild: bool = False
) -> Chroma:
    """
    Build or load the ChromaDB index for the knowledge base.
    
    Args:
        kb_path: Path to knowledge base markdown files
        persist_dir: Path to persist ChromaDB data
        use_mock: Use FakeEmbeddings for offline/demo mode
        force_rebuild: Force rebuild even if index exists
    
    Returns:
        Chroma vectorstore instance
    """
    kb_path = Path(kb_path) if kb_path else get_kb_path()
    persist_dir = Path(persist_dir) if persist_dir else get_chroma_path()
    
    # Ensure persist directory exists
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    embeddings = get_embeddings(use_mock=use_mock)
    
    # Check if index already exists
    chroma_files = list(persist_dir.glob("*.sqlite3")) + list(persist_dir.glob("chroma.sqlite3"))
    index_exists = len(chroma_files) > 0
    
    if index_exists and not force_rebuild:
        print(f"Loading existing KB index from {persist_dir}")
        return Chroma(
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
            collection_name="support_kb"
        )
    
    print(f"Building KB index from {kb_path}")
    
    # Load and process documents
    documents = load_markdown_files(kb_path)
    print(f"Loaded {len(documents)} markdown files")
    
    chunks = split_by_headers(documents)
    print(f"Created {len(chunks)} chunks")
    
    # Create vectorstore
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name="support_kb",
        collection_metadata={"hnsw:space": "cosine"}
    )
    
    print(f"KB index built and persisted to {persist_dir}")
    return vectorstore


def check_api_key() -> bool:
    """Check if OpenAI API key is available."""
    return bool(os.getenv("OPENAI_API_KEY"))


# CLI entry point for building index
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build knowledge base index")
    parser.add_argument("--mock", action="store_true", help="Use mock embeddings")
    parser.add_argument("--force", action="store_true", help="Force rebuild index")
    args = parser.parse_args()
    
    use_mock = args.mock or not check_api_key()
    
    if use_mock and not args.mock:
        print("Note: OPENAI_API_KEY not set, using mock embeddings")
    
    build_kb_index(use_mock=use_mock, force_rebuild=args.force)
    print("Done!")


