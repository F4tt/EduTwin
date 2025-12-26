"""add document processing status

Revision ID: add_document_processing_status
Revises: bedfdabc4a55
Create Date: 2025-12-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_document_processing_status'
down_revision = 'bedfdabc4a55'
branch_labels = None
depends_on = None


def upgrade():
    # Add processing_status column with default 'pending'
    op.add_column('documents', sa.Column('processing_status', sa.String(), nullable=False, server_default='completed'))
    
    # Add processing_progress column (0-100)
    op.add_column('documents', sa.Column('processing_progress', sa.Integer(), nullable=False, server_default='100'))
    
    # Add processing_error column for error messages
    op.add_column('documents', sa.Column('processing_error', sa.Text(), nullable=True))
    
    # Update existing documents to 'completed' since they were processed synchronously
    op.execute("UPDATE documents SET processing_status = 'completed', processing_progress = 100")


def downgrade():
    op.drop_column('documents', 'processing_error')
    op.drop_column('documents', 'processing_progress')
    op.drop_column('documents', 'processing_status')
