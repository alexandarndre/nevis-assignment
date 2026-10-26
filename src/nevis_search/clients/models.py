from sqlalchemy import Column, Computed, Index, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field

from nevis_search.clients.schemas import ClientBase
from nevis_search.core.db.models import Record


class Client(ClientBase, Record, table=True):
    __tablename__ = "clients"
    __table_args__ = (
        Index("uq_clients_email_lower", text("lower(email)"), unique=True),
        Index(
            "ix_clients_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index("ix_clients_description_tsv", "description_tsv", postgresql_using="gin"),
    )

    search_text: str = Field(
        sa_column=Column(
            Text, Computed("first_name || ' ' || last_name || ' ' || email", persisted=True), nullable=False
        )
    )
    description_tsv: str = Field(
        sa_column=Column(
            TSVECTOR, Computed("to_tsvector('english', coalesce(description, ''))", persisted=True), nullable=False
        )
    )
