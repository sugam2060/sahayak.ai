"""
Singleton gRPC client for the Workers service.
Provides order, product, and ticket stubs for AI agent tools.
"""
import logging
import grpc
from shared.config import WORKERS_SERVICE_ADDR
from shared.proto import service_pb2_grpc

logger = logging.getLogger("chatai_service.ai.grpc_client")


class WorkersGRPCClient:
    """
    Manages a single gRPC channel to the Workers service and exposes
    typed stubs for OrderService, ProductService, and TicketService.
    
    Usage:
        order_stub, product_stub, ticket_stub = WorkersGRPCClient.get_stubs()
    """
    _channel: grpc.aio.Channel = None
    _order_stub: service_pb2_grpc.OrderServiceStub = None
    _product_stub: service_pb2_grpc.ProductServiceStub = None
    _ticket_stub: service_pb2_grpc.TicketServiceStub = None

    @classmethod
    def get_stubs(cls):
        """
        Lazily initializes and returns the gRPC stubs.
        
        Returns:
            Tuple of (OrderServiceStub, ProductServiceStub, TicketServiceStub)
        """
        if cls._channel is None:
            logger.info(f"Initializing gRPC channel to Workers at {WORKERS_SERVICE_ADDR}")
            cls._channel = grpc.aio.insecure_channel(WORKERS_SERVICE_ADDR)
            cls._order_stub = service_pb2_grpc.OrderServiceStub(cls._channel)
            cls._product_stub = service_pb2_grpc.ProductServiceStub(cls._channel)
            cls._ticket_stub = service_pb2_grpc.TicketServiceStub(cls._channel)
        return cls._order_stub, cls._product_stub, cls._ticket_stub

    @classmethod
    async def close(cls):
        """Gracefully close the gRPC channel."""
        if cls._channel is not None:
            logger.info("Closing gRPC channel to Workers service.")
            await cls._channel.close()
            cls._channel = None
            cls._order_stub = None
            cls._product_stub = None
            cls._ticket_stub = None
