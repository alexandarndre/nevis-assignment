from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, Index, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field, SQLModel

from nevis_search.core.db.models import Record
from nevis_search.documents.schemas import DocumentBase
from nevis_search.embeddings.constants import EMBEDDING_DIM


class Document(DocumentBase, Record, table=True):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_search_tsv", "search_tsv", postgresql_using="gin"),)

    client_id: UUID = Field(foreign_key="clients.id", ondelete="CASCADE", index=True)
    search_tsv: str = Field(
        sa_column=Column(
            TSVECTOR,
            Computed(
                "setweight(to_tsvector('english', title), 'A') || setweight(to_tsvector('english', content), 'B')",
                persisted=True,
            ),
            nullable=False,
        )
    )


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    document_id: UUID = Field(foreign_key="documents.id", ondelete="CASCADE", primary_key=True)
    chunk_index: int = Field(primary_key=True)
    content: str = Field(sa_type=Text)
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM), nullable=False))
