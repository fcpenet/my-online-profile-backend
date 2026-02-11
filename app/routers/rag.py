import json

import libsql_client
from fastapi import APIRouter, HTTPException

from app.database import get_client
from app.models import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from app.services.rag_service import (
    chunk_text,
    get_embeddings,
    find_relevant_chunks,
    generate_answer,
)

router = APIRouter()


@router.post("/ingest", status_code=201)
async def ingest_document(body: DocumentIngestRequest) -> DocumentIngestResponse:
    client = get_client()

    # Store the document
    rs = await client.execute(
        libsql_client.Statement(
            "INSERT INTO documents (title, content) VALUES (?, ?) RETURNING id",
            [body.title, body.content],
        )
    )
    doc_id = rs.rows[0][0]

    # Chunk and embed
    chunks = chunk_text(body.content)
    if not chunks:
        return DocumentIngestResponse(
            document_id=doc_id, chunks_created=0, message="Document was empty"
        )

    embeddings = await get_embeddings(chunks)

    # Store embeddings in batch
    statements = [
        libsql_client.Statement(
            "INSERT INTO embeddings (document_id, chunk_index, chunk_text, embedding) "
            "VALUES (?, ?, ?, ?)",
            [doc_id, i, chunk, json.dumps(emb)],
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    await client.batch(statements)

    return DocumentIngestResponse(
        document_id=doc_id,
        chunks_created=len(chunks),
        message="Document ingested successfully",
    )


@router.post("/query")
async def query_document(body: RAGQueryRequest) -> RAGQueryResponse:
    client = get_client()

    # Resolve document_id — use the most recent if not specified
    if body.document_id is None:
        rs = await client.execute(
            "SELECT id FROM documents ORDER BY created_at DESC LIMIT 1"
        )
        if not rs.rows:
            raise HTTPException(status_code=404, detail="No documents found")
        doc_id = rs.rows[0][0]
    else:
        doc_id = body.document_id
        rs = await client.execute(
            libsql_client.Statement(
                "SELECT id FROM documents WHERE id = ?", [doc_id]
            )
        )
        if not rs.rows:
            raise HTTPException(status_code=404, detail="Document not found")

    # Fetch stored embeddings for this document
    rs = await client.execute(
        libsql_client.Statement(
            "SELECT chunk_text, embedding FROM embeddings "
            "WHERE document_id = ? ORDER BY chunk_index",
            [doc_id],
        )
    )
    if not rs.rows:
        raise HTTPException(
            status_code=404, detail="No embeddings found for this document"
        )

    stored = [(row[0], row[1]) for row in rs.rows]

    # Embed the question and find relevant chunks
    query_emb = (await get_embeddings([body.question]))[0]
    relevant_chunks = find_relevant_chunks(query_emb, stored, top_k=3)

    # Generate answer
    answer = await generate_answer(body.question, relevant_chunks)

    return RAGQueryResponse(answer=answer, sources=relevant_chunks)


@router.get("/documents")
async def list_documents():
    client = get_client()
    rs = await client.execute(
        "SELECT id, title, created_at FROM documents ORDER BY created_at DESC"
    )
    return [
        {"id": row[0], "title": row[1], "created_at": row[2]} for row in rs.rows
    ]


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int):
    client = get_client()

    # Delete embeddings first, then the document
    await client.execute(
        libsql_client.Statement(
            "DELETE FROM embeddings WHERE document_id = ?", [document_id]
        )
    )
    rs = await client.execute(
        libsql_client.Statement(
            "DELETE FROM documents WHERE id = ? RETURNING id", [document_id]
        )
    )
    if not rs.rows:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "deleted"}
