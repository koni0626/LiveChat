from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import mimetypes
import os
import re
import socket
import uuid
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from flask import current_app
import requests

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..repositories.feed_repository import FeedRepository
from ..utils import json_util
from .asset_service import AssetService
from .character_service import CharacterService
from .project_service import ProjectService
from .world_service import WorldService


class _MetaTagParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attr_map = {str(key).lower(): value for key, value in attrs}
        key = attr_map.get("property") or attr_map.get("name")
        content = attr_map.get("content")
        if key and content:
            self.meta[str(key).strip().lower()] = unescape(str(content).strip())


class FeedService:
    VALID_STATUSES = {"draft", "published", "archived"}

    def __init__(
        self,
        repository: FeedRepository | None = None,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._repo = repository or FeedRepository()
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _serialize_asset(self, asset):
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "media_url": self._media_url(asset.file_path),
            "width": asset.width,
            "height": asset.height,
        }

    def _serialize_character(self, character):
        if not character:
            return None
        thumbnail = self._asset_service.get_asset(character.thumbnail_asset_id) if character.thumbnail_asset_id else None
        base_asset = self._asset_service.get_asset(character.base_asset_id) if character.base_asset_id else None
        return {
            "id": character.id,
            "project_id": character.project_id,
            "name": character.name,
            "nickname": character.nickname,
            "thumbnail_asset": self._serialize_asset(thumbnail),
            "base_asset": self._serialize_asset(base_asset),
        }

    def _serialize_project(self, project):
        if not project:
            return None
        thumbnail = self._asset_service.get_asset(project.thumbnail_asset_id) if project.thumbnail_asset_id else None
        return {
            "id": project.id,
            "title": project.title,
            "summary": project.summary,
            "status": project.status,
            "thumbnail_asset": self._serialize_asset(thumbnail),
        }

    def _load_json(self, value):
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def serialize_post(self, post, *, liked_by_me: bool = False, can_manage: bool = False):
        character = self._character_service.get_character(post.character_id)
        project = self._project_service.get_project(post.project_id)
        image_asset = self._asset_service.get_asset(post.image_asset_id) if post.image_asset_id else None
        return {
            "id": post.id,
            "project_id": post.project_id,
            "character_id": post.character_id,
            "created_by_user_id": post.created_by_user_id,
            "body": post.body,
            "image_asset_id": post.image_asset_id,
            "image_asset": self._serialize_asset(image_asset),
            "status": post.status,
            "like_count": post.like_count or 0,
            "liked_by_me": liked_by_me,
            "can_manage": can_manage,
            "generation_state": self._load_json(post.generation_state_json),
            "character": self._serialize_character(character),
            "project": self._serialize_project(project),
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        }

    def list_posts(self, *, user, can_manage_project_func, project_id=None, character_id=None, search=None, status=None, limit=50):
        statuses = None
        if status:
            statuses = [status] if status in self.VALID_STATUSES else ["published"]
        rows = self._repo.list_posts(
            project_id=project_id,
            character_id=character_id,
            statuses=statuses,
            search=search,
            limit=limit,
        )
        visible = []
        for row in rows:
            project = self._project_service.get_project(row.project_id)
            can_manage = can_manage_project_func(user, project)
            can_edit = can_manage or row.created_by_user_id == user.id
            if row.status == "published" or can_edit:
                visible.append((row, can_edit))
        liked_ids = self._repo.liked_post_ids([row.id for row, _ in visible], user.id)
        return [
            self.serialize_post(row, liked_by_me=row.id in liked_ids, can_manage=can_manage)
            for row, can_manage in visible
        ]

    def get_post(self, post_id: int):
        return self._repo.get_post(post_id)

    def character_post_ranking(self, *, limit: int = 10, project_id: int | None = None):
        rows = self._repo.character_post_ranking(limit=limit, project_id=project_id, published_only=True)
        return [
            {
                "rank": index + 1,
                "post_count": int(post_count or 0),
                "character": self._serialize_character(character),
                "project": self._serialize_project(project),
            }
            for index, (character, project, post_count) in enumerate(rows)
        ]

    def create_post(self, *, project_id: int, user_id: int, payload: dict):
        body = str(payload.get("body") or "").strip()
        if not body:
            raise ValueError("本文を入力してください。")
        if len(body) > 10000:
            raise ValueError("本文は10000文字以内で入力してください。")
        character_id = int(payload.get("character_id") or 0)
        character = self._character_service.get_character(character_id)
        if not character or character.project_id != project_id:
            raise ValueError("キャラクターを選択してください。")
        status = str(payload.get("status") or "draft")
        if status not in self.VALID_STATUSES:
            status = "draft"
        post = self._repo.create_post(
            {
                "project_id": project_id,
                "character_id": character_id,
                "created_by_user_id": user_id,
                "body": body,
                "image_asset_id": payload.get("image_asset_id"),
                "status": status,
            }
        )
        self.refresh_character_feed_profile(character_id)
        return post

    def generate_posts(self, *, project_id: int, user_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        count = max(1, min(5, int(payload.get("count") or 1)))
        candidates = self._generate_feed_candidates(project_id, count=count)
        created = []
        for candidate in candidates[:count]:
            character_id = int(candidate.get("character_id") or 0)
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != project_id:
                continue
            body = str(candidate.get("body") or "").strip()
            if not body:
                continue
            post = self._repo.create_post(
                {
                    "project_id": project_id,
                    "character_id": character.id,
                    "created_by_user_id": user_id,
                    "body": body[:10000],
                    "status": "published",
                    "generation_state_json": json_util.dumps(
                        {
                            "source": "feed_auto_generate",
                            "generated_at": datetime.utcnow().isoformat(),
                            "candidate": candidate,
                        }
                    ),
                }
            )
            post = self.generate_post_image(post.id, payload) or post
            self.refresh_character_feed_profile(character.id)
            created.append(post)
        if not created:
            raise RuntimeError("feed auto generation did not create any posts")
        return created

    def update_post(self, post_id: int, payload: dict):
        normalized = {}
        current_post = self._repo.get_post(post_id)
        if not current_post:
            return None
        previous_character_id = current_post.character_id
        if "body" in payload:
            body = str(payload.get("body") or "").strip()
            if not body:
                raise ValueError("本文を入力してください。")
            if len(body) > 10000:
                raise ValueError("本文は10000文字以内で入力してください。")
            normalized["body"] = body
        if "character_id" in payload:
            character_id = int(payload.get("character_id") or 0)
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != current_post.project_id:
                raise ValueError("同じワールドのキャラクターを選択してください。")
            normalized["character_id"] = character_id
        if "image_asset_id" in payload:
            normalized["image_asset_id"] = payload.get("image_asset_id") or None
        if "status" in payload:
            status = str(payload.get("status") or "draft")
            normalized["status"] = status if status in self.VALID_STATUSES else "draft"
        post = self._repo.update_post(post_id, normalized)
        if post:
            if previous_character_id != post.character_id:
                self.refresh_character_feed_profile(previous_character_id)
            self.refresh_character_feed_profile(post.character_id)
        return post

    def delete_post(self, post_id: int):
        post = self._repo.get_post(post_id)
        deleted = self._repo.delete_post(post_id)
        if post:
            self.refresh_character_feed_profile(post.character_id)
        return deleted

    def set_like(self, post_id: int, user_id: int, liked: bool):
        return self._repo.set_like(post_id, user_id, liked)

    def import_from_url(self, project_id: int, url: str):
        normalized_url = self._normalize_import_url(url)
        html_text = self._fetch_url_html(normalized_url)
        metadata = self._extract_url_metadata(html_text)
        if self._is_x_url(normalized_url):
            metadata = {**metadata, **self._extract_x_metadata(html_text)}
        body = self._clean_imported_body(
            metadata.get("og:description")
            or metadata.get("twitter:description")
            or metadata.get("description")
            or metadata.get("x:full_text")
            or metadata.get("og:title")
            or metadata.get("twitter:title")
            or ""
        )
        image_url = (
            metadata.get("og:image")
            or metadata.get("twitter:image")
            or metadata.get("twitter:image:src")
            or metadata.get("x:image")
        )
        asset = self._download_import_image(project_id, image_url, source_url=normalized_url) if image_url else None
        if not body and not asset:
            raise ValueError("URLから本文または画像を取得できませんでした。")
        return {
            "source_url": normalized_url,
            "body": body,
            "image_asset": self._serialize_asset(asset),
            "metadata": {
                "title": metadata.get("og:title") or metadata.get("twitter:title") or "",
                "image_url": image_url,
            },
        }

    def _normalize_import_url(self, url: str):
        value = str(url or "").strip()
        if not value:
            raise ValueError("URLを入力してください。")
        match = re.search(r"https?://[^\s]+", value)
        value = match.group(0).rstrip("）。),]") if match else value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("httpまたはhttpsのURLを入力してください。")
        return value

    def _fetch_url_html(self, url: str):
        response = self._safe_get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise ValueError(f"URLの取得に失敗しました。HTTP {response.status_code}")
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValueError("HTMLページではないため取り込めません。")
        return response.text

    def _extract_url_metadata(self, html_text: str):
        parser = _MetaTagParser()
        parser.feed(html_text or "")
        return parser.meta

    def _is_x_url(self, url: str):
        hostname = (urlparse(url).hostname or "").lower()
        return hostname in {"x.com", "twitter.com", "www.x.com", "www.twitter.com", "mobile.twitter.com"}

    def _decode_json_string_fragment(self, value: str):
        try:
            return json_util.loads(f'"{value}"')
        except Exception:
            try:
                return bytes(value, "utf-8").decode("unicode_escape")
            except Exception:
                return value

    def _extract_x_metadata(self, html_text: str):
        metadata = {}
        text = html_text or ""
        full_text_match = re.search(r'"full_text"\s*:\s*"((?:\\.|[^"\\])*)"', text)
        if full_text_match:
            metadata["x:full_text"] = self._decode_json_string_fragment(full_text_match.group(1))
        image_match = re.search(r'"media_url_https"\s*:\s*"(https://pbs\.twimg\.com/media/[^"\\]+)"', text)
        if not image_match:
            image_match = re.search(r'(https://pbs\.twimg\.com/media/[^"\\<> ]+)', text)
        if image_match:
            metadata["x:image"] = self._decode_json_string_fragment(image_match.group(1))
        return metadata

    def _clean_imported_body(self, text: str):
        value = unescape(str(text or "")).strip()
        if not value:
            return ""
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"^.+?\s+on\s+X:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^.+?\s+on\s+Twitter:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+https?://t\.co/\S+", "", value)
        value = re.sub(r"\s+pic\.twitter\.com/\S+", "", value, flags=re.IGNORECASE)
        value = value.strip(" \n\r\t\"'")
        return value[:10000]

    def _download_import_image(self, project_id: int, image_url: str | None, *, source_url: str):
        if not image_url:
            return None
        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"}:
            return None
        response = self._safe_get(
            image_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*,*/*;q=0.8"},
            timeout=20,
            stream=True,
        )
        if response.status_code >= 400:
            return None
        mime_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if not mime_type.startswith("image/"):
            return None
        max_bytes = int(current_app.config.get("FEED_IMPORT_IMAGE_MAX_BYTES", 10 * 1024 * 1024))
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("image is too large")
        raw_bytes = response.content
        if not raw_bytes:
            return None
        if len(raw_bytes) > max_bytes:
            raise ValueError("image is too large")
        extension = mimetypes.guess_extension(mime_type) or ".jpg"
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "assets", "feed_import")
        os.makedirs(output_dir, exist_ok=True)
        file_name = f"feed_import_{uuid.uuid4().hex[:12]}{extension}"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "feed_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": mime_type,
                "file_size": len(raw_bytes),
                "checksum": hashlib.sha256(raw_bytes).hexdigest(),
                "metadata_json": json_util.dumps(
                    {
                        "source": "feed_url_import",
                        "source_url": source_url,
                        "image_url": image_url,
                    }
                ),
            },
        )

    def _safe_get(self, url: str, *, headers: dict, timeout: int, stream: bool = False):
        current_url = url
        for _ in range(4):
            self._validate_public_http_url(current_url)
            response = requests.get(
                current_url,
                headers=headers,
                timeout=timeout,
                stream=stream,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("location")
                if not location:
                    return response
                current_url = urljoin(current_url, location)
                continue
            return response
        raise ValueError("too many redirects")

    def _validate_public_http_url(self, url: str):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("httpまたはhttpsのURLを入力してください。")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            addresses = socket.getaddrinfo(parsed.hostname, port)
        except socket.gaierror as exc:
            raise ValueError("URLの名前解決に失敗しました。") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ValueError("このURLは取り込めません。")

    def upload_post_image(self, post_id: int, upload_file):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        asset = self._asset_service.create_asset(
            post.project_id,
            {
                "asset_type": "feed_image",
                "upload_file": upload_file,
            },
        )
        post = self._repo.update_post(post.id, {"image_asset_id": asset.id})
        return post

    def generate_post_image(self, post_id: int, payload: dict | None = None):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        payload = dict(payload or {})
        character = self._character_service.get_character(post.character_id)
        project = self._project_service.get_project(post.project_id)
        world = self._world_service.get_world(post.project_id)
        prompt = self._build_feed_image_prompt(post, character, project, world, payload)
        reference_paths = []
        reference_ids = []
        if character and character.base_asset_id:
            base_asset = self._asset_service.get_asset(character.base_asset_id)
            if base_asset and os.path.exists(base_asset.file_path):
                reference_paths.append(base_asset.file_path)
                reference_ids.append(base_asset.id)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1536x1024",
            quality=payload.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_feed_image(post.project_id, post.id, image_base64)
        asset = self._asset_service.create_asset(
            post.project_id,
            {
                "asset_type": "feed_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "feed_post_image",
                        "feed_post_id": post.id,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_ids,
                        "model": result.get("model"),
                    }
                ),
            },
        )
        post = self._repo.update_post(
            post.id,
            {
                "image_asset_id": asset.id,
                "generation_state_json": json_util.dumps(
                    {
                        "image_prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "generated_at": datetime.utcnow().isoformat(),
                        "reference_asset_ids": reference_ids,
                    }
                ),
            },
        )
        return post

    def _generate_feed_candidates(self, project_id: int, *, count: int):
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        characters = self._character_service.list_characters(project_id)[:20]
        if not characters:
            raise ValueError("character is required to generate Feed posts")
        recent_posts = self._repo.list_posts(project_id=project_id, statuses=["published"], limit=20)
        prompt = f"""
Return only JSON.
Create {count} public Feed posts for a Japanese character world app.
Each item is a short official character post, not a news article and not a chat reply.

Required shape:
{{"items":[{{"character_id": 1, "body": "..."}}]}}

Rules:
- Japanese only.
- Use only provided character IDs.
- Keep each body 80-220 Japanese characters.
- Match the selected character's personality and speech style.
- Make the post feel like a public character broadcast: daily note, small discovery, place recommendation, mood, teaser, or social update.
- Do not mention that AI generated the post.
- Avoid duplicating recent posts.

Project: {getattr(project, "title", "") or ""}
Project summary: {getattr(project, "summary", "") or ""}
World tone: {getattr(world, "tone", "") if world else ""}
World overview: {getattr(world, "overview", "") if world else ""}
Characters: {json_util.dumps([self._feed_character_context(character) for character in characters])}
Recent posts: {json_util.dumps([{"character_id": post.character_id, "body": post.body} for post in recent_posts[:12]])}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=1200,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        items = parsed.get("items") if isinstance(parsed, dict) else []
        if isinstance(items, list) and items:
            return [item for item in items if isinstance(item, dict)]
        return self._fallback_feed_candidates(characters, count)

    def _fallback_feed_candidates(self, characters, count: int):
        items = []
        for index in range(count):
            character = characters[index % len(characters)]
            name = getattr(character, "name", "") or "私"
            items.append(
                {
                    "character_id": character.id,
                    "body": f"{name}です。今日は街の空気が少し違って感じられました。気になる場所をひとつ見つけたので、また近いうちに話せたらうれしいです。",
                }
            )
        return items

    def _feed_character_context(self, character) -> dict:
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "personality": character.personality,
            "speech_style": character.speech_style,
            "appearance": character.appearance_summary,
        }

    def _build_feed_image_prompt(self, post, character, project, world, payload: dict):
        override = str(payload.get("prompt") or "").strip()
        if override:
            return override
        lines = [
            "Create a polished promotional Feed image for a character conversation app.",
            "Use the reference image as the primary source of character identity and art style.",
            "Keep the same face, hair, outfit design logic, linework, coloring, rendering quality, and mood.",
            "No text, no captions, no speech bubbles, no readable signs, no UI, no logo, no watermark.",
            "Show one character as the main subject. Do not show the player.",
            "Make it feel like an official character post image, daily snapshot, or visual novel event CG.",
            f"Feed post body: {post.body}",
        ]
        if project:
            lines.append(f"World: {project.title}. {project.summary or ''}")
        if world:
            lines.append(f"World setting: {world.overview or ''} {world.tone or ''}")
        if character:
            lines.append(f"Character: {character.name}")
            if character.nickname:
                lines.append(f"Nickname: {character.nickname}")
            if character.appearance_summary:
                lines.append(f"Appearance: {character.appearance_summary}")
            if character.personality:
                lines.append(f"Personality: {character.personality}")
            if character.art_style:
                lines.append(f"Art style: {character.art_style}")
            if character.ng_rules:
                lines.append(f"Never violate: {character.ng_rules}")
        lines.append("If safety-sensitive wording appears in the post, preserve intent while converting it into tasteful, non-explicit visual novel promotional art.")
        return "\n".join(lines)

    def _store_generated_feed_image(self, project_id: int, post_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "generated", "feed", str(post_id))
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_name = f"feed_{post_id}_{timestamp}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def refresh_character_feed_profile(self, character_id: int):
        posts = self._repo.list_posts(character_id=character_id, statuses=["published"], limit=80)
        latest_id = posts[0].id if posts else None
        if not posts:
            return self._repo.upsert_profile(
                character_id,
                {"profile_text": "", "source_post_count": 0, "source_latest_post_id": None, "summary_state_json": None},
            )
        try:
            profile = self._generate_feed_profile(character_id, posts)
        except Exception:
            current_app.logger.exception("feed profile refresh failed")
            return self._repo.get_profile(character_id)
        return self._repo.upsert_profile(
            character_id,
            {
                "profile_text": profile.get("profile_text") or "",
                "source_post_count": len(posts),
                "source_latest_post_id": latest_id,
                "summary_state_json": json_util.dumps(profile),
            },
        )

    def _generate_feed_profile(self, character_id: int, posts):
        character = self._character_service.get_character(character_id)
        post_lines = "\n".join(f"- {post.body}" for post in posts[:40])
        prompt = f"""
Return only JSON.
Summarize public Feed posts into a compact character profile supplement for live chat.
Do not overwrite explicit character settings. Extract tendencies visible from posts.

JSON keys:
{{
  "profile_text": "Japanese summary, 400 chars max",
  "likes": ["..."],
  "speech_tendencies": ["..."],
  "conversation_hooks": ["..."]
}}

Character:
name: {getattr(character, "name", "")}
nickname: {getattr(character, "nickname", "")}
personality: {getattr(character, "personality", "")}
speech_style: {getattr(character, "speech_style", "")}

Feed posts:
{post_lines}
"""
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.35,
            response_format={"type": "json_object"},
            max_tokens=900,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        return parsed if isinstance(parsed, dict) else {"profile_text": ""}

    def get_character_feed_profile(self, character_id: int):
        profile = self._repo.get_profile(character_id)
        if not profile:
            return None
        return {
            "character_id": profile.character_id,
            "profile_text": profile.profile_text or "",
            "source_post_count": profile.source_post_count or 0,
            "source_latest_post_id": profile.source_latest_post_id,
            "summary_state": self._load_json(profile.summary_state_json),
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
