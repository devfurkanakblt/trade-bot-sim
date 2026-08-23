import requests

PUSHBULLET_API_URL = "https://api.pushbullet.com/v2/pushes"


class NotifierError(Exception):
    pass


class PushbulletNotifier:
    def __init__(
        self,
        access_token: str,
        api_url: str = PUSHBULLET_API_URL,
        proxy_token: str = "",
    ):
        self.access_token = access_token
        self.api_url = api_url
        self.proxy_token = proxy_token

    def send_report(self, title: str, body: str) -> None:
        try:
            headers = {"Access-Token": self.access_token, "Content-Type": "application/json"}
            if self.proxy_token:
                headers["X-Proxy-Token"] = self.proxy_token
            response = requests.post(
                self.api_url,
                headers=headers,
                json={"type": "note", "title": title, "body": body},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Failed to send Pushbullet notification: {exc}") from exc
