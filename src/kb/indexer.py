"""
ChromaDB indexer with LangChain integration for the knowledge base.
Supports multiple collections defined in collections.py.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document

from .collections import KBCollection, get_collection_path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def get_kb_path() -> Path:
    """Get the knowledge base directory path."""
    return get_project_root() / "kb"


def get_data_path() -> Path:
    """Get the data directory path (base for all collections)."""
    return get_project_root() / "data"


def get_chroma_path() -> Path:
    """Get the ChromaDB persistence directory path for support_kb collection."""
    return get_collection_path(get_data_path(), KBCollection.SUPPORT_KB)


def get_embeddings():
    """
    Get the OpenAI embeddings model.
    Requires OPENAI_API_KEY environment variable to be set.
    """
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
    force_rebuild: bool = False
) -> Chroma:
    """
    Build or load the ChromaDB index for the SUPPORT_KB collection.

    Args:
        kb_path: Path to knowledge base markdown files
        persist_dir: Path to persist ChromaDB data
        force_rebuild: Force rebuild even if index exists

    Returns:
        Chroma vectorstore instance
    """
    kb_path = Path(kb_path) if kb_path else get_kb_path()
    persist_dir = Path(persist_dir) if persist_dir else get_chroma_path()

    # Ensure persist directory exists
    persist_dir.mkdir(parents=True, exist_ok=True)

    embeddings = get_embeddings()

    # Check if index already exists
    chroma_files = list(persist_dir.glob("*.sqlite3")) + list(persist_dir.glob("chroma.sqlite3"))
    index_exists = len(chroma_files) > 0

    if index_exists and not force_rebuild:
        print(f"Loading existing KB index from {persist_dir}")
        return Chroma(
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
            collection_name=KBCollection.SUPPORT_KB.value
        )

    print(f"Building KB index from {kb_path}")

    # Load and process documents
    documents = load_markdown_files(kb_path)
    print(f"Loaded {len(documents)} markdown files")

    chunks = split_by_headers(documents)
    print(f"Created {len(chunks)} chunks")

    # Create vectorstore for support_kb collection
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name=KBCollection.SUPPORT_KB.value,
        collection_metadata={"hnsw:space": "cosine"}
    )

    print(f"KB index built and persisted to {persist_dir}")
    return vectorstore


def add_approved_response(
    ticket_id: str,
    question_summary: str,
    response: str,
    category: str,
    tags: list[str],
    approved_by: str,
    approved_at: str,
    persist_dir: str | Path | None = None
) -> bool:
    """
    Add an approved response to the support_kb collection.

    This allows high-quality responses to be indexed and searchable
    for future similar tickets.

    Args:
        ticket_id: Original ticket ID
        question_summary: Generalized version of the question
        response: The approved response text
        category: Category (billing, bug, outage, etc.)
        tags: Searchable tags
        approved_by: Agent ID who approved
        approved_at: ISO timestamp of approval
        persist_dir: Path to ChromaDB persistence directory

    Returns:
        True if successfully added
    """
    persist_dir = Path(persist_dir) if persist_dir else get_chroma_path()
    embeddings = get_embeddings()

    # Load existing vectorstore
    vectorstore = Chroma(
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
        collection_name=KBCollection.SUPPORT_KB.value
    )

    # Format as Q&A document
    content = f"""## {question_summary}

**Category**: {category}
**Tags**: {', '.join(tags)}

### Answer

{response}
"""

    # Create document with metadata
    doc = Document(
        page_content=content,
        metadata={
            "source": "approved_responses",
            "section": category.lower().replace(" ", "-"),
            "ticket_id": ticket_id,
            "tags": ",".join(tags),
            "approved_by": approved_by,
            "approved_at": approved_at,
            "h2": question_summary,
            "h3": "Answer"
        }
    )

    # Add to vectorstore
    vectorstore.add_documents([doc])
    print(f"Added approved response from ticket {ticket_id} to KB")

    return True


# CLI entry point for building index
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build knowledge base index")
    parser.add_argument("--force", action="store_true", help="Force rebuild index")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required")
        exit(1)

    build_kb_index(force_rebuild=args.force)
    print("Done!")


