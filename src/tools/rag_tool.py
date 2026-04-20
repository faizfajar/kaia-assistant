import os
import logging
from datetime import datetime
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from flashrank import Ranker, RerankRequest

# Configuration
VECTOR_DB_PATH = "data/vectorstore"
EMBEDDING_MODEL = "models/gemini-embedding-001"
LLM_MODEL = "gemini-2.5-flash"

# Initialize Ranker once
try:
    ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="data/models")
except Exception as e:
    logging.error(f"Ranker initialization failed: {e}")
    ranker = None

def get_vector_db() -> Chroma:
    """Initializes and returns the Chroma vector database instance."""
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    return Chroma(persist_directory=VECTOR_DB_PATH, embedding_function=embeddings)

@tool
def add_document_to_db(text: str, source: str = "manual_ingest") -> None:
    """
    Ingests text into the knowledge base with automatic timestamping.
    """
    vector_db = get_vector_db()
    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    
    chunks = splitter.split_text(text)
    # Adding timestamp to metadata for version tracking
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    documents = [
        Document(page_content=chunk, metadata={"source": source, "created_at": timestamp}) 
        for chunk in chunks
    ]
    
    vector_db.add_documents(documents)
    logging.info(f"Ingested {len(documents)} chunks from {source} at {timestamp}")

def expand_query(original_query: str) -> List[str]:
    """
    Uses LLM to generate search variations for better retrieval coverage.
    """
    try:
        llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)
        prompt = ChatPromptTemplate.from_template(
            "Generate 3 diverse search queries in English and Indonesian "
            "based on this input to improve RAG retrieval: {query}. "
            "Output only the queries, one per line."
        )
        chain = prompt | llm
        response = chain.invoke({"query": original_query})
        return [original_query] + response.content.strip().split("\n")
    except Exception as e:
        logging.error(f"Query expansion failed: {e}")
        return [original_query]

@tool
def search_knowledge(query: str) -> str:
    """
    REQUIRED: Search information about Faiz's background, projects (Phony-API), and technical notes.
    Implements Query Expansion, Similarity Search, and Re-ranking.
    """
    try:
        vector_db = get_vector_db()
        
        # Query Expansion: Get multiple search variations
        expanded_queries = expand_query(query)
        
        # Multi-Query Retrieval: Gather unique candidates
        all_docs = []
        for q in expanded_queries:
            all_docs.extend(vector_db.similarity_search(q, k=5))
            
        # Deduplicate documents based on content
        unique_docs = {doc.page_content: doc for doc in all_docs}.values()
        
        if not unique_docs:
            return "No relevant information found."

        # Re-ranking and Thresholding
        final_docs = re_rank_documents(query, list(unique_docs))
        
        if not final_docs:
            return "Found documents, but none met the relevance threshold."

        # Final Formatting with Metadata
        context_parts = [
            f"[{i+1}] (Source: {d.metadata.get('source')} | Date: {d.metadata.get('created_at')}): {d.page_content}"
            for i, d in enumerate(final_docs)
        ]
        
        return "\n\n".join(context_parts)
        
    except Exception as e:
        logging.error(f"RAG search error: {e}")
        return "System error during knowledge retrieval."

def re_rank_documents(query: str, documents: List[Document]) -> List[Document]:
    """Re-scores documents and filters by a relevance threshold."""
    if not documents or not ranker:
        return documents[:3]

    passages = [{"id": i, "text": doc.page_content, "meta": doc.metadata} for i, doc in enumerate(documents)]
    rerank_request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(rerank_request)

    # Thresholding: Only keep documents with score > 0.4 to prevent hallucinations
    re_ranked_docs = [
        Document(page_content=res['text'], metadata=res['meta'])
        for res in results if res['score'] > 0.4
    ][:3]
        
    return re_ranked_docs