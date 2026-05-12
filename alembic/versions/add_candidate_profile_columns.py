"""Add candidate profile columns to candidates

Revision ID: add_candidate_profile_columns
Revises: add_interview_time
Create Date: 2026-04-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_candidate_profile_columns'
down_revision: Union[str, Sequence[str], None] = 'add_interview_time'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('avatar_path', sa.String(length=300), nullable=True))
    op.add_column('candidates', sa.Column('linkedin_url', sa.String(length=500), nullable=True))
    op.add_column('candidates', sa.Column('github_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'github_url')
    op.drop_column('candidates', 'linkedin_url')
    op.drop_column('candidates', 'avatar_path')