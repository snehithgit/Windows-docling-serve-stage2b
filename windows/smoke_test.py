"""Integration gate: verifies that the bundled services work with all network disabled.

The build MUST fail instead of publishing a broken offline installer.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import fitz
import httpx

PAYLOAD = Path(sys.argv[1]).resolve()
if not (PAYLOAD / "runtime" / "python.exe").is_file():
    raise SystemExit("Bundled Python executable missing")
sys.path.insert(0, str(PAYLOAD))
sys.path.insert(0, str(PAYLOAD / "stage2b"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from windows import launcher
from app.config import AppConfig
from app.docling_client import DoclingClient
from app.archive import select_docling_document


async def finish(client: DoclingClient, task_id: str, name: str) -> None:
    expiry = time.monotonic() + 360
    while time.monotonic() < expiry:
        status = await client.poll(task_id)
        state = str(status.get("task_status", "")).lower()
        if state in {"success", "completed", "done"}:
            return
        if state in {"failure", "failed", "error"}:
            raise AssertionError(name + " failed: " + json.dumps(status)[:1200])
        await asyncio.sleep(2)
    raise TimeoutError(name + " exceeded six-minute test deadline")


async def verify_pdf_and_chunking() -> None:
    config = AppConfig()
    config.docling_url = "http://127.0.0.1:5001"
    client = DoclingClient(lambda: config)
    with tempfile.TemporaryDirectory(prefix="docling-win-smoke-") as folder:
        pdf_path = Path(folder) / "test-manual.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "HYDRAULIC PUMP - SYSTEM TEST", fontsize=14)
        page.insert_text((72, 102), "The pressure setting is 210 bar. Check the relief valve.", fontsize=11)
        doc.save(pdf_path)
        doc.close()
        conversion_id = await client.submit(pdf_path, to_formats=["md", "json"])
        await finish(client, conversion_id, "PDF conversion")
        conversion = await client.result(conversion_id)
        if not zipfile.is_zipfile(io.BytesIO(conversion.content)):
            raise AssertionError("Docling did not return the requested ZIP")
        with zipfile.ZipFile(io.BytesIO(conversion.content)) as archive:
            doc_json, filename = select_docling_document(archive)
            if not doc_json.get("texts"):
                raise AssertionError("No texts found in converted Docling JSON")
            raw_doc = archive.read(filename)
        chunk_id = await client.submit_hybrid_chunks_json(
            filename="test-manual.json", content=raw_doc,
            max_tokens=256, tokenizer="sentence-transformers/all-MiniLM-L6-v2",
        )
        await finish(client, chunk_id, "Stage-3 HybridChunker")
        chunk_response = await client.result(chunk_id)
        if not chunk_response.content:
            raise AssertionError("HybridChunker returned empty result")


def test_embedding() -> None:
    with httpx.Client(timeout=45) as client:
        response = client.post("http://127.0.0.1:8090/embed",
                               json={"inputs": ["hydraulic pressure relief valve"]})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or len(rows) != 1 or len(rows[0]) != 384:
            raise AssertionError("Local BGE embedding endpoint returned wrong shape")


def main() -> None:
    print("Smoke testing WITH HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1", flush=True)
    try:
        launcher.start_services(lambda msg: print(msg, flush=True))
        test_embedding()
        asyncio.run(verify_pdf_and_chunking())
        print("PASS: Docling Serve, Stage-2B UI, BGE embeddings, PDF ZIP conversion and HybridChunker", flush=True)
    finally:
        launcher.stop_services()


if __name__ == "__main__":
    main()
