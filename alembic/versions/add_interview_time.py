"""Add interview_time to results

Revision ID: add_interview_time
Revises: 05afb2822af4
Create Date: 2026-04-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_interview_time'
down_revision: Union[str, Sequence[str], None] = '05afb2822af4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('results', sa.Column('interview_time', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('results', 'interview_time')
