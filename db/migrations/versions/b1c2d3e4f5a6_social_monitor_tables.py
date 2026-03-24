"""social_monitor_tables

Revision ID: b1c2d3e4f5a6
Revises: a884b0606c12
Create Date: 2026-03-24 19:14:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = 'b1c2d3e4f5a6'
down_revision = 'a884b0606c12'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('social_sources',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=False), nullable=True),
        sa.Column('created_by', sa.BigInteger(), sa.ForeignKey('users.telegram_id'), nullable=False),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('source_url', sa.String(2048), nullable=False),
        sa.Column('source_id', sa.String(512), nullable=False),
        sa.Column('source_name', sa.String(512), nullable=True),
        sa.Column('source_type', sa.String(20), nullable=False, server_default='profile'),
        sa.Column('collection_config', JSONB, nullable=True),
        sa.Column('schedule', JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('last_parsed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('source_meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_social_sources_workspace_id', 'social_sources', ['workspace_id'])
    op.create_index('ix_social_sources_created_by', 'social_sources', ['created_by'])
    op.create_index('ix_social_sources_status', 'social_sources', ['status'])

    op.create_table('social_posts',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('source_id', UUID(as_uuid=False), sa.ForeignKey('social_sources.id'), nullable=False),
        sa.Column('workspace_id', UUID(as_uuid=False), nullable=True),
        sa.Column('platform_post_id', sa.String(512), nullable=False),
        sa.Column('post_url', sa.String(2048), nullable=True),
        sa.Column('post_type', sa.String(30), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('author_name', sa.String(512), nullable=True),
        sa.Column('author_id', sa.String(256), nullable=True),
        sa.Column('metrics', JSONB, nullable=True),
        sa.Column('media_urls', JSONB, nullable=True),
        sa.Column('hashtags', JSONB, nullable=True),
        sa.Column('mentions', JSONB, nullable=True),
        sa.Column('location', JSONB, nullable=True),
        sa.Column('raw_data', JSONB, nullable=True),
        sa.Column('dedupe_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_social_posts_source_id', 'social_posts', ['source_id'])
    op.create_index('ix_social_posts_workspace_id', 'social_posts', ['workspace_id'])
    op.create_index('ix_social_posts_platform_post_id', 'social_posts', ['platform_post_id'])
    op.create_index('ix_social_posts_posted_at', 'social_posts', ['posted_at'])
    op.create_index('ix_social_posts_dedupe_hash', 'social_posts', ['dedupe_hash'])

    op.create_table('social_parse_runs',
        sa.Column('id', UUID(as_uuid=False), primary_key=True),
        sa.Column('source_id', UUID(as_uuid=False), sa.ForeignKey('social_sources.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posts_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('posts_new', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('metrics', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_social_parse_runs_source_id', 'social_parse_runs', ['source_id'])


def downgrade() -> None:
    op.drop_table('social_parse_runs')
    op.drop_table('social_posts')
    op.drop_table('social_sources')
