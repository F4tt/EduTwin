"""Rename learning_documents to ai_insights and refactor structure

Revision ID: 0008
Revises: 0007
Create Date: 2025-12-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_rename_learning_documents_to_ai_insights'
down_revision = '0007_rename_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Rename table
    op.rename_table('learning_documents', 'ai_insights')
    
    # Rename and refactor columns for better clarity
    # Note: 'source' becomes 'insight_type', 'reference_type' becomes 'context_key'
    op.alter_column('ai_insights', 'source', new_column_name='insight_type')
    op.alter_column('ai_insights', 'reference_type', new_column_name='context_key')
    
    # Drop unused columns
    op.drop_column('ai_insights', 'reference_id')
    op.drop_column('ai_insights', 'title')
    
    # Add comment to table
    op.execute("""
        COMMENT ON TABLE ai_insights IS 
        'Stores AI-generated insights including slide comments, subject analysis, and chat responses'
    """)


def downgrade():
    # Restore columns
    op.add_column('ai_insights', sa.Column('reference_id', sa.Integer(), nullable=True))
    op.add_column('ai_insights', sa.Column('title', sa.String(), nullable=True))
    
    # Restore column names
    op.alter_column('ai_insights', 'context_key', new_column_name='reference_type')
    op.alter_column('ai_insights', 'insight_type', new_column_name='source')
    
    # Rename table back
    op.rename_table('ai_insights', 'learning_documents')
