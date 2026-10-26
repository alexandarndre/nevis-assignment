from nevis_search.search.retrievers import highlight, truncate


def test_truncate_cuts_on_a_word_boundary() -> None:
    assert truncate("alpha beta gamma", 12) == "alpha beta…"
    assert truncate("short", 12) == "short"


def test_highlight_escapes_document_html_but_keeps_marks() -> None:
    assert highlight("<script>x</script> ⟦gilts⟧") == "&lt;script&gt;x&lt;/script&gt; <mark>gilts</mark>"
