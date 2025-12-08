"""add custom structure documents

Revision ID: 0012_add_structure_documents
Revises: 0011_remove_first_login
Create Date: 2025-12-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0012_add_structure_documents'
down_revision = '0011_remove_first_login'
branch_labels = None
depends_on = None


def upgrade():
    # Create custom_structure_documents table
    op.create_table(
        'custom_structure_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('original_content', sa.Text(), nullable=True),
        sa.Column('extracted_summary', sa.Text(), nullable=False),
        sa.Column('extraction_method', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes
    op.create_index('ix_custom_structure_documents_id', 'custom_structure_documents', ['id'])
    op.create_index('ix_custom_structure_documents_structure_id', 'custom_structure_documents', ['structure_id'])


def downgrade():
    op.drop_index('ix_custom_structure_documents_structure_id', table_name='custom_structure_documents')
    op.drop_index('ix_custom_structure_documents_id', table_name='custom_structure_documents')
    op.drop_table('custom_structure_documents')
