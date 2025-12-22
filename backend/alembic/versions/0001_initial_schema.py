"""Initial schema - consolidated migration

Revision ID: 0001_initial
Revises: 
Create Date: 2024-12-17

This migration creates all tables from scratch.
Previous migrations have been squashed into this single file.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('age', sa.String(), nullable=True),
        sa.Column('preferences', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('current_grade', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False, server_default='user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_index('ix_users_id', 'users', ['id'])

    # Custom Teaching Structures table (global)
    op.create_table(
        'custom_teaching_structures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('structure_name', sa.String(), nullable=False),
        sa.Column('num_time_points', sa.Integer(), nullable=False),
        sa.Column('num_subjects', sa.Integer(), nullable=False),
        sa.Column('time_point_labels', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('subject_labels', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('scale_type', sa.String(), nullable=False, server_default='0-10'),
        sa.Column('pipeline_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_custom_teaching_structures_id', 'custom_teaching_structures', ['id'])
    # Unique partial index for single active structure
    op.execute("""
        CREATE UNIQUE INDEX ix_custom_teaching_structures_single_active 
        ON custom_teaching_structures (is_active) 
        WHERE is_active = true
    """)

    # Chat Sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_sessions_id', 'chat_sessions', ['id'])
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])

    # Chat Messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_id', 'chat_messages', ['id'])
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])

    # AI Insights table
    op.create_table(
        'ai_insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=True),
        sa.Column('insight_type', sa.String(), nullable=False),
        sa.Column('context_key', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_insights_id', 'ai_insights', ['id'])
    op.create_index('ix_ai_insights_user_id', 'ai_insights', ['user_id'])
    op.create_index('ix_ai_insights_structure_id', 'ai_insights', ['structure_id'])

    # Custom Reference Dataset (global per structure)
    op.create_table(
        'custom_reference_dataset',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=False),
        sa.Column('sample_name', sa.String(), nullable=True),
        sa.Column('score_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_custom_reference_dataset_id', 'custom_reference_dataset', ['id'])
    op.create_index('ix_custom_reference_dataset_structure_id', 'custom_reference_dataset', ['structure_id'])

    # Custom User Scores
    op.create_table(
        'custom_user_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('time_point', sa.String(), nullable=False),
        sa.Column('actual_score', sa.Float(), nullable=True),
        sa.Column('predicted_score', sa.Float(), nullable=True),
        sa.Column('predicted_source', sa.String(), nullable=True),
        sa.Column('predicted_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_custom_user_scores_id', 'custom_user_scores', ['id'])
    op.create_index('ix_custom_user_scores_structure_id', 'custom_user_scores', ['structure_id'])
    op.create_index('ix_custom_user_scores_user_id', 'custom_user_scores', ['user_id'])
    op.create_index('ix_custom_user_score_unique', 'custom_user_scores', 
                    ['user_id', 'structure_id', 'subject', 'time_point'], unique=True)

    # Custom Structure Documents
    op.create_table(
        'custom_structure_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('original_content', sa.Text(), nullable=True),
        sa.Column('extracted_summary', sa.Text(), nullable=False),
        sa.Column('extraction_method', sa.String(), nullable=True, server_default='llm_summary'),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_custom_structure_documents_id', 'custom_structure_documents', ['id'])
    op.create_index('ix_custom_structure_documents_structure_id', 'custom_structure_documents', ['structure_id'])

    # ML Model Parameters
    op.create_table(
        'ml_model_parameters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('knn_n', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('kr_bandwidth', sa.Float(), nullable=False, server_default='1.25'),
        sa.Column('lwlr_tau', sa.Float(), nullable=False, server_default='3.0'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_model_parameters_id', 'ml_model_parameters', ['id'])

    # ML Model Config
    op.create_table(
        'ml_model_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('active_model', sa.String(), nullable=False, server_default='knn'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_model_config_id', 'ml_model_config', ['id'])

    # User Structure Preferences
    op.create_table(
        'user_structure_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('structure_id', sa.Integer(), nullable=False),
        sa.Column('current_timepoint', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['structure_id'], ['custom_teaching_structures.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_structure_preferences_id', 'user_structure_preferences', ['id'])
    op.create_index('ix_user_structure_preferences_user_id', 'user_structure_preferences', ['user_id'])
    op.create_index('ix_user_structure_preferences_structure_id', 'user_structure_preferences', ['structure_id'])
    op.create_index('ix_user_structure_pref_unique', 'user_structure_preferences',
                    ['user_id', 'structure_id'], unique=True)


def downgrade():
    op.drop_table('user_structure_preferences')
    op.drop_table('ml_model_config')
    op.drop_table('ml_model_parameters')
    op.drop_table('custom_structure_documents')
    op.drop_table('custom_user_scores')
    op.drop_table('custom_reference_dataset')
    op.drop_table('ai_insights')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('custom_teaching_structures')
    op.drop_table('users')
