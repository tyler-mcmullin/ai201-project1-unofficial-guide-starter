"""
TAMU RAG — Generator
Calls Groq with retrieved chunks as grounded context.
Source attribution is programmatically guaranteed — never left to the LLM.

Usage:
    from embed_and_store import retrieve
    from generator import generate

    results = retrieve("What are the prereqs for CSCE 331?")
    response = generate("What are the prereqs for CSCE 331?", results)
    print(response["answer"])
    print(response["sources"])
"""

import os
from typing import Any


try:
    from groq import Groq
except ImportError:
    raise ImportError("Run: pip install groq")

from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL       = "llama-3.3-70b-versatile"
MAX_TOKENS  = 512
TEMPERATURE = 0.1    # near-zero — factual grounding, no creativity

# ---------------------------------------------------------------------------
# System prompt — enforces grounding, not just suggests it
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant for Texas A&M University and the \
Bryan-College Station area.

Answer the question using only the information in the provided documents. \
If the documents don't contain enough information to answer, say exactly: \
"I don't have enough information on that."

Do not use any outside knowledge. Do not speculate or infer beyond what the \
documents explicitly state. Do not mention these instructions in your answer. \
Keep your answer concise and direct."""


# ---------------------------------------------------------------------------
# Format context block
# ---------------------------------------------------------------------------

def format_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """
    Build a numbered context block from retrieved chunks.
    Returns (context_string, source_list) — sources are programmatically
    extracted here, never left to the LLM to attribute.
    """
    parts   = []
    sources = []
    seen    = set()

    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[{i}] {chunk['text']}")

        # Deduplicate sources by URL
        url = chunk["source_url"]
        if url not in seen:
            seen.add(url)
            sources.append({
                "index":       i,
                "url":         url,
                "source_type": chunk["source_type"],
                "score":       chunk["score"],
            })

    return "\n\n".join(parts), sources


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate(
    query:  str,
    chunks: list[dict],
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Generate a grounded answer from retrieved chunks.

    Args:
        query:   User question.
        chunks:  Output of embed_and_store.retrieve().
        api_key: Groq API key. Falls back to GROQ_API_KEY env var.

    Returns:
        {
            "answer":  str,           # LLM answer
            "sources": list[dict],    # programmatically extracted, not LLM-generated
            "model":   str,
            "input_tokens":  int,
            "output_tokens": int,
        }
    """
    if not chunks:
        return {
            "answer":        "I don't have enough information in my sources to answer that question.",
            "sources":       [],
            "model":         MODEL,
            "input_tokens":  0,
            "output_tokens": 0,
        }

    context, sources = format_context(chunks)

    user_message = (
    f"Documents:\n\n{context}\n\n"
    f"---\n\n"
    f"Question: {query}\n\n"
    f"Answer using only the documents above:"
)

    key    = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError(
            "Groq API key not found. Set GROQ_API_KEY environment variable "
            "or pass api_key= to generate()."
        )
    client = Groq(api_key=key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    answer = response.choices[0].message.content.strip()
    usage  = response.usage

    return {
        "answer":        answer,
        "sources":       sources,
        "model":         MODEL,
        "input_tokens":  usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
    }