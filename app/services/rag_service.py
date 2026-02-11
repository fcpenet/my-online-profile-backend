import json
import math
import os

from openai import AsyncOpenAI

_openai_client = None


def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai_client


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks, preferring paragraph then sentence boundaries."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= chunk_size:
            current += ("\n\n" + para if current else para)
        else:
            if current:
                chunks.append(current)
            if len(para) > chunk_size:
                # Split long paragraphs by sentences
                sentences = para.replace(". ", ".\n").split("\n")
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current += (" " + sent if current else sent)
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para

    if current:
        chunks.append(current)

    # Add overlap by prepending tail of previous chunk
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prefix = chunks[i - 1][-overlap:]
            overlapped.append(prefix + " " + chunks[i])
        chunks = overlapped

    return chunks


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-small."""
    client = _get_openai()
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_relevant_chunks(
    query_embedding: list[float],
    stored: list[tuple[str, str]],  # list of (chunk_text, embedding_json)
    top_k: int = 3,
) -> list[str]:
    """Return the top-k most similar chunk texts."""
    scored = []
    for chunk_text, emb_json in stored:
        emb = json.loads(emb_json)
        score = cosine_similarity(query_embedding, emb)
        scored.append((score, chunk_text))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:top_k]]


async def generate_answer(question: str, context_chunks: list[str]) -> str:
    """Generate an answer using GPT-4o-mini grounded on the provided context."""
    client = _get_openai()
    context = "\n---\n".join(context_chunks)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer the question based ONLY "
                    "on the provided context. If the context doesn't contain the "
                    "answer, say so."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n---\n{context}\n---\n\nQuestion: {question}",
            },
        ],
    )
    return response.choices[0].message.content
