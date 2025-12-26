"""simplify documents - remove chunks and vector

Revision ID: simplify_documents
Revises: add_document_processing_status
Create Date: 2025-12-25 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'simplify_documents'
down_revision = 'add_document_processing_status'
branch_labels = None
depends_on = None


def upgrade():
    # Drop document_chunks table (no longer needed)
    op.execute("DROP TABLE IF EXISTS document_chunks CASCADE")
    
    # Remove columns from documents table (using raw SQL for columns that exist)
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS processing_error")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS processing_progress")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS processing_status")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS uploaded_by_admin")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS metadata")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS original_filename")
    
    # Make user_id NOT NULL (all documents belong to a user now)
    op.execute("ALTER TABLE documents ALTER COLUMN user_id SET NOT NULL")


def downgrade():
    # Reverse changes
    op.alter_column('documents', 'user_id', nullable=True)
    op.add_column('documents', sa.Column('original_filename', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('metadata_', sa.JSON(), nullable=True))
    op.add_column('documents', sa.Column('uploaded_by_admin', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('documents', sa.Column('processing_status', sa.String(), server_default='completed', nullable=False))
    op.add_column('documents', sa.Column('processing_progress', sa.Integer(), server_default='100', nullable=False))
    op.add_column('documents', sa.Column('processing_error', sa.Text(), nullable=True))
    
    # Recreate document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('metadata_', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
