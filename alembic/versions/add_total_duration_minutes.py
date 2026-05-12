"""Add total_duration_minutes to job_descriptions

Revision ID: add_total_duration_minutes
Revises: add_eligibility_calendar_columns
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_total_duration_minutes'
down_revision: Union[str, Sequence[str], None] = 'add_eligibility_calendar_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('total_duration_minutes', sa.Integer(), nullable=False, server_default='30'))


def downgrade() -> None:
    op.drop_column('jobs', 'total_duration_minutes')
