import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import status
from shared.database.schema.platform_connectors import PlatformConnector
from services.api_gateway.routers.chat_routers.instagram_webhook import get_db

@pytest.fixture
def override_webhook_db(test_client, mock_db_session):
    async def _get_db():
        yield mock_db_session
    test_client.app.dependency_overrides[get_db] = _get_db
    yield
    test_client.app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
@patch("services.api_gateway.routers.chat_routers.instagram_webhook.route_inbound_message")
async def test_instagram_webhook_ignores_seller_reply(
    mock_route, test_client, override_webhook_db, mock_db_session
):
    # Connector for sugam_pudasain (recipient)
    recipient_connector = PlatformConnector(
        business_id="b3754942-862a-3a94-06a2-f1daae851b5f",
        platform="instagram",
        platform_account_id="sugam_pudasain_id",
        platform_account_name="sugam_pudasain",
        tokens={"access_token": "recipient-token"}
    )
    
    # Connector for paperjetlabs (sender)
    sender_connector = PlatformConnector(
        business_id="4942862a-3a94-06a2-f1da-ae851b5fb375",
        platform="instagram",
        platform_account_id="paperjetlabs_id",
        platform_account_name="paperjetlabs",
        tokens={"access_token": "sender-token"}
    )

    def mock_execute(stmt):
        params = stmt.compile().params
        res = MagicMock()
        if any(v == "sugam_pudasain_id" for v in params.values()):
            res.scalar_one_or_none.return_value = recipient_connector
        elif any(v == "paperjetlabs_id" for v in params.values()):
            res.scalar_one_or_none.return_value = sender_connector
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_db_session.execute = AsyncMock(side_effect=mock_execute)

    # Mock MongoDB
    mock_mongo = MagicMock()
    mock_mongo.conversations = AsyncMock()
    
    # CASE 1: We are the customer (paperjetlabs_id) of sugam_pudasain_id, so there is an existing conversation
    # under the sender's (sugam_pudasain_id) organization where recipient (paperjetlabs_id) is the customer.
    # In this case, paperjetlabs_id is receiving a message from sugam_pudasain_id.
    # The webhook recipient is paperjetlabs_id (connector), sender is sugam_pudasain_id (sender_connector).
    # Since recipient is paperjetlabs_id, we check if there is an existing conversation under sender_connector's
    # org (sugam_pudasain) where customer is paperjetlabs_id.
    mock_mongo.conversations.find_one = AsyncMock(return_value={"id": "existing-conversation"})

    # Messaging event payload: sugam_pudasain_id sends a reply to paperjetlabs_id
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "paperjetlabs_id",  # The webhook recipient/entry ID
                "messaging": [
                    {
                        "sender": {"id": "sugam_pudasain_id"},
                        "recipient": {"id": "paperjetlabs_id"},
                        "message": {
                            "mid": "mid.12345",
                            "text": "Hello, here is your order details"
                        }
                    }
                ]
            }
        ]
    }

    with patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_mongo):
        response = test_client.post("/webhooks/instagram", json=payload)
        
    assert response.status_code == status.HTTP_200_OK
    # verify route_inbound_message was NOT called (meaning the message was ignored)
    mock_route.assert_not_called()


@pytest.mark.asyncio
@patch("services.api_gateway.routers.chat_routers.instagram_webhook.route_inbound_message")
async def test_instagram_webhook_processes_inbound_from_registered_business_if_not_customer(
    mock_route, test_client, override_webhook_db, mock_db_session
):
    # Recipient: sugam_pudasain_id
    recipient_connector = PlatformConnector(
        business_id="b3754942-862a-3a94-06a2-f1daae851b5f",
        platform="instagram",
        platform_account_id="sugam_pudasain_id",
        platform_account_name="sugam_pudasain",
        tokens={"access_token": "recipient-token"}
    )
    
    # Sender: paperjetlabs_id
    sender_connector = PlatformConnector(
        business_id="4942862a-3a94-06a2-f1da-ae851b5fb375",
        platform="instagram",
        platform_account_id="paperjetlabs_id",
        platform_account_name="paperjetlabs",
        tokens={"access_token": "sender-token"}
    )

    def mock_execute(stmt):
        params = stmt.compile().params
        res = MagicMock()
        if any(v == "sugam_pudasain_id" for v in params.values()):
            res.scalar_one_or_none.return_value = recipient_connector
        elif any(v == "paperjetlabs_id" for v in params.values()):
            res.scalar_one_or_none.return_value = sender_connector
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_db_session.execute = AsyncMock(side_effect=mock_execute)

    mock_mongo = MagicMock()
    mock_mongo.conversations = AsyncMock()
    
    # CASE 2: recipient (sugam_pudasain_id) is NOT a customer of sender (paperjetlabs_id)'s business,
    # meaning sugam_pudasain_id has no existing conversation in paperjetlabs's org where sugam_pudasain_id is the customer.
    # Therefore, paperjetlabs_id is initiating a brand new customer conversation with sugam_pudasain_id.
    # This must be processed.
    mock_mongo.conversations.find_one = AsyncMock(return_value=None)

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "sugam_pudasain_id",
                "messaging": [
                    {
                        "sender": {"id": "paperjetlabs_id"},
                        "recipient": {"id": "sugam_pudasain_id"},
                        "message": {
                            "mid": "mid.67890",
                            "text": "Hi, I want to buy a graphics card"
                        }
                    }
                ]
            }
        ]
    }

    with patch("shared.database.mongodb.MongoDBManager.get_db", return_value=mock_mongo):
        response = test_client.post("/webhooks/instagram", json=payload)
        
    assert response.status_code == status.HTTP_200_OK
    # verify route_inbound_message was called because this is a new inbound query
    mock_route.assert_called_once()
