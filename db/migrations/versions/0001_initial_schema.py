"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('message', sa.String(2000), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='received'),
        sa.Column('enrichment_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'enrichment_data',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('company_size', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('funding_stage', sa.String(100), nullable=True),
        sa.Column('raw_data', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'ai_scores',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('score', sa.Integer, nullable=False),
        sa.Column('tier', sa.String(1), nullable=False),
        sa.Column('reasoning', sa.String(2000), nullable=False),
        sa.Column('disqualifiers', sa.JSON, nullable=False),
        sa.Column('recommended_action', sa.String(100), nullable=False),
        sa.Column('confidence', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'lead_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'errors',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('lead_id', sa.String(36), nullable=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('error_message', sa.String(2000), nullable=False),
        sa.Column('payload', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('errors')
    op.drop_table('lead_events')
    op.drop_table('ai_scores')
    op.drop_table('enrichment_data')
    op.drop_table('leads')
