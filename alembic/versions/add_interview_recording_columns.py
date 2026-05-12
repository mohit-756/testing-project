"""Add interview recording metadata columns

Revision ID: add_interview_recording_columns
Revises: add_total_duration_minutes, add_linkedin_github_columns
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_interview_recording_columns"
down_revision: Union[str, Sequence[str], None] = ("add_total_duration_minutes", "add_linkedin_github_columns")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interview_sessions", sa.Column("recording_path", sa.String(length=500), nullable=True))
    op.add_column("interview_sessions", sa.Column("recording_mime_type", sa.String(length=120), nullable=True))
    op.add_column("interview_sessions", sa.Column("recording_size_bytes", sa.Integer(), nullable=True))
    op.add_column("interview_sessions", sa.Column("recording_uploaded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_sessions", "recording_uploaded_at")
    op.drop_column("interview_sessions", "recording_size_bytes")
    op.drop_column("interview_sessions", "recording_mime_type")
    op.drop_column("interview_sessions", "recording_path")
