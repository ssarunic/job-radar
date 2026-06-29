"""Atomic store writes (review P2)."""
from services import store


def test_atomic_write_creates_and_overwrites(tmp_path):
    p = tmp_path / "sub" / "f.jsonl"
    store.atomic_write_text(p, "v1")
    assert p.read_text() == "v1"
    store.atomic_write_text(p, "v2")
    assert p.read_text() == "v2"
    # no stray temp files left behind in the dir
    assert sorted(x.name for x in p.parent.iterdir()) == ["f.jsonl"]
