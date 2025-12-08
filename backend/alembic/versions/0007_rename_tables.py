"""rename tables for consistency

Revision ID: 0007
Revises: 0006
Create Date: 2025-12-03

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0007_rename_tables'
down_revision = '0006b_update_custom_model_structure'
branch_labels = None
depends_on = None


def upgrade():
    # Rename tables to more consistent naming
    op.rename_table('knn_reference_samples', 'reference_dataset')
    op.rename_table('custom_dataset_samples', 'custom_reference_dataset')
    op.rename_table('data_import_logs', 'dataset_import_logs')
    op.rename_table('model_parameters', 'ml_model_parameters')


def downgrade():
    # Revert table names
    op.rename_table('reference_dataset', 'knn_reference_samples')
    op.rename_table('custom_reference_dataset', 'custom_dataset_samples')
    op.rename_table('dataset_import_logs', 'data_import_logs')
    op.rename_table('ml_model_parameters', 'model_parameters')
