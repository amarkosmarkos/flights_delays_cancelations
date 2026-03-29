"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "airports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("iata_code", sa.String(3), nullable=False),
        sa.Column("icao_code", sa.String(4), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iata_code"),
    )

    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        sa.Column("airline_code", sa.String(10), nullable=True),
        sa.Column("frequency_weekly", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("origin_iata", "destination_iata", "airline_code", name="uq_route"),
    )

    op.create_table(
        "flights_raw",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flight_number", sa.String(20), nullable=True),
        sa.Column("origin_iata", sa.String(3), nullable=True),
        sa.Column("destination_iata", sa.String(3), nullable=True),
        sa.Column("airline_code", sa.String(10), nullable=True),
        sa.Column("scheduled_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_arrival", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_arrival", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departure_delay_minutes", sa.Integer(), nullable=True),
        sa.Column("arrival_delay_minutes", sa.Integer(), nullable=True),
        sa.Column("cancelled", sa.Boolean(), server_default="false"),
        sa.Column("cancellation_reason", sa.String(50), nullable=True),
        sa.Column("data_source", sa.String(50), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_flights_raw_origin", "flights_raw", ["origin_iata", "scheduled_departure"])
    op.create_index("idx_flights_raw_route", "flights_raw", ["origin_iata", "destination_iata", "scheduled_departure"])

    op.create_table(
        "airport_aggregates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("airport_iata", sa.String(3), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_departures", sa.Integer(), nullable=True),
        sa.Column("total_arrivals", sa.Integer(), nullable=True),
        sa.Column("cancelled_departures", sa.Integer(), nullable=True),
        sa.Column("avg_departure_delay_minutes", sa.Float(), nullable=True),
        sa.Column("avg_arrival_delay_minutes", sa.Float(), nullable=True),
        sa.Column("cancellation_rate", sa.Float(), nullable=True),
        sa.Column("delay_level", sa.String(10), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("airport_iata", "period_start", name="uq_airport_agg"),
    )

    op.create_table(
        "route_aggregates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("origin_iata", sa.String(3), nullable=False),
        sa.Column("destination_iata", sa.String(3), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_flights", sa.Integer(), nullable=True),
        sa.Column("cancelled_flights", sa.Integer(), nullable=True),
        sa.Column("avg_departure_delay_minutes", sa.Float(), nullable=True),
        sa.Column("avg_arrival_delay_minutes", sa.Float(), nullable=True),
        sa.Column("cancellation_rate", sa.Float(), nullable=True),
        sa.Column("delay_level", sa.String(10), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("origin_iata", "destination_iata", "period_start", name="uq_route_agg"),
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flight_number", sa.String(20), nullable=True),
        sa.Column("origin_iata", sa.String(3), nullable=True),
        sa.Column("destination_iata", sa.String(3), nullable=True),
        sa.Column("airline_code", sa.String(10), nullable=True),
        sa.Column("scheduled_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("predicted_cancellation_probability", sa.Float(), nullable=True),
        sa.Column("predicted_delay_minutes", sa.Float(), nullable=True),
        sa.Column("prediction_interval_low", sa.Float(), nullable=True),
        sa.Column("prediction_interval_high", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("model_region", sa.String(50), nullable=True),
        sa.Column("data_sources_used", sa.JSON(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), server_default="false"),
        sa.Column("fallback_reason", sa.String(255), nullable=True),
        sa.Column("actual_delay_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_cancelled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "model_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("training_samples", sa.Integer(), nullable=True),
        sa.Column("delay_mae", sa.Float(), nullable=True),
        sa.Column("delay_rmse", sa.Float(), nullable=True),
        sa.Column("cancellation_auc", sa.Float(), nullable=True),
        sa.Column("cancellation_brier", sa.Float(), nullable=True),
        sa.Column("train_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("features_used", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("model_metrics")
    op.drop_table("predictions")
    op.drop_table("route_aggregates")
    op.drop_table("airport_aggregates")
    op.drop_index("idx_flights_raw_route", table_name="flights_raw")
    op.drop_index("idx_flights_raw_origin", table_name="flights_raw")
    op.drop_table("flights_raw")
    op.drop_table("routes")
    op.drop_table("airports")
