#!/usr/bin/env python3
"""Seed Firestore collections with locally ingested knowledge."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.utils import env_loader  # noqa: F401
from app.models import KnowledgeDoc, Playbook, Prospect  # noqa: E402
from app.services import firestore_client  # noqa: E402
from app.services.local_store import (  # noqa: E402
    load_cached_prospects,
    load_local_knowledge,
    load_local_playbooks,
)


def seed_collection(collection: str, documents):
    client = firestore_client.get_firestore_client()
    if client is None:
        print("⚠️ Firestore client unavailable. Configure FIREBASE_SERVICE_ACCOUNT before seeding.")
        return

    batch = client.batch()
    for doc in documents:
        payload = doc.model_dump()
        ref = client.collection(collection).document(payload["id"])
        batch.set(ref, payload)
    batch.commit()
    print(f"✅ Seeded {len(documents)} documents into {collection}")


def main():
    knowledge_docs = load_local_knowledge()
    playbooks = load_local_playbooks()
    prospects = load_cached_prospects()

    if knowledge_docs:
        seed_collection("knowledge_docs", knowledge_docs)
    if playbooks:
        seed_collection("playbooks", playbooks)
    if prospects:
        seed_collection("prospects", prospects)


if __name__ == "__main__":
    main()
