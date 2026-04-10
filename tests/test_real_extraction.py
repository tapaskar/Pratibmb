"""Integration test: extract pairs from the real corpus."""
import pytest
from pathlib import Path
from pratibmb.store.sqlite import Store
from pratibmb.finetune.pairs import extract_pairs
from pratibmb.finetune.format import format_for_gemma

REAL_DB = Path("data/pratibmb.db")


@pytest.mark.skipif(not REAL_DB.exists(), reason="real DB not available")
def test_real_extraction():
    store = Store(REAL_DB)
    try:
        pairs = extract_pairs(store, self_name="Tapas Kar")
        print(f"\nExtracted {len(pairs)} training pairs")

        assert len(pairs) > 100, f"Expected 100+ pairs, got {len(pairs)}"

        for p in pairs[:3]:
            print(f"  Context: {p['context'][:80]}...")
            print(f"  Prompt: {p['prompt'][:80]}...")
            print(f"  Completion: {p['completion'][:80]}...")
            print(f"  Thread: {p['thread_name']}")
            print()

        # Check formatting works
        records = format_for_gemma(pairs)
        assert len(records) == len(pairs)

        # Show one formatted example
        print("--- Formatted example ---")
        print(records[0]["text"][:500])
    finally:
        store.close()
