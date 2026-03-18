"""
dock.py - The Local Knowledge Repository (RAG Layer)

The Dock is the strategic lens for the system. It holds chunked
knowledge from markdown files and provides contextual retrieval
for the Compilation stage of the pipeline.

Sprint 3: Local implementation with keyword matching.
Future: Vector database integration (ChromaDB, etc.).
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from engine.profile import get_dock_dir


@dataclass
class Chunk:
    """
    A chunk of knowledge from a source document.
    """
    content: str
    source_file: str
    heading: Optional[str] = None
    chunk_index: int = 0

    def __str__(self) -> str:
        source = Path(self.source_file).stem
        if self.heading:
            return f"[{source}/{self.heading}] {self.content[:100]}..."
        return f"[{source}] {self.content[:100]}..."


@dataclass
class RetrievalResult:
    """
    Result of a dock query with relevance scoring.
    """
    chunk: Chunk
    score: float
    matched_keywords: list[str] = field(default_factory=list)


class LocalDock:
    """
    Local knowledge repository with markdown ingestion and retrieval.

    This class provides the RAG interface that will eventually connect
    to a vector database. For Sprint 3, it uses keyword matching.

    Usage:
        dock = LocalDock()
        dock.ingest()  # Load all markdown from dock/
        context = dock.query_context("revenue goals")
    """

    def __init__(self, dock_dir: Optional[Path] = None):
        self.dock_dir = dock_dir or get_dock_dir()
        self.chunks: list[Chunk] = []
        self.loaded = False

    def ingest(self) -> int:
        """
        Ingest and chunk all markdown files from the dock directory.

        Returns the number of chunks created.
        """
        self.chunks = []

        if not self.dock_dir.exists():
            return 0

        # Find all markdown files
        md_files = list(self.dock_dir.glob("*.md"))

        for md_file in md_files:
            file_chunks = self._chunk_markdown(md_file)
            self.chunks.extend(file_chunks)

        self.loaded = True
        return len(self.chunks)

    def _chunk_markdown(self, filepath: Path) -> list[Chunk]:
        """
        Chunk a markdown file by headings.

        Strategy:
        - Split on ## headings (H2)
        - Each section becomes a chunk
        - Preserve heading context for retrieval
        """
        content = filepath.read_text(encoding="utf-8")
        chunks = []

        # Split by H2 headings
        sections = re.split(r'\n(?=## )', content)

        for idx, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            # Extract heading if present
            heading = None
            heading_match = re.match(r'^##\s+(.+?)(?:\n|$)', section)
            if heading_match:
                heading = heading_match.group(1).strip()

            # Also check for H1 in first section
            if idx == 0:
                h1_match = re.match(r'^#\s+(.+?)(?:\n|$)', section)
                if h1_match:
                    heading = h1_match.group(1).strip()

            chunks.append(Chunk(
                content=section,
                source_file=str(filepath),
                heading=heading,
                chunk_index=idx
            ))

        return chunks

    def query_context(self, query_string: str, top_k: int = 3) -> str:
        """
        Retrieve relevant context for a query.

        Sprint 3: Simple keyword matching against chunks.
        Future: Vector similarity search.

        Args:
            query_string: The query to search for
            top_k: Number of top results to return

        Returns:
            Concatenated context string from relevant chunks
        """
        if not self.loaded:
            self.ingest()

        if not self.chunks:
            return "[DOCK EMPTY] No strategic context available."

        # Extract keywords from query (simple tokenization)
        keywords = self._extract_keywords(query_string)

        if not keywords:
            # No meaningful keywords - return summary
            return self._get_summary()

        # Score each chunk by keyword matches
        results = []
        for chunk in self.chunks:
            score, matched = self._score_chunk(chunk, keywords)
            if score > 0:
                results.append(RetrievalResult(
                    chunk=chunk,
                    score=score,
                    matched_keywords=matched
                ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        # Take top_k results
        top_results = results[:top_k]

        if not top_results:
            # No matches - return summary
            return self._get_summary()

        # Format retrieved context
        return self._format_results(top_results, query_string)

    def _extract_keywords(self, text: str) -> list[str]:
        """
        Extract meaningful keywords from text.

        Filters out common stopwords, short words, and conversational words.

        Sprint 8: Added conversational stopwords as defense-in-depth.
        Even if conversational input accidentally reaches dock.query(),
        these words won't trigger irrelevant context retrieval.
        """
        # Common stopwords to filter
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
            'until', 'while', 'about', 'what', 'which', 'who', 'whom',
            'this', 'that', 'these', 'those', 'am', 'i', 'me', 'my',
            'we', 'our', 'you', 'your', 'he', 'him', 'his', 'she',
            'her', 'it', 'its', 'they', 'them', 'their', 'show', 'get',
            'want', 'help', 'please', 'tell', 'give'
        }

        # Sprint 8: Conversational stopwords (defense-in-depth)
        # These words indicate greetings/small talk and should not trigger
        # dock retrieval even if conversational input reaches this function.
        conversational_stopwords = {
            # Greetings
            'hello', 'hi', 'hey', 'howdy', 'greetings', 'hola',
            'morning', 'afternoon', 'evening', 'night',
            # Acknowledgments
            'thanks', 'thank', 'ok', 'okay', 'sure', 'alright', 'yep',
            'yeah', 'yes', 'no', 'nope', 'got', 'cool', 'great', 'good',
            'nice', 'awesome', 'perfect', 'excellent', 'fine', 'right',
            # Farewells
            'bye', 'goodbye', 'later', 'see', 'talk', 'soon', 'cya',
            # Pleasantries
            'how', 'doing', 'going', 'feeling', 'today', 'hope',
            'glad', 'happy', 'welcome', 'pleasure', 'meet',
            # Conversational fillers
            'well', 'anyway', 'actually', 'basically', 'literally',
            'honestly', 'really', 'pretty', 'quite', 'kind',
            # Commands that don't need dock
            'start', 'begin', 'lets', 'ready', 'go', 'started'
        }

        stopwords.update(conversational_stopwords)

        # Tokenize and filter
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        return keywords

    def _score_chunk(self, chunk: Chunk, keywords: list[str]) -> tuple[float, list[str]]:
        """
        Score a chunk based on keyword matches.

        Returns (score, list of matched keywords).
        """
        chunk_text = chunk.content.lower()
        heading_text = (chunk.heading or "").lower()

        matched = []
        score = 0.0

        for keyword in keywords:
            # Check content
            content_count = chunk_text.count(keyword)
            if content_count > 0:
                matched.append(keyword)
                score += content_count * 1.0

            # Bonus for heading match
            if keyword in heading_text:
                score += 2.0

        return score, matched

    def _get_summary(self) -> str:
        """
        Return a summary of all dock content when no specific match.
        """
        if not self.chunks:
            return "[DOCK EMPTY]"

        # Get unique source files
        sources = set(Path(c.source_file).stem for c in self.chunks)

        # Get all headings
        headings = [c.heading for c in self.chunks if c.heading]

        summary = "[DOCK CONTEXT]\n"
        summary += f"Sources: {', '.join(sources)}\n"
        summary += f"Topics: {', '.join(headings[:5])}"

        return summary

    def _format_results(self, results: list[RetrievalResult], query: str) -> str:
        """
        Format retrieval results as context string.
        """
        output = f"[DOCK CONTEXT for: '{query}']\n"
        output += f"Retrieved {len(results)} relevant chunk(s):\n\n"

        for i, result in enumerate(results, 1):
            source = Path(result.chunk.source_file).stem
            heading = result.chunk.heading or "General"
            keywords = ", ".join(result.matched_keywords) if result.matched_keywords else "summary"

            output += f"--- [{i}] {source} / {heading} (matched: {keywords}) ---\n"
            # Truncate long chunks
            content = result.chunk.content
            if len(content) > 500:
                content = content[:500] + "..."
            output += content + "\n\n"

        return output.strip()

    def list_sources(self) -> list[str]:
        """List all loaded source files."""
        if not self.loaded:
            self.ingest()
        return list(set(c.source_file for c in self.chunks))

    def get_chunk_count(self) -> int:
        """Return total number of chunks."""
        return len(self.chunks)


# Module-level singleton for shared access
_dock_instance: Optional[LocalDock] = None


def get_dock() -> LocalDock:
    """Get the shared LocalDock instance."""
    global _dock_instance
    if _dock_instance is None:
        _dock_instance = LocalDock()
        _dock_instance.ingest()
    return _dock_instance


def query_dock(query: str, top_k: int = 3) -> str:
    """
    Convenience function to query the dock.

    This is the primary interface for the pipeline's Compilation stage.
    """
    dock = get_dock()
    return dock.query_context(query, top_k)
