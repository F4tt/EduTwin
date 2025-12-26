"""add learning mode tables

Revision ID: 0002
Revises: 0001
Create Date: 2025-12-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Add session_type column to chat_sessions
    op.add_column('chat_sessions', 
        sa.Column('session_type', sa.String(), nullable=False, server_default='chat')
    )
    
    # Create documents table for user uploads and admin documents
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),  # NULL if uploaded by admin
        sa.Column('structure_id', sa.Integer(), nullable=True),  # Reference to teaching structure
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),  # 'txt', 'docx', 'pdf'
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=True),  # Extracted text content
        sa.Column('metadata_', sa.JSON(), nullable=True),
        sa.Column('uploaded_by_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])
    op.create_index('ix_documents_structure_id', 'documents', ['structure_id'])
    
    # Create document_chunks table for vector embeddings
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),  # Vector embedding using pgvector
        sa.Column('metadata_', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    
    # Create index for vector similarity search (using pgvector)
    # Note: This uses PostgreSQL's vector type, requires pgvector extension
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding 
        ON document_chunks 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade():
    op.drop_index('ix_document_chunks_embedding', table_name='document_chunks')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index('ix_documents_structure_id', table_name='documents')
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_table('documents')
    op.drop_column('chat_sessions', 'session_type')
    op.execute('DROP EXTENSION IF EXISTS vector')
