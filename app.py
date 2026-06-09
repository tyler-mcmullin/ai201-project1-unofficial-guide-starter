"""
TAMU RAG — Gradio Interface
Wires together embed_and_store.retrieve() and generator.generate()
into a simple chat UI.

Usage:
    export GROQ_API_KEY=your_key_here
    python app.py
"""

import os

try:
    import gradio as gr
except ImportError:
    raise ImportError("Run: pip install gradio")

from embedding import retrieve
from generator import generate


# ---------------------------------------------------------------------------
# Core query function
# ---------------------------------------------------------------------------

def answer_question(query: str) -> tuple[str, str]:
    """
    Run the full RAG pipeline for a single query.
    Returns (answer, sources_markdown) for Gradio outputs.
    """
    query = query.strip()
    if not query:
        return "Please enter a question.", ""

    # Retrieve
    chunks = retrieve(query, top_k=5)

    # Generate
    response = generate(query, chunks)

    answer  = response["answer"]
    sources = response["sources"]

    # Format sources as markdown — programmatically built, not LLM-generated
    if sources:
        source_lines = ["**Sources:**"]
        for s in sources:
            label = s["url"].replace("https://", "").split("/")[0]
            source_lines.append(f"- [{label}]({s['url']}) — relevance: {s['score']:.2f}")
        sources_md = "\n".join(source_lines)
    else:
        sources_md = "_No sources retrieved._"

    return answer, sources_md


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

EXAMPLE_QUESTIONS = [
    "What is Professor Paul Taele rated on RateMyProfessor?",
    "What classes are taken in the first semester of a CS degree?",
    "When is tuition due for Summer 2026?",
    "When is the Caneck Culinary Camp?",
    "Why are warnings not given to parking violators?",
]

with gr.Blocks(title="TAMU Unofficial Guide", theme=gr.themes.Soft()) as app:

    gr.Markdown("""
    #TAMU Unofficial Guide
    Ask questions about Texas A&M and the Bryan-College Station area.
    Answers are grounded in official and community sources only.
    """)

    with gr.Row():
        with gr.Column(scale=3):
            query_box = gr.Textbox(
                label="Your question",
                placeholder="",
                lines=2,
            )
            submit_btn = gr.Button("Ask", variant="primary")

        with gr.Column(scale=1):
            gr.Markdown("**Example questions:**")
            for example in EXAMPLE_QUESTIONS:
                gr.Button(example, size="sm").click(
                    fn=lambda q=example: q,
                    outputs=query_box,
                )

    with gr.Row():
        with gr.Column():
            answer_box = gr.Textbox(
                label="Answer",
                lines=6,
                interactive=False,
            )
            sources_box = gr.Markdown(label="Sources")

    # Wire submit button
    submit_btn.click(
        fn=answer_question,
        inputs=query_box,
        outputs=[answer_box, sources_box],
    )

    # Also submit on Enter
    query_box.submit(
        fn=answer_question,
        inputs=query_box,
        outputs=[answer_box, sources_box],
    )

    gr.Markdown("""
    ---
    _Answers are generated from retrieved documents only.
    Always verify important information with official sources._
    """)


if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        print("⚠️  GROQ_API_KEY not set — set it before running:")
        print("   export GROQ_API_KEY=your_key_here")
    app.launch(server_port=7860)