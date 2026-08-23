from unittest.mock import Mock, patch

import pytest
import requests

from src.notifier.pushbullet_notifier import NotifierError, PushbulletNotifier


def make_response(status_ok=True):
    resp = Mock()
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.RequestException("boom")
    return resp


@patch("src.notifier.pushbullet_notifier.requests.post")
def test_send_report_posts_note_to_pushbullet_api(mock_post):
    mock_post.return_value = make_response()

    notifier = PushbulletNotifier("fake-token")
    notifier.send_report("Trade Bot Sim - Daily Report", "report body text")

    mock_post.assert_called_once_with(
        "https://api.pushbullet.com/v2/pushes",
        headers={"Access-Token": "fake-token", "Content-Type": "application/json"},
        json={"type": "note", "title": "Trade Bot Sim - Daily Report", "body": "report body text"},
        timeout=10,
    )


@patch("src.notifier.pushbullet_notifier.requests.post")
def test_proxy_report_uses_custom_url_and_authentication_header(mock_post):
    mock_post.return_value = make_response()
    notifier = PushbulletNotifier(
        "pushbullet-token",
        api_url="https://trade-bot-proxy.example.workers.dev/pushbullet/v2/pushes",
        proxy_token="proxy-secret",
    )

    notifier.send_report("Title", "Body")

    mock_post.assert_called_once_with(
        "https://trade-bot-proxy.example.workers.dev/pushbullet/v2/pushes",
        headers={
            "Access-Token": "pushbullet-token",
            "Content-Type": "application/json",
            "X-Proxy-Token": "proxy-secret",
        },
        json={"type": "note", "title": "Title", "body": "Body"},
        timeout=10,
    )


@patch("src.notifier.pushbullet_notifier.requests.post")
def test_send_report_raises_notifier_error_on_failure(mock_post):
    mock_post.return_value = make_response(status_ok=False)

    notifier = PushbulletNotifier("fake-token")
    with pytest.raises(NotifierError):
        notifier.send_report("Title", "Body")
