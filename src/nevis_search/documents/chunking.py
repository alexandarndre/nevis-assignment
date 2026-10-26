import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n\s*\n")


def split_sentences(text: str) -> list[str]:
    return [sentence for part in _SENTENCE_BOUNDARY.split(text) if (sentence := " ".join(part.split())) != ""]


def chunk_text(text: str, max_words: int) -> list[str]:
    pieces = [
        " ".join(words[start : start + max_words])
        for sentence in split_sentences(text)
        for words in [sentence.split()]
        for start in range(0, len(words), max_words)
    ]
    chunks: list[list[str]] = []
    current: list[str] = []
    for piece in pieces:
        if len(current) > 0 and _word_count([*current, piece]) > max_words:
            chunks.append(current)
            current = [current[-1]] if _word_count([current[-1], piece]) <= max_words else []
        current.append(piece)
    if len(current) > 0:
        chunks.append(current)
    return [" ".join(chunk) for chunk in chunks]


def _word_count(pieces: list[str]) -> int:
    return sum(len(piece.split()) for piece in pieces)
