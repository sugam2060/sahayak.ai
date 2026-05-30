import grpc
import logging
from shared.proto import service_pb2_grpc
from services.workers.products.handlers import ProductService
from services.workers.orders.handlers import OrderService

logger = logging.getLogger("workers.grpc_server")

async def start_grpc_server():
    from shared.config import WORKERS_SERVICE_ADDR
    server = grpc.aio.server()
    
    # Register stubs
    service_pb2_grpc.add_ProductServiceServicer_to_server(ProductService(), server)
    service_pb2_grpc.add_OrderServiceServicer_to_server(OrderService(), server)
    
    port = WORKERS_SERVICE_ADDR.split(":")[-1]
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"Workers gRPC Server starting on port {port}...")
    await server.start()
    return server
