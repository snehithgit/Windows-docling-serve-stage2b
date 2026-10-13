# Docling Stage-2B — Windows offline installer

This is the **separate** Windows packaging repository for [snehithgit/docling-stage2b](https://github.com/snehithgit/docling-stage2b) and the official [Docling Serve](https://github.com/docling-project/docling-serve).

**Goal:** a single `Docling-Stage2B-Offline-Setup.exe` that installs on Windows 10/11 x64 **without internet, Docker, WSL or a separate Python installation**. The build machine uses the internet once to fetch dependencies and models.

## Download the EXE

[Open the Windows installer workflow](https://github.com/snehithgit/Windows-docling-serve-stage2b/actions/workflows/build-windows.yml). Select a **successful** run and download the `Docling-Stage2B-Windows-x64-Offline` Actions artifact. Extract its ZIP; the installer EXE is inside. Only a passed run is usable; until then, this repository contains build tooling, not a proven installer.

## What the installer includes

| Component | Local endpoint |
| --- | --- |
| Official Docling Serve and its model assets | 127.0.0.1:5001 |
| Existing Stage-2B FastAPI backend, UI, processing, review and retrieval | 127.0.0.1:8080 |
| BAAI/bge-small-en-v1.5 embedding model and API | 127.0.0.1:8090/embed |
| Desktop shell | Native WebView2 window |

Includes relocatable Python 3.11, CPU-only PyTorch, Docling layout/table/picture/OCR models (English), the Stage-3 tokenizer, and Microsoft's **offline** WebView2 installer. A small Windows launcher starts/stops all services as child processes and creates a new user data area without touching the original repository.

First-run files are in `%LOCALAPPDATA%\DoclingStage2B\`, including `input`, `converted`, `processed`, `db`, `logs`, and `config.yaml`. Settings and documents remain there when the program is reinstalled.

**Fully local without internet:** bundled document conversion, layout, English OCR, table extraction, chunking, lexical search, and BGE-based vector retrieval.

**Not included:** a local vision LLM/llama.cpp and its weights. Stage-2B model-driven text/vision verification, Colab/Groq, and LLM answer generation require a separate connected or local inference provider. Additional OCR languages and VLM options may require extra offline model packs. This installer guarantees no first-run model download by setting Hugging Face offline flags.

## Build and verification

GitHub Actions runs `windows/build.ps1` on `windows-latest`: clones the upstream Stage-2B commit `b23ed0bd81b9f8cad153f9d0d3582e7166d7a611`, assembles the portable runtime, downloads model files, builds the desktop launcher, and runs `windows/smoke_test.py` **with Hugging Face offline mode enabled**. The smoke test must start Docling Serve, the local embedding service and Stage-2B, embed a query, convert a generated PDF to ZIP, and run the Stage-3 HybridChunker endpoint. Only then does it compile the Inno Setup installer.

The build may be several gigabytes. Storage or artifact limits may require a smaller model profile if a CI run fails. A passing build alone does not replace an actual offline installation test on a clean Windows PC.

## Warnings and migration

Keep a backup before copying old Stage-2B databases or output folders. **Do not copy the original Linux config.yaml** without converting its paths and endpoints. The installer is unsigned, so Windows SmartScreen may display a warning. Verify the SHA256 included with Actions artifacts. Review third-party licenses before redistributing installer binaries.
