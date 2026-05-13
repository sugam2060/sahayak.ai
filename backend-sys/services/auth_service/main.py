import grpc
import asyncio
from concurrent import futures
from shared.proto import service_pb2_grpc, service_pb2
from shared.database.engine import SessionLocal
from shared.database.schema.users import User
from sqlalchemy import select
from shared.config import AUTH_SERVICE_ADDR

from services.auth_service.registration import handle_registration
from services.auth_service.verification import handle_verify_email
from services.auth_service.login import handle_login
from services.auth_service.verify_token import handle_verify_access_token
from services.auth_service.refresh import handle_refresh_token

class AuthService(service_pb2_grpc.AuthServiceServicer):
    async def Login(self, request, context):
        try:
            return await handle_login(request)
        except Exception as e:
            import traceback
            traceback.print_exc()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
            return service_pb2.LoginResponse(success=False, message="An internal error occurred.")

    async def Register(self, request, context):
        try:
            return await handle_registration(request)
        except ValueError as e:
            # Human-friendly errors (already sanitized in registration.py)
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            context.set_details(str(e))
            return service_pb2.RegisterResponse()
        except Exception as e:
            import traceback
            traceback.print_exc()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
            return service_pb2.RegisterResponse()

    async def VerifyEmail(self, request, context):
        try:
            return await handle_verify_email(request)
        except Exception as e:
            import traceback
            traceback.print_exc()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
            return service_pb2.VerifyEmailResponse(success=False, message="An internal error occurred.")

    async def VerifyAccessToken(self, request, context):
        try:
            return await handle_verify_access_token(request)
        except Exception as e:
            import traceback
            traceback.print_exc()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
            return service_pb2.VerifyAccessTokenResponse(valid=False, message="An internal error occurred.")

    async def RefreshToken(self, request, context):
        try:
            return await handle_refresh_token(request)
        except Exception as e:
            import traceback
            traceback.print_exc()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal server error")
            return service_pb2.RefreshTokenResponse(success=False, message="An internal error occurred.")

async def serve():
    server = grpc.aio.server()
    service_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    port = AUTH_SERVICE_ADDR.split(":")[-1]
    server.add_insecure_port(f'[::]:{port}')
    print("Auth Service starting on port 50051...")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
