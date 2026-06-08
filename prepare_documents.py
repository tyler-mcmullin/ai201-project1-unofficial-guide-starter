"""
TAMU RAG — Document Preparation
Loads local PDFs and TXTs plus scraped URLs, cleans them,
and writes chunks to a JSONL file for later embedding.

Usage:
    python prepare_documents.py

Output:
    chunks.jsonl  — one JSON object per line, each a chunk ready for embedding
"""

import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# PDF reading
try:
    import pdfplumber
except ImportError:
    raise ImportError("Run: pip install pdfplumber")

# HTML scraping
import requests
from bs4 import BeautifulSoup

# Dynamic scraping
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise ImportError("Run: pip install playwright && playwright install chromium")


# ---------------------------------------------------------------------------
# Configuration — edit this to match your documents
# ---------------------------------------------------------------------------

DOCUMENTS = [
    # Local PDFs
    {"type": "pdf",  "path": "documents/BS-Computer Science.pdf",
     "url": "https://catalog.tamu.edu/"},

    # Local TXT files
    {"type": "txt",  "path": "documents/academic-calendar.txt",
     "url": "https://calendar.tamu.edu/registrar/all"},
     {"type": "txt",  "path": "documents/cstx-events.txt",
     "url": "https://visit.cstx.gov/"},
     {"type": "txt",  "path": "documents/parking-faqs.txt",
     "url": "https://transport.tamu.edu/Parking/faqparking.aspx"},
     {"type": "txt",  "path": "documents/tuition-due-dates.txt",
     "url": "https://www.tamu.edu/admissions/index.html"},

    # Dynamic URLs (JS-rendered)
    {"type": "dynamic", "url": "https://www.thebatt.com/news",
     "wait_selector": "article"},
    {"type": "dynamic", "url": "https://12thman.com/",
     "wait_selector": "article, .story"},

    # RateMyProfessor — CS department
    {"type": "rmp",
     "url": "https://www.ratemyprofessors.com/search/professors/1003"},
]

# Chunking config (tuned for all-MiniLM-L6-v2's 256-token limit)
STANDARD_CHUNK_SIZE = 150   # tokens
STANDARD_OVERLAP    = 30    # tokens
OUTPUT_FILE         = "chunks.jsonl"
HEADERS             = {"User-Agent": "Mozilla/5.0 (research bot)"}
RATE_LIMIT          = 1.5


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    text:        str
    source_url:  str
    source_type: str    # "atomic" or "standard"
    chunk_index: int
    metadata:    dict


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

NOISE_TAGS = ["nav", "header", "footer", "script", "style", "aside", "noscript"]


def clean_text(text: str) -> str:
    """Normalize whitespace and remove empty lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text  = "\n".join(lines)
    text  = re.sub(r'\n{3,}', '\n\n', text)   # collapse 3+ blank lines to 2
    return text.strip()


def html_to_text(html: str) -> str:
    """Strip HTML tags and boilerplate, return clean text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    main = (
        soup.find("main") or
        soup.find("article") or
        soup.find(id="content") or
        soup.find(class_="content") or
        soup.body
    )
    return clean_text(main.get_text("\n") if main else "")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_pdf(path: str) -> str:
    """Extract text from a local PDF using pdfplumber."""
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return clean_text(text)


def load_txt(path: str) -> str:
    """Load a local plain text file."""
    return clean_text(Path(path).read_text(encoding="utf-8"))


