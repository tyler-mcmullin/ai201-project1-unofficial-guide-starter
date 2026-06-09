# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

This domain provides a mix of objective information through sports scores, course offerings, and university scheduling but also provides subjective context 
for the information through forum pages. One could use the official course catalog to find which course they need to fulfil a degree plan, but the other sources can narrow down a wide range of choices into preferable outcomes. Official pages are often deep and take time to navigate, which can be inconvenient for someone trying to take a cursory look. 

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | RateMyProfessor | Professor Paul Taele RateMyProfessor Page Text File| paul-taele-rmp.txt |
| 2 | TexAgs | News site for A&M football | https://texags.com/aggie-football |
| 3 | r/aggies | Subreddit for Texas A&M | | https://www.reddit.com/r/aggies/ |
| 4 | TAMU Registrar | Summer Academic Calendar | academic-calendar.txt |
| 5 | The Battalion | Student newspaper for campus news | https://www.thebatt.com/news |
| 6 | TAMU Course Catalog | Offician BS - Computer Science Degree Plan | BS-Computer Science.pdf |
| 7 | 12thman | TAMU Athletics news source | https://12thman.com/ |
| 8 | TAMU Transportation | Official FAQs page for university parking and transportation | parking-faqs.txt |
| 9 | TAMU.edu | Upcoming Tuition Due Dates | tuition-due-dates.txt |
| 10 | Visit College Station Events | City page about events within College Station | cstx-events.txt |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**

Chunk size was set to be 175 tokens in order to stay within the bounds of the embedder and give enough headspace for the overlap.
Most pieces of data are relatively small meaning that I did not need much more than this.

**Overlap:**

An overlap of 30 tokens was set to stay within the limits of the embedder. Most questions that I asked were about specific dates which led
to some cutoff between chunks. However, the overlap is able to go back and forth to ensure that the data is collected.

**Why these choices fit your documents:**

This chunk organization fit my data well because I ended up breaking down many of the sources. Large, formatted HTML files, JavaScript websites, and PDFs proved to be difficult to extract data from in a simple manner. As a result of the human effort, data retrieval was a more streamlined process.

**Final chunk count:**

69

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:**

all-MiniLM-L6-v2

**Production tradeoff reflection:**

Some tradeoffs were made with this model since the chunk size it supports is relatively small. For larger, dense documents it felt that a larger one may have been useful. However, being a free to use product makes this an ideal choice. Additionally, with much of my data being edited for content, the smaller chunk size made less of an impact. 

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

The system is instructed to not pull from outside sources and admit when it does not know the answer. Another contstrain given is that response size
is limited to 512 tokens to give the model less room for hallucination. Also, the model only uses information from the sources.

**How source attribution is surfaced in the response:**

Source attribution is done through the model by showing the sources it drew from below the response. Additionally, it shows the relevance scores for the information drawn from these sources.

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What is Professor Paul Taele rated on RateMyProfessor? | 4.6 | The professor's rating is 4.6 | Relevant | Accurate
| 2 | What classes should be taken the first semester for a computer science degree? | CHEM 107 and 117, ENGL 103, ENGR 102, MATH 151 | Relevant | Inaccurate
| 3 | When is tuition due for Summer 2026? | May 21st, 2026 | Relevant | Accurate
| 4 | When is the Caneck Culinary camp? | Jun 8th to Jul 24th | Relevant | Partially accurate
| 5 | Why are warnings not given to parking violators? | Warnings do not work| Partially relevant | Partially accurate

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**

The main question that the system kept getting wrong was "What classes should be taken during the first semester for a computer science degree?"

**What the system returned:**

The system kept specifically returning the requirements for the second semester.

**Root cause (tied to a specific pipeline stage):**

I am not entirely sure what led to this issue. At first I had the course catalog in PDF form and assumed that there was an issue with the data scraping.
I then converted it to plain text. That also did not work. I then formatted the plaintext further to ensure that all information was on one line for the
information that I specifically wanted. I even tried changing the chunk size and re-embedding after removing my local ChromaDB. 

**What you would change to fix it:**

I am honestly not sure what the fix is. Likely something to do with how the data is embedded or even changing the query could help. 
The answer to this question is definitely one I will be paying close attention to in later modues. 

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

Planning helped me out by giving me reachable goals during my development. By having a clear path forward, it made reaching the next step seem more achievable
which in turn led to the completion of the project. 

**One way your implementation diverged from the spec, and why:**

My implementation completely diverged from the spec because I was initially unsure of what this whole process would look like. I prompted AI for some pointers and received an overly complicated solution that was outside the scope of this project. I was intimidated at first, but simplifying the project somewhat and breaking certain steps down made it achievable. 

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*

I asked the AI to give me a chunker that would chunk different files in different ways based on the file being read.

- *What it produced:*

It produced a chunker that would create variable size chunks depending on the specific document being read.

- *What I changed or overrode:*

I ended up changing this specification to keeping consistently sized chunks and collecting the data through varying means. Some semantic meaning was lost in the prompt.



**Instance 2**

- *What I gave the AI:*

I asked the AI to link the embedded information and generator to the app that used Gradio. 

- *What it produced:*

It produced an easy to use, basic local webpage I could use to test the model and my questions. It was formatted well and included buttons with my sample queries ready to go.

- *What I changed or overrode:*

I was honestly impressed with what it came up with so quickly, however some of the limitations of the AI came through and the importance of staying vigilant
when coding with AI was made clear. In this case, it was harmless but I could see larger implications. One of the queries it suggested and even had as a 
"suggested prompt" that started in the text box was an older question that I had since changed to something else more focused on the scope of my sources.
This stressed the importance of reviewing generated code for imperfections or artifacts from older prompts. 
