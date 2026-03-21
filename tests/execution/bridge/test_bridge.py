"""Tests for the ZeroMQ bridge: message schemas and socket classes.

All ZMQ socket tests use mocked sockets — no real connections required.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.execution.abstract import Bar, OrderRequest, OrderResult, OrderType, Side, Tick


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_tick() -> Tick:
    return Tick(
        timestamp=np.datetime64("2024-01-15T10:30:00.123456789", "ns"),
        symbol="EURUSD",
        bid=1.08500,
        ask=1.08510,
        bid_volume=100.0,
        ask_volume=150.0,
        source="mt5",
    )


@pytest.fixture()
def sample_bar() -> Bar:
    return Bar(
        timestamp=np.datetime64("2024-01-15T10:00:00.000000000", "ns"),
        symbol="GBPUSD",
        open=1.27100,
        high=1.27250,
        low=1.27050,
        close=1.27200,
        volume=500.0,
        spread=0.0002,
    )


@pytest.fixture()
def sample_order_request() -> OrderRequest:
    return OrderRequest(
        symbol="EURUSD",
        side=Side.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET,
        price=None,
        sl=1.08000,
        tp=1.09000,
        comment="alpha-engine",
    )


@pytest.fixture()
def sample_order_request_limit() -> OrderRequest:
    return OrderRequest(
        symbol="GBPUSD",
        side=Side.SELL,
        quantity=0.2,
        order_type=OrderType.LIMIT,
        price=1.27500,
        sl=None,
        tp=None,
        comment="",
    )


@pytest.fixture()
def sample_order_result_success() -> OrderResult:
    return OrderResult(
        order_id="ORD-12345",
        fill_price=1.08502,
        fill_quantity=0.1,
        slippage=0.00002,
        commission=3.50,
        success=True,
        error_message="",
    )


@pytest.fixture()
def sample_order_result_failure() -> OrderResult:
    return OrderResult(
        order_id="ORD-99999",
        fill_price=0.0,
        fill_quantity=0.0,
        slippage=0.0,
        commission=0.0,
        success=False,
        error_message="Insufficient margin",
    )


# ---------------------------------------------------------------------------
# Task 1: MessagePack schema round-trip tests
# ---------------------------------------------------------------------------


class TestTickRoundTrip:
    """Tick serialization/deserialization round-trip tests."""

    def test_tick_roundtrip_all_fields(self, sample_tick: Tick) -> None:
        from src.execution.bridge.message_schemas import pack_tick, unpack_tick

        packed = pack_tick(sample_tick)
        assert isinstance(packed, bytes)
        unpacked = unpack_tick(packed)
        assert unpacked.timestamp == sample_tick.timestamp
        assert unpacked.symbol == sample_tick.symbol
        assert unpacked.bid == pytest.approx(sample_tick.bid)
        assert unpacked.ask == pytest.approx(sample_tick.ask)
        assert unpacked.bid_volume == pytest.approx(sample_tick.bid_volume)
        assert unpacked.ask_volume == pytest.approx(sample_tick.ask_volume)
        assert unpacked.source == sample_tick.source

    def test_tick_roundtrip_default_fields(self) -> None:
        from src.execution.bridge.message_schemas import pack_tick, unpack_tick

        tick = Tick(
            timestamp=np.datetime64("2024-01-15T10:30:00", "ns"),
            symbol="USDJPY",
            bid=148.500,
            ask=148.510,
        )
        unpacked = unpack_tick(pack_tick(tick))
        assert unpacked.bid_volume == 0.0
        assert unpacked.ask_volume == 0.0
        assert unpacked.source == ""

    def test_tick_nanosecond_precision(self) -> None:
        from src.execution.bridge.message_schemas import pack_tick, unpack_tick

        # nanosecond-precise timestamp
        ts = np.datetime64("2024-01-15T10:30:00.123456789", "ns")
        tick = Tick(timestamp=ts, symbol="EURUSD", bid=1.0, ask=1.0001)
        unpacked = unpack_tick(pack_tick(tick))
        assert unpacked.timestamp == ts


class TestBarRoundTrip:
    """Bar serialization/deserialization round-trip tests."""

    def test_bar_roundtrip_all_fields(self, sample_bar: Bar) -> None:
        from src.execution.bridge.message_schemas import pack_bar, unpack_bar

        packed = pack_bar(sample_bar)
        assert isinstance(packed, bytes)
        unpacked = unpack_bar(packed)
        assert unpacked.timestamp == sample_bar.timestamp
        assert unpacked.symbol == sample_bar.symbol
        assert unpacked.open == pytest.approx(sample_bar.open)
        assert unpacked.high == pytest.approx(sample_bar.high)
        assert unpacked.low == pytest.approx(sample_bar.low)
        assert unpacked.close == pytest.approx(sample_bar.close)
        assert unpacked.volume == pytest.approx(sample_bar.volume)
        assert unpacked.spread == pytest.approx(sample_bar.spread)

    def test_bar_roundtrip_default_fields(self) -> None:
        from src.execution.bridge.message_schemas import pack_bar, unpack_bar

        bar = Bar(
            timestamp=np.datetime64("2024-01-15T10:00:00", "ns"),
            symbol="AUDUSD",
            open=0.66000,
            high=0.66100,
            low=0.65950,
            close=0.66050,
        )
        unpacked = unpack_bar(pack_bar(bar))
        assert unpacked.volume == 0.0
        assert unpacked.spread == 0.0


class TestOrderRequestRoundTrip:
    """OrderRequest serialization/deserialization round-trip tests."""

    def test_order_request_roundtrip_with_optionals(
        self, sample_order_request: OrderRequest
    ) -> None:
        from src.execution.bridge.message_schemas import (
            pack_order_request,
            unpack_order_request,
        )

        packed = pack_order_request(sample_order_request)
        assert isinstance(packed, bytes)
        unpacked = unpack_order_request(packed)
        assert unpacked.symbol == sample_order_request.symbol
        assert unpacked.side == sample_order_request.side
        assert unpacked.quantity == pytest.approx(sample_order_request.quantity)
        assert unpacked.order_type == sample_order_request.order_type
        assert unpacked.price is None
        assert unpacked.sl == pytest.approx(sample_order_request.sl)  # type: ignore[arg-type]
        assert unpacked.tp == pytest.approx(sample_order_request.tp)  # type: ignore[arg-type]
        assert unpacked.comment == sample_order_request.comment

    def test_order_request_roundtrip_none_fields(
        self, sample_order_request_limit: OrderRequest
    ) -> None:
        from src.execution.bridge.message_schemas import (
            pack_order_request,
            unpack_order_request,
        )

        unpacked = unpack_order_request(pack_order_request(sample_order_request_limit))
        assert unpacked.sl is None
        assert unpacked.tp is None
        assert unpacked.price == pytest.approx(sample_order_request_limit.price)  # type: ignore[arg-type]

    def test_order_request_enum_side_preserved(self) -> None:
        from src.execution.bridge.message_schemas import (
            pack_order_request,
            unpack_order_request,
        )

        for side in (Side.BUY, Side.SELL):
            req = OrderRequest(symbol="EURUSD", side=side, quantity=0.1)
            assert unpack_order_request(pack_order_request(req)).side == side

    def test_order_request_enum_order_type_preserved(self) -> None:
        from src.execution.bridge.message_schemas import (
            pack_order_request,
            unpack_order_request,
        )

        for ot in (OrderType.MARKET, OrderType.LIMIT, OrderType.STOP):
            req = OrderRequest(
                symbol="EURUSD",
                side=Side.BUY,
                quantity=0.1,
                order_type=ot,
            )
            assert unpack_order_request(pack_order_request(req)).order_type == ot


class TestOrderResultRoundTrip:
    """OrderResult serialization/deserialization round-trip tests."""

    def test_order_result_success_roundtrip(
        self, sample_order_result_success: OrderResult
    ) -> None:
        from src.execution.bridge.message_schemas import (
            pack_order_result,
            unpack_order_result,
        )

        packed = pack_order_result(sample_order_result_success)
        assert isinstance(packed, bytes)
        unpacked = unpack_order_result(packed)
        assert unpacked.order_id == sample_order_result_success.order_id
        assert unpacked.fill_price == pytest.approx(sample_order_result_success.fill_price)
        assert unpacked.fill_quantity == pytest.approx(
            sample_order_result_success.fill_quantity
        )
        assert unpacked.slippage == pytest.approx(sample_order_result_success.slippage)
        assert unpacked.commission == pytest.approx(sample_order_result_success.commission)
        assert unpacked.success is True
        assert unpacked.error_message == ""

    def test_order_result_failure_roundtrip(
        self, sample_order_result_failure: OrderResult
    ) -> None:
        from src.execution.bridge.message_schemas import (
            pack_order_result,
            unpack_order_result,
        )

        unpacked = unpack_order_result(pack_order_result(sample_order_result_failure))
        assert unpacked.success is False
        assert unpacked.error_message == "Insufficient margin"


class TestHeartbeatRoundTrip:
    """Heartbeat pack/unpack tests."""

    def test_heartbeat_returns_bytes(self) -> None:
        from src.execution.bridge.message_schemas import pack_heartbeat

        result = pack_heartbeat()
        assert isinstance(result, bytes)

    def test_heartbeat_roundtrip_timestamp_within_1_second(self) -> None:
        from src.execution.bridge.message_schemas import pack_heartbeat, unpack_heartbeat

        before = np.datetime64("now", "ns")
        packed = pack_heartbeat()
        after = np.datetime64("now", "ns")
        ts = unpack_heartbeat(packed)
        assert isinstance(ts, np.datetime64)
        # timestamp must be between before and after (within ~1 second slack)
        slack_ns = int(1e9)  # 1 second in nanoseconds
        assert int(ts.astype("datetime64[ns]").astype(np.int64)) >= int(
            before.astype("datetime64[ns]").astype(np.int64)
        ) - slack_ns
        assert int(ts.astype("datetime64[ns]").astype(np.int64)) <= int(
            after.astype("datetime64[ns]").astype(np.int64)
        ) + slack_ns


# ---------------------------------------------------------------------------
# Task 2: WindowsPublisher mocked socket tests
# ---------------------------------------------------------------------------


class TestWindowsPublisherPorts:
    """Verify port constants per D-33."""

    def test_port_constants(self) -> None:
        from src.execution.bridge.windows_publisher import WindowsPublisher

        assert WindowsPublisher.TICK_PORT == 5556
        assert WindowsPublisher.BAR_PORT == 5557
        assert WindowsPublisher.ORDER_REQ_PORT == 5558
        assert WindowsPublisher.ORDER_RES_PORT == 5559


class TestWindowsPublisherPublishTick:
    """WindowsPublisher publishes ticks as multipart ZMQ messages."""

    @pytest.mark.asyncio
    async def test_publish_tick_sends_multipart(self, sample_tick: Tick) -> None:
        from src.execution.bridge.windows_publisher import WindowsPublisher
        from src.execution.bridge.message_schemas import pack_tick

        publisher = WindowsPublisher()
        mock_socket = AsyncMock()
        publisher._tick_pub = mock_socket
        publisher._running = True

        await publisher.publish_tick(sample_tick)

        mock_socket.send_multipart.assert_called_once()
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == sample_tick.symbol.encode()
        assert call_args[1] == pack_tick(sample_tick)

    @pytest.mark.asyncio
    async def test_publish_bar_sends_multipart(self, sample_bar: Bar) -> None:
        from src.execution.bridge.windows_publisher import WindowsPublisher
        from src.execution.bridge.message_schemas import pack_bar

        publisher = WindowsPublisher()
        mock_socket = AsyncMock()
        publisher._bar_pub = mock_socket
        publisher._running = True

        await publisher.publish_bar(sample_bar)

        mock_socket.send_multipart.assert_called_once()
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == sample_bar.symbol.encode()
        assert call_args[1] == pack_bar(sample_bar)


class TestWindowsPublisherHeartbeat:
    """Heartbeat loop sends heartbeat messages at the specified interval."""

    @pytest.mark.asyncio
    async def test_heartbeat_loop_sends_heartbeat(self) -> None:
        from src.execution.bridge.windows_publisher import WindowsPublisher
        from src.execution.bridge.message_schemas import pack_heartbeat

        publisher = WindowsPublisher()
        mock_socket = AsyncMock()
        publisher._tick_pub = mock_socket
        publisher._running = True

        # Run heartbeat loop for one iteration then stop
        async def stop_after_one() -> None:
            await asyncio.sleep(0.05)
            publisher._running = False

        with patch.object(
            publisher, "_heartbeat_interval_seconds", 0.01
        ):
            await asyncio.gather(
                publisher._heartbeat_loop(),
                stop_after_one(),
                return_exceptions=True,
            )

        # Heartbeat should have been sent at least once
        assert mock_socket.send.call_count >= 1


# ---------------------------------------------------------------------------
# Task 2: LinuxConsumer mocked socket tests
# ---------------------------------------------------------------------------


class TestLinuxConsumerConstants:
    """LinuxConsumer has correct reconnect and stale thresholds per D-35."""

    def test_reconnect_delays_max_30s(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        assert max(LinuxConsumer.RECONNECT_DELAYS) == 30.0

    def test_stale_threshold_10s(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        assert LinuxConsumer.STALE_THRESHOLD == 10.0

    def test_default_host_wireguard(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        assert consumer._host == "10.200.0.1"


class TestLinuxConsumerSubscribe:
    """Consumer subscribe sets ZMQ topic filter on SUB socket."""

    @pytest.mark.asyncio
    async def test_subscribe_sets_topic_filter(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        mock_socket = MagicMock()
        consumer._tick_sub = mock_socket

        await consumer.subscribe("EURUSD")

        mock_socket.setsockopt.assert_called_with(
            consumer._zmq_subscribe_opt, b"EURUSD"
        )
        assert "EURUSD" in consumer._subscribed_symbols


class TestLinuxConsumerStaleDetection:
    """Consumer marks data stale when no heartbeat received for >10 seconds."""

    def test_is_stale_initially_true(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        # _last_heartbeat defaults to 0.0 — far in past
        assert consumer.is_stale is True

    def test_is_stale_false_after_recent_heartbeat(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        consumer._last_heartbeat = time.monotonic()
        assert consumer.is_stale is False

    def test_is_stale_true_after_11_seconds(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        consumer._last_heartbeat = time.monotonic() - 11.0
        assert consumer.is_stale is True


class TestLinuxConsumerReconnect:
    """Consumer reconnect follows exponential backoff schedule."""

    @pytest.mark.asyncio
    async def test_reconnect_delays_follow_schedule(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        delays_observed: list[float] = []

        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays_observed.append(delay)
            # Don't actually sleep

        consumer._reconnect_attempt = 0
        consumer._ctx = None  # No real context

        with patch("asyncio.sleep", side_effect=mock_sleep):
            # Run just the backoff calculation — simulate disconnect handling
            # by calling the backoff helper directly
            delay = consumer._get_reconnect_delay()
            assert delay == LinuxConsumer.RECONNECT_DELAYS[0]

            consumer._reconnect_attempt = 1
            delay2 = consumer._get_reconnect_delay()
            assert delay2 == LinuxConsumer.RECONNECT_DELAYS[1]

            # At max index, should cap at 30s
            consumer._reconnect_attempt = 100
            delay_max = consumer._get_reconnect_delay()
            assert delay_max == 30.0

    @pytest.mark.asyncio
    async def test_reconnect_increments_attempt_counter(self) -> None:
        from src.execution.bridge.linux_consumer import LinuxConsumer

        consumer = LinuxConsumer()
        consumer._reconnect_attempt = 0
        consumer._running = False  # Will exit loop immediately

        # patch sleep so test doesn't block
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # _reconnect should increment the counter
            await consumer._reconnect()

        assert consumer._reconnect_attempt >= 1
