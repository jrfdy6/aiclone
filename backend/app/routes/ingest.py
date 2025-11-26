import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.embedders import embed_texts
from app.services.memory_service import log_ingest_job, save_chunk
from app.services.parsers import pdf_parser, pptx_parser
from app.utils.chunker import chunk_text


router = APIRouter()


SUPPORTED_TEXT_TYPES = {"text/plain", "application/json"}

# Valid persona section tags for weighted retrieval
VALID_PERSONA_TAGS = {
    "VOICE_PATTERNS",
    "BIO_FACTS", 
    "VENTURES",
    "EXPERIENCES",
    "PHILOSOPHY",
    "LINKEDIN_EXAMPLES",
    "STRUGGLES",
}


def _parse_tagged_markdown(text: str) -> List[Tuple[str, str, str]]:
    """
    Parse markdown with ## SECTION_NAME headers into tagged chunks.
    
    Returns list of tuples: (section_tag, subsection_name, content)
    """
    lines = text.split('\n')
    chunks = []
    current_tag = "UNTAGGED"
    current_subsection = ""
    current_content = []
    
    for line in lines:
        # Check for main section header (## ALL_CAPS)
        section_match = re.match(r'^## ([A-Z][A-Z_]+)$', line.strip())
        if section_match:
            # Save previous chunk if exists
            if current_content:
                content_text = '\n'.join(current_content).strip()
                if content_text:
                    chunks.append((current_tag, current_subsection, content_text))
            
            current_tag = section_match.group(1)
            if current_tag not in VALID_PERSONA_TAGS:
                current_tag = "UNTAGGED"
            current_subsection = ""
            current_content = []
            continue
        
        # Check for subsection header (### Title)
        subsection_match = re.match(r'^### (.+)$', line.strip())
        if subsection_match:
            # Save previous chunk if exists
            if current_content:
                content_text = '\n'.join(current_content).strip()
                if content_text:
                    chunks.append((current_tag, current_subsection, content_text))
            
            current_subsection = subsection_match.group(1)
            current_content = []
            continue
        
        # Skip horizontal rules and empty structural elements
        if line.strip() == '---' or line.strip() == '':
            if current_content and current_content[-1] != '':
                current_content.append('')  # Preserve paragraph breaks
            continue
        
        current_content.append(line)
    
    # Don't forget the last chunk
    if current_content:
        content_text = '\n'.join(current_content).strip()
        if content_text:
            chunks.append((current_tag, current_subsection, content_text))
    
    return chunks


def _chunk_tagged_content(tagged_chunks: List[Tuple[str, str, str]], max_chunk_size: int = 600) -> List[Dict[str, Any]]:
    """
    Process tagged chunks, splitting large ones while preserving tags.
    
    Returns list of dicts with: text, tag, subsection
    """
    result = []
    
    for tag, subsection, content in tagged_chunks:
        words = content.split()
        
        if len(words) <= max_chunk_size:
            # Small enough, keep as single chunk
            result.append({
                "text": content,
                "tag": tag,
                "subsection": subsection,
            })
        else:
            # Split into smaller chunks, all with same tag
            start = 0
            chunk_num = 0
            while start < len(words):
                end = min(len(words), start + max_chunk_size)
                chunk_text = ' '.join(words[start:end])
                result.append({
                    "text": chunk_text,
                    "tag": tag,
                    "subsection": f"{subsection} (part {chunk_num + 1})" if subsection else f"part {chunk_num + 1}",
                })
                start = end
                chunk_num += 1
    
    return result


def _load_metadata(metadata_raw: Optional[str]) -> Dict[str, Any]:
    if not metadata_raw:
        return {}
    try:
        return json.loads(metadata_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc


def _extract_text(
    temp_path: Path,
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str],
    source_type: str,
) -> str:
    suffix = Path(filename).suffix.lower()

    if source_type == "pdf" or suffix == ".pdf" or content_type == "application/pdf":
        return pdf_parser.extract_text_from_pdf(temp_path)
    if source_type in {"pptx", "slides"} or suffix in {".ppt", ".pptx"}:
        return pptx_parser.extract_text_from_pptx(temp_path)
    if content_type in SUPPORTED_TEXT_TYPES:
        return file_bytes.decode("utf-8", errors="ignore")

    # Fallback: attempt utf-8 decode
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Unsupported file type for ingestion.")


