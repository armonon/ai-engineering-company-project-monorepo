"""Load TrackFlow's approved policy documents into Qdrant."""

from trackflow_process.rag import setup

if __name__ == "__main__":
    result = setup()
    print(
        f"Loaded {result['chunks']} chunks into {result['collection']} "
        f"({result['dimensions']} dimensions)."
    )
