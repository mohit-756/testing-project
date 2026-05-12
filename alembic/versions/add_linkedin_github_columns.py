"""Add missing candidate profile columns

Revision ID: add_linkedin_github_columns
Revises: add_candidate_profile_columns
Create Date: 2026-04-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_linkedin_github_columns'
down_revision: Union[str, Sequence[str], None] = 'add_candidate_profile_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('linkedin_url', sa.String(length=500), nullable=True))
    op.add_column('candidates', sa.Column('github_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'github_url')
    op.drop_column('candidates', 'linkedin_url')