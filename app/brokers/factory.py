from __future__ import annotations

from app.brokers.base import BrokerClient
from app.brokers.fdr_client import FinanceDataReaderBrokerClient
from app.brokers.sample_client import SampleBrokerClient
from app.brokers.toss_client import TossBrokerClient
from app.config import Settings


def create_broker_client(settings: Settings) -> BrokerClient:
    if settings.broker == "sample":
        return SampleBrokerClient()
    if settings.broker == "fdr":
        return FinanceDataReaderBrokerClient()
    if settings.broker == "toss":
        return TossBrokerClient(settings)
    raise ValueError(f"Unsupported broker: {settings.broker}")
