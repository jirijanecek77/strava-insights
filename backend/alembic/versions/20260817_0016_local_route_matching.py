"""add local GPS route matching storage

Revision ID: 20260817_0016
Revises: 20260810_0015
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260817_0016"
down_revision = "20260810_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_route_signatures",
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sport_type", sa.String(length=50), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("source_point_count", sa.Integer(), nullable=False),
        sa.Column("valid_point_count", sa.Integer(), nullable=False),
        sa.Column("distance_meters", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_loop", sa.Boolean(), nullable=False),
        sa.Column(
            "sampled_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "spatial_cells",
            postgresql.ARRAY(sa.String(length=15)),
            nullable=False,
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_activity_route_signatures_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_activity_route_signatures_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "activity_id", name=op.f("pk_activity_route_signatures")
        ),
    )
    op.create_index(
        "ix_route_signatures_user_sport_distance",
        "activity_route_signatures",
        ["user_id", "sport_type", "distance_meters"],
        unique=False,
    )
    op.create_index(
        "ix_route_signatures_spatial_cells",
        "activity_route_signatures",
        ["spatial_cells"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "route_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sport_type", sa.String(length=50), nullable=False),
        sa.Column("representative_activity_id", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column(
            "nominal_distance_meters",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["representative_activity_id"],
            ["activities.id"],
            name=op.f("fk_route_groups_representative_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_route_groups_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_route_groups")),
    )
    op.create_index(
        "ix_route_groups_user_sport",
        "route_groups",
        ["user_id", "sport_type"],
        unique=False,
    )

    op.create_table(
        "activity_route_memberships",
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("route_group_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_activity_route_memberships_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["route_group_id"],
            ["route_groups.id"],
            name=op.f("fk_activity_route_memberships_route_group_id_route_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "activity_id", name=op.f("pk_activity_route_memberships")
        ),
    )
    op.create_index(
        "ix_activity_route_memberships_group",
        "activity_route_memberships",
        ["route_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activity_route_memberships_group",
        table_name="activity_route_memberships",
    )
    op.drop_table("activity_route_memberships")
    op.drop_index("ix_route_groups_user_sport", table_name="route_groups")
    op.drop_table("route_groups")
    op.drop_index(
        "ix_route_signatures_spatial_cells",
        table_name="activity_route_signatures",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_route_signatures_user_sport_distance",
        table_name="activity_route_signatures",
    )
    op.drop_table("activity_route_signatures")