def load_static(url: str) -> str:
    """Scrape a static HTML page."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return html_to_text(resp.text)


def load_dynamic(url: str, wait_selector: str = "main") -> str:
    """Scrape a JS-rendered page using Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda r: r.abort())
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        try:
            page.wait_for_selector(wait_selector, timeout=8000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    return html_to_text(html)


def load_rmp(url: str) -> list[dict]:
    """
    Scrape RateMyProfessor professor listing.
    Returns list of review dicts: {professor, department, course, text}
    """
    reviews = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}", lambda r: r.abort())
        page.goto(url, wait_until="domcontentloaded", timeout=20000)

        # Click "load more" until it disappears or we hit the limit
        max_clicks = 10
        clicks = 0
        while clicks < max_clicks:
            try:
                load_more = page.query_selector("button[class*='PaginationButton']")
                if not load_more:
                    break
                load_more.click()
                page.wait_for_timeout(2000)
                clicks += 1
            except Exception:
                break

        # Collect professor cards
        for card in page.query_selector_all("[class*='TeacherCard']"):
            name_el = card.query_selector("[class*='CardName']")
            dept_el = card.query_selector("[class*='CardSchool'] span:last-child")
            name    = name_el.inner_text().strip() if name_el else ""
            dept    = dept_el.inner_text().strip() if dept_el else ""

            # Each card rating snippet as a lightweight review
            rating_el  = card.query_selector("[class*='CardNumRating']")
            comment_el = card.query_selector("[class*='CardFeedback']")
            rating     = rating_el.inner_text().strip() if rating_el else ""
            comment    = comment_el.inner_text().strip() if comment_el else ""

            if name and comment:
                reviews.append({
                    "professor":  name,
                    "department": dept,
                    "course":     "",
                    "text":       f"Rating: {rating}. {comment}",
                })

        browser.close()
    return reviews


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Sliding window split that prefers sentence/paragraph boundaries."""
    char_limit   = chunk_size * 4
    char_overlap = overlap * 4
    sentences    = re.split(r'(?<=[.!?])\s+|\n{2,}', text.strip())

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        slen = len(sentence)
        if current_len + slen > char_limit and current:
            chunks.append(" ".join(current))
            while current and current_len - len(current[0]) > char_overlap:
                current_len -= len(current[0])
                current.pop(0)
        current.append(sentence)
        current_len += slen

    if current:
        chunks.append(" ".join(current))

    return chunks


def make_standard_chunks(text: str, url: str) -> list[Chunk]:
    """200-token sliding window for all non-atomic sources."""
    return [
        Chunk(
            text=t, source_url=url, source_type="standard",
            chunk_index=i, metadata={},
        )
        for i, t in enumerate(split_into_chunks(text, STANDARD_CHUNK_SIZE, STANDARD_OVERLAP))
    ]


def make_review_chunks(reviews: list[dict], url: str) -> list[Chunk]:
    """One chunk per review — atomic."""
    chunks = []
    for i, r in enumerate(reviews):
        header = f"Professor: {r['professor']} | Dept: {r['department']} | Course: {r['course']}\n"
        chunks.append(Chunk(
            text=header + r["text"],
            source_url=url, source_type="atomic",
            chunk_index=i,
            metadata={"professor": r["professor"], "department": r["department"]},
        ))
    return chunks

def hard_split(chunk: Chunk, max_tokens: int = 256) -> list[Chunk]:
    """Recursively split any chunk exceeding max_tokens."""
    if len(chunk.text) // 4 <= max_tokens:
        return [chunk]
    mid = len(chunk.text) // 2
    left  = Chunk(chunk.text[:mid], chunk.source_url, chunk.source_type,
                  chunk.chunk_index, chunk.metadata)
    right = Chunk(chunk.text[mid:], chunk.source_url, chunk.source_type,
                  chunk.chunk_index + 1, chunk.metadata)
    return hard_split(left, max_tokens) + hard_split(right, max_tokens)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_document(doc: dict) -> list[Chunk]:
    dtype = doc["type"]
    url   = doc["url"]

    print(f"  Loading [{dtype}] {url or doc.get('path')}")

    if dtype == "pdf":
        text = load_pdf(doc["path"])
        return make_standard_chunks(text, url)

    if dtype == "txt":
        text = load_txt(doc["path"])
        return make_standard_chunks(text, url)

    if dtype == "static":
        text = load_static(url)
        time.sleep(RATE_LIMIT)
        return make_standard_chunks(text, url)

    if dtype == "dynamic":
        text = load_dynamic(url, doc.get("wait_selector", "main"))
        return make_standard_chunks(text, url)

    if dtype == "rmp":
        reviews = load_rmp(url)
        return make_review_chunks(reviews, url)

    raise ValueError(f"Unknown document type: {dtype}")


def main():
    all_chunks: list[Chunk] = []

    for doc in DOCUMENTS:
        try:
            chunks = process_document(doc)
            print(f"    → {len(chunks)} chunks")
            for chunk in chunks:
                all_chunks.extend(hard_split(chunk))
        except Exception as e:
            print(f"    ✗ Failed: {e}")

    # Write to JSONL
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(asdict(chunk)) + "\n")

    print(f"\nTotal chunks: {len(all_chunks)}")
    print(f"Saved to: {OUTPUT_FILE}")

    # Quick size check
    oversized = [c for c in all_chunks if estimate_tokens(c.text) > 256]
    if oversized:
        print(f"⚠️  {len(oversized)} chunks exceed 256 tokens — lower STANDARD_CHUNK_SIZE")
    else:
        print("All chunks within 256-token model limit ✓")


if __name__ == "__main__":
    print("Preparing documents…\n")
    main()