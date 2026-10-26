from nevis_search.documents.chunking import chunk_text, split_sentences


def test_split_sentences_handles_punctuation_paragraphs_and_whitespace() -> None:
    text = "First sentence.  Second one!\n\nThird\nline continues?   Last"
    assert split_sentences(text) == ["First sentence.", "Second one!", "Third line continues?", "Last"]


def test_split_sentences_of_blank_text_is_empty() -> None:
    assert split_sentences("  \n\n  ") == []


def test_chunk_text_keeps_short_text_in_one_chunk() -> None:
    assert chunk_text("One. Two. Three.", max_words=50) == ["One. Two. Three."]


def test_chunk_text_packs_sentences_and_overlaps_by_one_sentence() -> None:
    sentences = [f"Sentence number {i} has five words." for i in range(6)]
    chunks = chunk_text(" ".join(sentences), max_words=12)
    assert all(len(chunk.split()) <= 12 for chunk in chunks)
    assert chunks[0] == f"{sentences[0]} {sentences[1]}"
    assert chunks[1].startswith(sentences[1])
    assert chunks[-1].endswith(sentences[-1])


def test_chunk_text_splits_a_sentence_longer_than_the_limit() -> None:
    chunks = chunk_text(" ".join(f"w{i}" for i in range(25)), max_words=10)
    assert [len(chunk.split()) for chunk in chunks] == [10, 10, 5]
