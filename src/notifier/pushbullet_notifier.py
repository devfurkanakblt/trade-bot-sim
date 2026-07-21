import requests

PUSHBULLET_API_URL = "https://api.pushbullet.com/v2/pushes"


class NotifierError(Exception):
    pass


class PushbulletNotifier:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def send_report(self, title: str, body: str) -> None:
        try:
            response = requests.post(
                PUSHBULLET_API_URL,
                headers={"Access-Token": self.access_token, "Content-Type": "application/json"},
                json={"type": "note", "title": title, "body": body},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Failed to send Pushbullet notification: {exc}") from exc
