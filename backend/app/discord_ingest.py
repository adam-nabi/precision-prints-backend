import json
import os
from dataclasses import dataclass
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://discord.com/api/v10"


class DiscordConfigError(RuntimeError):
    pass


@dataclass
class DiscordMessage:
    message_id: str
    channel_id: str
    author_name: str
    content: str
    source_url: Optional[str]


@dataclass
class _DiscordConfig:
    bot_token: str
    channel_ids: List[str]
    limit_per_channel: int


def fetch_recent_messages() -> List[DiscordMessage]:
    config = _load_config()
    headers = {
        "Authorization": f"Bot {config.bot_token}",
        "Content-Type": "application/json",
    }

    messages: List[DiscordMessage] = []

    for channel_id in config.channel_ids:
        query = urlencode({"limit": config.limit_per_channel})
        endpoint = f"{API_BASE_URL}/channels/{channel_id}/messages?{query}"
        request = Request(endpoint, headers=headers)
        payload = _read_json(request)

        for item in payload:
            author = item.get("author", {})
            if author.get("bot"):
                continue

            message_id = str(item.get("id", ""))
            if not message_id:
                continue

            text_parts = []
            content = str(item.get("content", "")).strip()
            if content:
                text_parts.append(content)

            for attachment in item.get("attachments", []):
                url = attachment.get("url")
                if url:
                    text_parts.append(str(url))

            if not text_parts:
                continue

            guild_id = item.get("guild_id")
            source_url = None
            if guild_id:
                source_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"

            display_name = (
                author.get("global_name")
                or author.get("username")
                or author.get("id")
                or "Discord User"
            )

            messages.append(
                DiscordMessage(
                    message_id=message_id,
                    channel_id=channel_id,
                    author_name=str(display_name),
                    content="\n".join(text_parts),
                    source_url=source_url,
                )
            )

    return messages


def _load_config() -> _DiscordConfig:
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    channel_ids = [item.strip() for item in os.getenv("DISCORD_CHANNEL_IDS", "").split(",") if item.strip()]
    limit_per_channel = int(os.getenv("DISCORD_LIMIT", "25"))

    if not bot_token or not channel_ids:
        raise DiscordConfigError("Missing Discord config. Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_IDS.")

    return _DiscordConfig(
        bot_token=bot_token,
        channel_ids=channel_ids,
        limit_per_channel=max(limit_per_channel, 1),
    )


def _read_json(request: Request):
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="ignore")
        raise DiscordConfigError(f"Discord request failed with HTTP {error.code}: {message}") from error
    except URLError as error:
        raise DiscordConfigError("Could not reach Discord.") from error
