from uuid import uuid4

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.schemas.chunk import ChunkCreate
from app.services.embeddings import count_token, get_tokenizer


def ingest_document(file_path):
    # Keep native PDF text, but do not turn decorative images and logos into
    # searchable OCR noise. Other formats continue to use their normal parser.
    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = False
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
        }
    )
    result = converter.convert(file_path)
    document = result.document
    return document


def extract_text(document):
    current_heading = None
    extracted_items = []

    for document_item, _level in document.iterate_items():
        label = document_item.label.value
        text = getattr(document_item, "text", "")
        is_bullet_heading = label == "section_header" and text.lstrip().startswith(
            ("▪", "•", "-", "–", "—", "●", "○", "◦")
        )
        content_layer = getattr(
            getattr(document_item, "content_layer", None),
            "value",
            "body",
        )

        # Furniture is repeated page decoration such as headers and footers.
        if content_layer != "body":
            continue

        if label == "section_header" and not is_bullet_heading:
            current_heading = text
            continue

        if label == "table":
            content = document_item.export_to_markdown(doc=document)
        elif label in {"text", "list_item"} or is_bullet_heading:
            content = text
        else:
            continue

        if not content.strip():
            continue
        # PDF items carry page provenance. Reflowable formats such as DOCX
        # can contain valid text without page coordinates; dropping those
        # items makes a readable document look empty to the indexer.
        pages = [provenance.page_no for provenance in document_item.prov]
        page_start = min(pages) if pages else 1
        page_end = max(pages) if pages else 1

        item = {
            "heading": current_heading,
            "page_start": page_start,
            "page_end": page_end,
            "content": content,
        }

        extracted_items.append(item)
    return extracted_items


def split_long_text(text, max_token=500):
    token_count = count_token(text)
    if token_count <= max_token:
        return [text]
    else:
        tokenizer = get_tokenizer()
        encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        offsets = encoded["offset_mapping"]
        splitting_point = offsets[max_token - 1][1]
        first_part = text[:splitting_point]
        second_part = text[splitting_point:]

        return [first_part] + split_long_text(second_part, max_token)


def create_chunk(extracted_items, file_id, max_token=350) -> list[ChunkCreate]:

    chunks = []
    heading = None  # 是旧箱子的 Introduction
    page = []
    content = []
    total_token = 0

    for item in extracted_items:
        current_heading = item["heading"]  # 是刚读到的 Methods
        current_content = item["content"]
        pieces = split_long_text(current_content, max_token)

        for piece in pieces:
            token_count = count_token(piece)

            if (content and total_token + token_count > max_token) or (
                content and current_heading != heading
            ):
                join_content = " ".join(content)

                chunk = ChunkCreate(
                    chunk_index=len(chunks),
                    heading=heading,
                    page_start=min(page),
                    page_end=max(page),
                    content=join_content,
                    file_id=file_id,
                    token_count=count_token(join_content),
                )

                heading = None
                page = []
                content = []
                total_token = 0

                chunks.append(chunk)

            if not content:
                heading = current_heading

            content.append(piece)
            page.append(item["page_start"])
            page.append(item["page_end"])
            total_token += token_count

    if content:
        join_content = " ".join(content)

        chunk = ChunkCreate(
            chunk_index=len(chunks),
            heading=heading,
            page_start=min(page),
            page_end=max(page),
            content=join_content,
            file_id=file_id,
            token_count=count_token(join_content),
        )

        chunks.append(chunk)

    return chunks


def main() -> None:
    """
    file_path = "https://arxiv.org/pdf/2408.09869"
    document = ingest_document(file_path)
    extracted_texts = extract_text(document)
    print("Number of extracted items:", len(extracted_texts))
    print("First extracted item:", extracted_texts[0])

    first_content = extracted_texts[0]["content"]
    words = first_content.split()
    print("Words", words)
    print("Words count", len(words))

    chunk_parts = []
    for item in extracted_texts[:3]:
        chunk_parts.append(item["content"])

    chunk_content = " ".join(chunk_parts)

    print("Combine content: ", chunk_content)
    print("Combined word count: ", len(chunk_content.split()))

    file_id = uuid4()
    chunks = create_chunk(extracted_texts, file_id, max_token=350)
    print("Number of Chunks:", len(chunks))
    print("First chunk:", chunks[0])
    print("Second chunk:", chunks[1])

    text = "I love Python"
    tokenizer = get_tokenizer()
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    print(encoded["input_ids"])
    print(encoded["offset_mapping"])

    for start, end in encoded["offset_mapping"]:
        print(text[start:end])

    max_tokens = 2
    offsets = encoded["offset_mapping"]

    last_allocated_offset = offsets[max_tokens - 1]
    cut_position = last_allocated_offset[1]
    first_part = text[:cut_position]
    second_part = text[cut_position:]

    print("First part:", first_part)
    print("Second part: ", second_part)
    """
    test_text = "I Love python. " * 100
    parts = split_long_text(test_text, max_token=20)
    print("Number of parts: ", len(parts))
    for part in parts:
        print("Token COunt for chunks:", count_token(part))
    print("Content preserved: ", "".join(parts) == test_text)

    test_items = [
        {
            "heading": "Test Heading",
            "page_start": 1,
            "page_end": 1,
            "content": test_text,
        }
    ]
    test_max_token = 20
    rebuilt_text = ""
    test_file_id = uuid4()

    # ChunkCreate test_chunks
    test_chunks = create_chunk(test_items, test_file_id, max_token=test_max_token)
    print("Numbe of Chunks: ", len(test_chunks))
    for chunk in test_chunks:
        chunk_content = chunk.content
        print("Token Number:", count_token(chunk_content))
        print(count_token(chunk_content) <= test_max_token)
        rebuilt_text += chunk_content

    print("Content preserved: ", rebuilt_text == test_text)
    print(type(test_chunks[0]))


if __name__ == "__main__":
    main()


# $env:DOCLING_INFERENCE_COMPILE_TORCH_MODELS="false"
# uv run --directory apps/api python -m app.services.ingestion
"""
encoded             → 你的变量名，可以更换
"input_ids"         → Hugging Face 规定的 key= 代表每个 token 在 tokenizer 字典里的编号。
"attention_mask"    → Hugging Face 规定的 key=告诉模型哪些位置是真实内容，哪些位置只是为了对齐而补上的空位
"offset_mapping"    → Hugging Face 规定的 key=代表每个 token 对应原文的字符范围
里面的数字和位置     → tokenizer 根据输入动态生成

input_ids       → token 是谁
attention_mask  → token 要不要看
offset_mapping  → token 在原文哪里
"""
