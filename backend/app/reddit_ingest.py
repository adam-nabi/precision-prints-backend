import base64
import json
import os
from dataclasses import dataclass
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE_URL = "https://oauth.reddit.com"


class RedditConfigError(RuntimeError):
    pass


@dataclass
class RedditPost:
    post_id: str
    title: str
    selftext: str
    author: str
    permalink: str
    outbound_url: Optional[str]
    subreddit: str


def fetch_recent_posts() -> List[RedditPost]:
    config = _load_config()
    access_token = _fetch_access_token(config)
    headers = {
        "Authorization": f"bearer {access_token}",
        "User-Agent": config.user_agent,
    }

    posts: List[RedditPost] = []
    for subreddit in config.subreddits:
        endpoint = f"{API_BASE_URL}/r/{subreddit}/new?limit={config.limit_per_subreddit}"
        request = Request(endpoint, headers=headers)
        payload = _read_json(request)
        children = payload.get("data", {}).get("children", [])

        for child in children:
            data = child.get("data", {})
            posts.append(
                RedditPost(
                    post_id=str(data.get("id", "")),
                    title=str(data.get("title", "")),
                    selftext=str(data.get("selftext", "")),
                    author=f"u/{data.get('author', 'unknown')}",
                    permalink=f"https://reddit.com{data.get('permalink', '')}",
                    outbound_url=data.get("url"),
                    subreddit=subreddit,
                )
            )

    return posts


@dataclass
class _RedditConfig:
    client_id: str
    client_secret: str
    username: str
    password: str
    user_agent: str
    subreddits: List[str]
    limit_per_subreddit: int


def _load_config() -> _RedditConfig:
    client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
    username = os.getenv("REDDIT_USERNAME", "").strip()
    password = os.getenv("REDDIT_PASSWORD", "").strip()
    user_agent = os.getenv("REDDIT_USER_AGENT", "PrecisionPrintsBot/0.1").strip()
    subreddits = [item.strip() for item in os.getenv("REDDIT_SUBREDDITS", "").split(",") if item.strip()]
    limit_per_subreddit = int(os.getenv("REDDIT_LIMIT", "10"))

    if not all([client_id, client_secret, username, password]) or not subreddits:
        raise RedditConfigError(
            "Missing Reddit config. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, "
            "REDDIT_PASSWORD, and REDDIT_SUBREDDITS."
        )

    return _RedditConfig(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=user_agent,
        subreddits=subreddits,
        limit_per_subreddit=max(limit_per_subreddit, 1),
    )


def _fetch_access_token(config: _RedditConfig) -> str:
    auth_value = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode("utf-8")).decode("utf-8")
    body = urlencode(
        {
            "grant_type": "password",
            "username": config.username,
            "password": config.password,
        }
    ).encode("utf-8")
    request = Request(
        OAUTH_TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {auth_value}",
            "User-Agent": config.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    payload = _read_json(request)
    access_token = payload.get("access_token")
    if not access_token:
        raise RedditConfigError("Reddit access token was not returned.")

    return str(access_token)


def _read_json(request: Request) -> dict:
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="ignore")
        raise RedditConfigError(f"Reddit request failed with HTTP {error.code}: {message}") from error
    except URLError as error:
        raise RedditConfigError("Could not reach Reddit.") from error
