"""Add eligibility feedback and calendar columns to results

Revision ID: add_eligibility_calendar_columns
Revises: add_interview_time
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_eligibility_calendar_columns'
down_revision: Union[str, Sequence[str], None] = 'add_interview_time'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('results', sa.Column('interview_datetime', sa.DateTime(), nullable=True))
    op.add_column('results', sa.Column('reminder_24h_sent', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('results', sa.Column('reminder_1h_sent', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('results', sa.Column('interview_rescheduled_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('results', sa.Column('eligibility_feedback', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('results', 'eligibility_feedback')
    op.drop_column('results', 'interview_rescheduled_count')
    op.drop_column('results', 'reminder_1h_sent')
    op.drop_column('results', 'reminder_24h_sent')
    op.drop_column('results', 'interview_datetime')