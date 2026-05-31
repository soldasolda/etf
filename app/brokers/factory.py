from __future__ import annotations

from app.brokers.base import BrokerClient
from app.brokers.fdr_client import FinanceDataReaderBrokerClient
from app.brokers.sample_client import SampleBrokerClient
from app.brokers.toss_client import TossBrokerClient
from app.config import Settings


def create_broker_client(settings: Settings) -> BrokerClient:
    provider = settings.market_data_provider
    if provider == "sample":
        return SampleBrokerClient()
    if provider == "fdr":
        return FinanceDataReaderBrokerClient()
    if provider == "toss":
        return TossBrokerClient(settings)
    raise ValueError(f"Unsupported market data provider: {provider}")
