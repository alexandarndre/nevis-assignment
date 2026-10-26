from pydantic import AfterValidator


def _reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("text must not contain NUL characters")
    return value


NoNul = AfterValidator(_reject_nul)
