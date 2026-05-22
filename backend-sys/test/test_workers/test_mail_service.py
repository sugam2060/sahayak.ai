import pytest
from unittest.mock import MagicMock, patch
from services.workers.mail_service import send_verification_email

@patch("smtplib.SMTP")
def test_send_verification_email_success(mock_smtp_class):
    # Mock SMTP instance methods
    mock_smtp_instance = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance
    
    email = "recipient@example.com"
    subject = "Verify your account"
    html_content = "<p>Click here to verify</p>"
    
    # Run the task
    with patch("services.workers.mail_service.SMTP_USER", "user@example.com"), \
         patch("services.workers.mail_service.SMTP_PASSWORD", "password123"):
        result = send_verification_email(email, subject, html_content)
        
        assert result is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user@example.com", "password123")
        mock_smtp_instance.sendmail.assert_called_once()

@patch("smtplib.SMTP")
def test_send_verification_email_smtp_failure(mock_smtp_class):
    # Mock SMTP failure
    mock_smtp_instance = MagicMock()
    mock_smtp_instance.sendmail.side_effect = Exception("SMTP error")
    mock_smtp_class.return_value.__enter__.return_value = mock_smtp_instance
    
    email = "recipient@example.com"
    subject = "Verify your account"
    html_content = "<p>Click here to verify</p>"
    
    with pytest.raises(Exception) as exc_info:
        send_verification_email(email, subject, html_content)
        
    assert "SMTP error" in str(exc_info.value)
