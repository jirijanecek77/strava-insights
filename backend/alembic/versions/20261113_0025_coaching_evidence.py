"""Add reusable local coaching evidence and stored period metrics."""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0025"
down_revision = "20261111_0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_coaching_evidence",
        sa.Column(
            "activity_id",
            sa.Integer(),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
    )
    op.add_column(
        "period_coaching_summaries", sa.Column("metrics", sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column("period_coaching_summaries", "metrics")
    op.drop_table("activity_coaching_evidence")
