import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class KlineModel(Base):
    __tablename__ = "klines"

    # Composite Primary Key to ensure we don't duplicate klines
    symbol = sa.Column(sa.String, primary_key=True)
    interval = sa.Column(sa.String, primary_key=True)
    open_time = sa.Column(sa.DateTime, primary_key=True)

    open_price = sa.Column(sa.Float, nullable=False)
    high_price = sa.Column(sa.Float, nullable=False)
    low_price = sa.Column(sa.Float, nullable=False)
    close_price = sa.Column(sa.Float, nullable=False)
    volume = sa.Column(sa.Float, nullable=False)
    close_time = sa.Column(sa.DateTime, nullable=False)
    quote_asset_volume = sa.Column(sa.Float, nullable=False)
    number_of_trades = sa.Column(sa.Integer, nullable=False)
    taker_buy_base_asset_volume = sa.Column(sa.Float, nullable=False)
    taker_buy_quote_asset_volume = sa.Column(sa.Float, nullable=False)
