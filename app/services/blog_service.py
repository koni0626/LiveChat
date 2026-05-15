from __future__ import annotations

import base64
import binascii
import os
import re
from datetime import datetime, timedelta

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..extensions import db
from ..models.blog_x_schedule import BlogXSchedule
from ..repositories.blog_repository import BlogRepository
from ..utils import json_util
from .asset_service import AssetService
from .character_service import CharacterService
from .project_service import ProjectService
from .world_service import WorldService
from .x_publishing_service import XPublishingService


class BlogService:
    VALID_STATUSES = {"draft", "published", "archived"}

    def __init__(
        self,
        repository: BlogRepository | None = None,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        x_publishing_service: XPublishingService | None = None,
    ):
        self._repo = repository or BlogRepository()
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._x_publishing_service = x_publishing_service or XPublishingService(asset_service=self._asset_service)

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

    def _load_json(self, value):
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

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
        return {
            "id": project.id,
            "title": project.title,
            "summary": project.summary,
            "status": project.status,
        }

    def _active_x_schedule_for_post(self, post_id: int):
        return (
            BlogXSchedule.query.filter(
                BlogXSchedule.blog_post_id == post_id,
                BlogXSchedule.status == "scheduled",
            )
            .order_by(BlogXSchedule.scheduled_for.asc(), BlogXSchedule.id.asc())
            .first()
        )

    def _serialize_x_schedule(self, schedule):
        if not schedule:
            return None
        return {
            "id": schedule.id,
            "blog_post_id": schedule.blog_post_id,
            "project_id": schedule.project_id,
            "created_by_user_id": schedule.created_by_user_id,
            "scheduled_for": schedule.scheduled_for.isoformat() if schedule.scheduled_for else None,
            "status": schedule.status,
            "x_post_id": schedule.x_post_id,
            "error_message": schedule.error_message,
            "metadata": self._load_json(schedule.metadata_json),
            "posted_at": schedule.posted_at.isoformat() if schedule.posted_at else None,
            "cancelled_at": schedule.cancelled_at.isoformat() if schedule.cancelled_at else None,
            "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
            "updated_at": schedule.updated_at.isoformat() if schedule.updated_at else None,
        }

    def serialize_post(self, post, *, can_manage: bool = False):
        character = self._character_service.get_character(post.character_id)
        project = self._project_service.get_project(post.project_id)
        thumbnail_asset = self._asset_service.get_asset(post.thumbnail_asset_id) if post.thumbnail_asset_id else None
        return {
            "id": post.id,
            "project_id": post.project_id,
            "character_id": post.character_id,
            "created_by_user_id": post.created_by_user_id,
            "theme": post.theme,
            "instruction": post.instruction,
            "body": post.body,
            "thumbnail_asset_id": post.thumbnail_asset_id,
            "thumbnail_asset": self._serialize_asset(thumbnail_asset),
            "status": post.status,
            "can_manage": can_manage,
            "x_schedule": self._serialize_x_schedule(self._active_x_schedule_for_post(post.id)),
            "generation_state": self._load_json(post.generation_state_json),
            "character": self._serialize_character(character),
            "project": self._serialize_project(project),
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        }

    def list_posts(self, *, user, can_manage_project_func, project_id=None, character_id=None, search=None, status=None, limit=50, offset=0):
        statuses = None
        if status:
            statuses = [status] if status in self.VALID_STATUSES else ["published"]
        rows = self._repo.list_posts(
            project_id=project_id,
            character_id=character_id,
            statuses=statuses,
            search=search,
            limit=limit,
            offset=offset,
        )
        visible = []
        for row in rows:
            project = self._project_service.get_project(row.project_id)
            can_manage = can_manage_project_func(user, project)
            can_edit = can_manage or row.created_by_user_id == user.id
            if row.status == "published" or can_edit:
                visible.append((row, can_edit))
        return [self.serialize_post(row, can_manage=can_manage) for row, can_manage in visible]

    def count_posts(self, *, project_id=None, character_id=None, search=None, status=None):
        statuses = None
        if status:
            statuses = [status] if status in self.VALID_STATUSES else ["published"]
        return self._repo.count_posts(project_id=project_id, character_id=character_id, statuses=statuses, search=search)

    def get_post(self, post_id: int):
        return self._repo.get_post(post_id)

    def create_post(self, *, project_id: int, user_id: int, payload: dict):
        theme = str(payload.get("theme") or "").strip()
        if not theme:
            raise ValueError("テーマを入力してください。")
        body = self._plain_text_article(payload.get("body") or "")
        if not body:
            raise ValueError("本文を入力してください。")
        character_id = int(payload.get("character_id") or 0)
        character = self._character_service.get_character(character_id)
        if not character or character.project_id != project_id:
            raise ValueError("キャラクターを選択してください。")
        status = str(payload.get("status") or "draft")
        if status not in self.VALID_STATUSES:
            status = "draft"
        return self._repo.create_post(
            {
                "project_id": project_id,
                "character_id": character_id,
                "created_by_user_id": user_id,
                "theme": theme[:255],
                "instruction": str(payload.get("instruction") or "").strip(),
                "body": body,
                "thumbnail_asset_id": payload.get("thumbnail_asset_id"),
                "status": status,
                "generation_state_json": json_util.dumps(payload.get("generation_state") or {}),
            }
        )

    def generate_post(self, *, project_id: int, user_id: int, payload: dict):
        theme = str(payload.get("theme") or "").strip()
        instruction = str(payload.get("instruction") or "").strip()
        character_id = int(payload.get("character_id") or 0)
        character = self._character_service.get_character(character_id)
        if not theme:
            raise ValueError("テーマを入力してください。")
        if not character or character.project_id != project_id:
            raise ValueError("キャラクターを選択してください。")
        prompt = self._build_blog_prompt(project_id, character, theme, instruction)
        result = self._text_ai_client.generate_text(
            prompt,
            model=payload.get("model") or payload.get("text_ai_model"),
            temperature=0.75,
            max_tokens=5000,
        )
        body = self._plain_text_article(result.get("text") or "")
        if not body:
            raise RuntimeError("blog generation response was empty")
        status = str(payload.get("status") or "draft")
        if status not in self.VALID_STATUSES:
            status = "draft"
        return self._repo.create_post(
            {
                "project_id": project_id,
                "character_id": character_id,
                "created_by_user_id": user_id,
                "theme": theme[:255],
                "instruction": instruction,
                "body": body,
                "status": status,
                "generation_state_json": json_util.dumps(
                    {
                        "source": "blog_generate",
                        "prompt": prompt,
                        "model": result.get("model"),
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            }
        )

    def update_post(self, post_id: int, payload: dict):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        normalized = {}
        if "theme" in payload:
            theme = str(payload.get("theme") or "").strip()
            if not theme:
                raise ValueError("テーマを入力してください。")
            normalized["theme"] = theme[:255]
        if "instruction" in payload:
            normalized["instruction"] = str(payload.get("instruction") or "").strip()
        if "body" in payload:
            body = self._plain_text_article(payload.get("body") or "")
            if not body:
                raise ValueError("本文を入力してください。")
            normalized["body"] = body
        if "character_id" in payload:
            character_id = int(payload.get("character_id") or 0)
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != post.project_id:
                raise ValueError("キャラクターを選択してください。")
            normalized["character_id"] = character_id
        if "thumbnail_asset_id" in payload:
            normalized["thumbnail_asset_id"] = payload.get("thumbnail_asset_id")
        if "status" in payload:
            status = str(payload.get("status") or "draft")
            normalized["status"] = status if status in self.VALID_STATUSES else "draft"
        return self._repo.update_post(post_id, normalized)

    def delete_post(self, post_id: int):
        return self._repo.delete_post(post_id)

    def generate_thumbnail(self, post_id: int, payload: dict | None = None):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        payload = dict(payload or {})
        character = self._character_service.get_character(post.character_id)
        project = self._project_service.get_project(post.project_id)
        world = self._world_service.get_world(post.project_id)
        prompt = self._build_thumbnail_prompt(post, character, project, world, payload)
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
        file_name, file_path, file_size = self._store_generated_thumbnail(post.project_id, post.id, image_base64)
        asset = self._asset_service.create_asset(
            post.project_id,
            {
                "asset_type": "blog_thumbnail",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "blog_thumbnail",
                        "blog_post_id": post.id,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_ids,
                        "model": result.get("model"),
                    }
                ),
            },
        )
        generation_state = self._load_json(post.generation_state_json)
        generation_state.update(
            {
                "thumbnail_prompt": prompt,
                "thumbnail_generated_at": datetime.utcnow().isoformat(),
                "thumbnail_reference_asset_ids": reference_ids,
            }
        )
        return self._repo.update_post(
            post.id,
            {
                "thumbnail_asset_id": asset.id,
                "generation_state_json": json_util.dumps(generation_state),
            },
        )

    def schedule_x_post(self, post_id: int, user_id: int, scheduled_for_value: str):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        scheduled_for = self._parse_schedule_datetime(scheduled_for_value)
        if scheduled_for <= datetime.now():
            raise ValueError("scheduled_for must be in the future")
        scheduled_for = scheduled_for.replace(minute=0, second=0, microsecond=0)
        existing = self._active_x_schedule_for_post(post_id)
        if existing:
            existing.status = "cancelled"
            existing.cancelled_at = datetime.now()
        schedule = BlogXSchedule(
            blog_post_id=post.id,
            project_id=post.project_id,
            created_by_user_id=user_id,
            scheduled_for=scheduled_for,
            status="scheduled",
            metadata_json=json_util.dumps({"source": "blog_calendar"}),
        )
        db.session.add(schedule)
        db.session.commit()
        return schedule

    def cancel_x_schedule(self, post_id: int, schedule_id: int | None = None):
        query = BlogXSchedule.query.filter(
            BlogXSchedule.blog_post_id == post_id,
            BlogXSchedule.status == "scheduled",
        )
        if schedule_id:
            query = query.filter(BlogXSchedule.id == schedule_id)
        schedule = query.order_by(BlogXSchedule.scheduled_for.asc(), BlogXSchedule.id.asc()).first()
        if not schedule:
            return None
        schedule.status = "cancelled"
        schedule.cancelled_at = datetime.now()
        db.session.commit()
        return schedule

    def publish_x_post_now(self, post_id: int, user_id: int):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        now = datetime.now()
        schedule = BlogXSchedule(
            blog_post_id=post.id,
            project_id=post.project_id,
            created_by_user_id=user_id,
            scheduled_for=now,
            status="posting",
            metadata_json=json_util.dumps({"source": "blog_manual_publish"}),
        )
        db.session.add(schedule)
        db.session.commit()
        self._publish_schedule(schedule, post)
        return schedule

    def list_x_schedules(self, *, project_id: int | None = None, start: str | None = None, end: str | None = None):
        start_dt = self._parse_schedule_datetime(start) if start else datetime.utcnow() - timedelta(days=1)
        end_dt = self._parse_schedule_datetime(end) if end else start_dt + timedelta(days=14)
        query = BlogXSchedule.query.filter(
            BlogXSchedule.scheduled_for >= start_dt,
            BlogXSchedule.scheduled_for < end_dt,
            BlogXSchedule.status == "scheduled",
        )
        if project_id:
            query = query.filter(BlogXSchedule.project_id == project_id)
        schedules = query.order_by(BlogXSchedule.scheduled_for.asc(), BlogXSchedule.id.asc()).all()
        return [self._serialize_x_schedule_item(schedule) for schedule in schedules]

    def publish_due_x_schedules(self, *, now: datetime | None = None, limit: int = 10):
        now = now or datetime.now()
        rows = (
            BlogXSchedule.query.filter(
                BlogXSchedule.status == "scheduled",
                BlogXSchedule.scheduled_for <= now,
            )
            .order_by(BlogXSchedule.scheduled_for.asc(), BlogXSchedule.id.asc())
            .limit(max(1, min(int(limit or 10), 50)))
            .all()
        )
        results = []
        for schedule in rows:
            post = self._repo.get_post(schedule.blog_post_id)
            if not post:
                schedule.status = "failed"
                schedule.error_message = "Blog post not found"
                db.session.commit()
                results.append(self._serialize_x_schedule(schedule))
                continue
            try:
                self._publish_schedule(schedule, post)
            except Exception:
                pass
            results.append(self._serialize_x_schedule(schedule))
        return results

    def _publish_schedule(self, schedule, post):
        thumbnail_asset = self._asset_service.get_asset(post.thumbnail_asset_id) if post.thumbnail_asset_id else None
        try:
            published = self._x_publishing_service.publish_feed_post(post, image_asset=thumbnail_asset)
            schedule.status = "posted"
            schedule.posted_at = datetime.now()
            schedule.x_post_id = published.get("x_post_id")
            schedule.metadata_json = json_util.dumps({**self._load_json(schedule.metadata_json), "published": published})
            schedule.error_message = None
        except Exception as exc:
            schedule.status = "failed"
            schedule.error_message = str(exc)
            db.session.commit()
            raise
        db.session.commit()

    def _serialize_x_schedule_item(self, schedule):
        post = self._repo.get_post(schedule.blog_post_id)
        thumbnail_asset = self._asset_service.get_asset(post.thumbnail_asset_id) if post and post.thumbnail_asset_id else None
        data = self._serialize_x_schedule(schedule)
        data["post"] = self.serialize_post(post, can_manage=True) if post else None
        data["thumbnail_url"] = self._media_url(thumbnail_asset.file_path) if thumbnail_asset else None
        return data

    def _parse_schedule_datetime(self, value):
        text = str(value or "").strip()
        if not text:
            raise ValueError("scheduled_for is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("scheduled_for must be ISO datetime") from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _build_blog_prompt(self, project_id: int, character, theme: str, instruction: str):
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        lines = [
            "あなたはキャラクター本人として、長めのブログ記事を書きます。",
            "この記事はあとでX投稿にも使われますが、短いポスト文や要約ではありません。ブログ本文として十分な長さで書いてください。",
            "出力は本文のみ。タイトル、見出し、箇条書き、Markdown、コードブロック、引用記号は使わないでください。",
            "ハッシュタグの羅列ではなく、自然な段落の文章にしてください。",
            "最低でも全角900文字以上、できれば全角1000文字から1500文字程度で書いてください。短くまとめないでください。",
            "一段落だけで終わらせず、4から7段落に分けてください。各段落は2から4文程度にしてください。",
            "句点「。」ごとに改行してください。段落と段落の間には必ず空行を1行入れてください。ただし段落見出しは付けないでください。",
            "指定キャラクターの口調、価値観、距離感を優先してください。",
            f"テーマ: {theme}",
            f"ユーザー指示: {instruction or '指定なし'}",
        ]
        if project:
            lines.append(f"ワールド名: {project.title}")
            if project.summary:
                lines.append(f"ワールド概要: {project.summary}")
        if world:
            if world.overview:
                lines.append(f"世界観: {world.overview}")
            if world.tone:
                lines.append(f"トーン: {world.tone}")
        lines.extend(
            [
                f"キャラクター名: {character.name}",
                f"ニックネーム: {character.nickname or ''}",
                f"性格: {character.personality or ''}",
                f"口調: {character.speech_style or ''}",
                f"キャラクター概要: {getattr(character, 'character_summary', '') or ''}",
            ]
        )
        return "\n".join(lines)

    def _build_thumbnail_prompt(self, post, character, project, world, payload: dict):
        override = str(payload.get("prompt") or "").strip()
        if override:
            return override
        lines = [
            "Create an eye-catching thumbnail image for a character blog post that will be shared on X.",
            "Include a short, readable Japanese headline/title text in the image, using the article theme as the main title.",
            "The headline should be large, high-contrast, and placed like a blog thumbnail title. Keep it short enough to read at small size.",
            "Do not add long body text, captions, speech bubbles, UI overlay, logo, or watermark.",
            "Use the reference image as the primary identity and art style guide for the character.",
            "The image should summarize the article's emotion and situation in one visual moment.",
            "Make it suitable for a 16:9 social thumbnail: clear focal point, expressive character, readable composition at small size.",
            f"Article theme: {post.theme}",
            f"Thumbnail headline text: {post.theme}",
            f"Article body: {post.body}",
        ]
        if project:
            lines.append(f"World: {project.title}. {project.summary or ''}")
        if world:
            lines.append(f"World setting: {world.overview or ''} {world.tone or ''}")
        if character:
            lines.append(f"Character: {character.name}")
            if character.appearance_summary:
                lines.append(f"Appearance: {character.appearance_summary}")
            if character.personality:
                lines.append(f"Personality: {character.personality}")
            if getattr(character, "art_style", None):
                lines.append(f"Art style: {character.art_style}")
            if character.ng_rules:
                lines.append(f"Never violate: {character.ng_rules}")
        return "\n".join(lines)

    def _plain_text_article(self, value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        lines = []
        for line in text.splitlines():
            cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
            cleaned = re.sub(r"^\s*>\s*", "", cleaned)
            cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned)
            cleaned = re.sub(r"^\s*\d+[.)]\s+", "", cleaned)
            cleaned = re.sub(r"[*_~]{1,3}", "", cleaned)
            lines.append(cleaned.strip())
        paragraphs = []
        for line in lines:
            if not line:
                continue
            sentence_lines = re.sub(r"。(?!\n)", "。\n", line)
            sentences = [sentence.strip() for sentence in sentence_lines.splitlines() if sentence.strip()]
            if sentences:
                paragraphs.append("\n".join(sentences))
        return "\n\n".join(paragraphs).strip()

    def _store_generated_thumbnail(self, project_id: int, post_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "generated", "blog", str(post_id))
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_name = f"blog_{post_id}_{timestamp}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)
