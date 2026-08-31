"""record Garmin connection state for controlled reauthentication"""

import sqlalchemy as sa
from alembic import op

revision = "20260831_0019"
down_revision = "20260826_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "garmin_credentials",
        sa.Column(
            "connection_status",
            sa.String(length=50),
            nullable=False,
            server_default="connected",
        ),
    )
    op.alter_column("garmin_credentials", "connection_status", server_default=None)


def downgrade() -> None:
    op.drop_column("garmin_credentials", "connection_status")