def _build_base_metadata(
    user_id: str,
    filename: str,
    source_type: str,
    extra_metadata: Dict[str, Any],
    ingest_job_id: str,
    file_id: str,
) -> Dict[str, Any]:
    timestamp = datetime.utcnow().isoformat() + "Z"
    metadata = {
        "source": filename,
        "source_type": source_type,
        "source_id": file_id,
        "file_name": filename,
        "file_type": source_type,
        "upload_timestamp": timestamp,
        "ingest_job_id": ingest_job_id,
        **extra_metadata,
    }
    metadata.setdefault("extra_tags", extra_metadata.get("extra_tags", []))
    metadata.setdefault("topic", extra_metadata.get("topic"))
    metadata.setdefault("user_id", user_id)
    return metadata


@router.post("/upload")
async def upload_file(
    user_id: str = Form(...),
    source_type: str = Form("unknown"),
    metadata: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extra_metadata = _load_metadata(metadata)

    fd, tmp_path_str = tempfile.mkstemp(suffix=Path(file.filename or "").suffix)
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(file_bytes)

        text = _extract_text(
            tmp_path,
            file_bytes,
            file.filename or "upload",
            file.content_type,
            source_type,
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    ingest_job_id = f"ingest_{uuid.uuid4().hex}"
    file_id = f"file_{uuid.uuid4().hex}"

    base_metadata = _build_base_metadata(
        user_id=user_id,
        filename=file.filename or "upload",
        source_type=source_type,
        extra_metadata=extra_metadata,
        ingest_job_id=ingest_job_id,
        file_id=file_id,
    )

    # Check if this is a tagged persona file (has ## SECTION_NAME headers)
    is_tagged_persona = bool(re.search(r'^## [A-Z][A-Z_]+$', text, re.MULTILINE))
    
    saved_chunk_ids: List[str] = []
    tag_counts: Dict[str, int] = {}
    
    if is_tagged_persona and source_type in ("persona", "style_guide"):
        # Use section-aware chunking for persona files
        print(f"[ingest] Detected tagged persona file, using section-aware chunking", flush=True)
        
        tagged_chunks = _parse_tagged_markdown(text)
        processed_chunks = _chunk_tagged_content(tagged_chunks)
        
        if not processed_chunks:
            raise HTTPException(status_code=400, detail="No textual content could be extracted from the file.")
        
        # Extract just the text for embedding
        chunk_texts = [c["text"] for c in processed_chunks]
        embeddings = embed_texts(chunk_texts)
        
        for idx, (chunk_data, embedding) in enumerate(zip(processed_chunks, embeddings)):
            chunk_metadata = {
                **base_metadata,
                "chunk_index": idx,
                "persona_tag": chunk_data["tag"],
                "subsection": chunk_data["subsection"],
            }
            
            # Track tag counts for logging
            tag = chunk_data["tag"]
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # Add tag to extra_tags for retrieval
            tags_list = list(chunk_metadata.get("extra_tags", []))
            tags_list.append(chunk_data["tag"])
            if chunk_data["subsection"]:
                tags_list.append(chunk_data["subsection"])
            
            chunk_id = save_chunk(
                user_id=user_id,
                text=chunk_data["text"],
                embedding=embedding,
                metadata=chunk_metadata,
                tags=tags_list,
            )
            saved_chunk_ids.append(chunk_id)
        
        print(f"[ingest] Tagged chunks by section: {tag_counts}", flush=True)
    else:
        # Use standard chunking for other files
        chunks = chunk_text(text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No textual content could be extracted from the file.")

        embeddings = embed_texts(chunks)

        for idx, (chunk_text_value, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_metadata = {
                **base_metadata,
                "chunk_index": idx,
            }
            chunk_id = save_chunk(
                user_id=user_id,
                text=chunk_text_value,
                embedding=embedding,
                metadata=chunk_metadata,
                tags=chunk_metadata.get("extra_tags"),
            )
            saved_chunk_ids.append(chunk_id)

    log_ingest_job(
        user_id=user_id,
        job_id=ingest_job_id,
        status="completed",
        filename=file.filename or "upload",
        chunk_count=len(saved_chunk_ids),
        metadata={
            "file_id": file_id, 
            "source_type": source_type,
            "tag_counts": tag_counts if tag_counts else None,
        },
    )

    return {
        "success": True,
        "file_id": file_id,
        "chunks_created": len(saved_chunk_ids),
        "ingest_job_id": ingest_job_id,
        "tag_counts": tag_counts if tag_counts else None,
        "message": "File successfully ingested and embedded." + (f" Tags: {tag_counts}" if tag_counts else ""),
    }
