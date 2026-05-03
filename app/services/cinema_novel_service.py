from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import (
    Asset,
    Character,
    CharacterMemoryNote,
    CinemaNovel,
    CinemaNovelChapter,
    CinemaNovelCharacterImpression,
    CinemaNovelLoreEntry,
    CinemaNovelProgress,
    CinemaNovelReview,
    FeedPost,
    Project,
    World,
)
from ..utils import json_util
from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from .asset_service import AssetService
from .user_setting_service import UserSettingService


class CinemaNovelService:
    VALID_STATUSES = {"draft", "building", "published", "archived"}

    def list_novels(self, project_id: int, *, include_unpublished: bool = False):
        query = CinemaNovel.query.filter(
            CinemaNovel.project_id == project_id,
            CinemaNovel.deleted_at.is_(None),
        )
        if not include_unpublished:
            query = query.filter(CinemaNovel.status == "published")
        return query.order_by(CinemaNovel.sort_order.asc(), CinemaNovel.updated_at.desc(), CinemaNovel.id.desc()).all()

    def get_novel(self, novel_id: int):
        return CinemaNovel.query.filter(CinemaNovel.id == novel_id, CinemaNovel.deleted_at.is_(None)).first()

    def delete_novel(self, novel_id: int) -> bool:
        novel = self.get_novel(novel_id)
        if not novel:
            return False
        now = datetime.utcnow()
        novel.deleted_at = now
        novel.status = "archived"
        for chapter in CinemaNovelChapter.query.filter(CinemaNovelChapter.novel_id == novel.id).all():
            chapter.deleted_at = now
            db.session.add(chapter)
        for entry in CinemaNovelLoreEntry.query.filter(CinemaNovelLoreEntry.novel_id == novel.id).all():
            entry.deleted_at = now
            db.session.add(entry)
        reviews = CinemaNovelReview.query.filter(CinemaNovelReview.novel_id == novel.id).all()
        feed_post_ids = []
        memory_note_ids = []
        for review in reviews:
            review.deleted_at = now
            if review.feed_post_id:
                feed_post_ids.append(review.feed_post_id)
            if review.memory_note_id:
                memory_note_ids.append(review.memory_note_id)
            db.session.add(review)
        for impression in CinemaNovelCharacterImpression.query.filter(CinemaNovelCharacterImpression.novel_id == novel.id).all():
            impression.deleted_at = now
            if impression.memory_note_id:
                memory_note_ids.append(impression.memory_note_id)
            db.session.add(impression)
        if feed_post_ids:
            for post in FeedPost.query.filter(FeedPost.id.in_(feed_post_ids)).all():
                post.deleted_at = now
                post.status = "archived"
                db.session.add(post)
        source_refs = [f"cinema_novel:{novel.id}", f"cinema_novel:{novel.id}:impressions"]
        note_query = CharacterMemoryNote.query.filter(
            (CharacterMemoryNote.source_ref.in_(source_refs))
            | (CharacterMemoryNote.id.in_(memory_note_ids or [-1]))
        )
        for note in note_query.all():
            note.enabled = False
            db.session.add(note)
        CinemaNovelProgress.query.filter(CinemaNovelProgress.novel_id == novel.id).delete(synchronize_session=False)
        db.session.add(novel)
        db.session.commit()
        return True

    def list_chapters(self, novel_id: int):
        return CinemaNovelChapter.query.filter(
            CinemaNovelChapter.novel_id == novel_id,
            CinemaNovelChapter.deleted_at.is_(None),
        ).order_by(CinemaNovelChapter.chapter_no.asc(), CinemaNovelChapter.sort_order.asc(), CinemaNovelChapter.id.asc()).all()

    def get_chapter(self, chapter_id: int):
        return CinemaNovelChapter.query.filter(
            CinemaNovelChapter.id == chapter_id,
            CinemaNovelChapter.deleted_at.is_(None),
        ).first()

    def serialize_novel(self, novel, *, include_chapters: bool = False, user_id: int | None = None):
        if not novel:
            return None
        payload = {
            "id": novel.id,
            "project_id": novel.project_id,
            "created_by_user_id": novel.created_by_user_id,
            "title": novel.title,
            "subtitle": novel.subtitle,
            "description": novel.description,
            "status": novel.status,
            "mode": novel.mode,
            "cover_asset_id": novel.cover_asset_id,
            "poster_asset_id": novel.poster_asset_id,
            "cover_asset": self._serialize_asset(novel.cover_asset_id),
            "poster_asset": self._serialize_asset(novel.poster_asset_id),
            "source_path": novel.source_path,
            "production_json": self._load_json(novel.production_json),
            "sort_order": novel.sort_order,
            "created_at": novel.created_at.isoformat() if novel.created_at else None,
            "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
        }
        chapters = self.list_chapters(novel.id)
        payload["chapter_count"] = len(chapters)
        if include_chapters:
            payload["chapters"] = [self.serialize_chapter(chapter) for chapter in chapters]
        if user_id:
            payload["progress"] = self.serialize_progress(self.get_progress(user_id, novel.id))
            payload["reviews"] = [self.serialize_review(review) for review in self.list_reviews(novel.id, user_id=user_id)]
        else:
            payload["reviews"] = [self.serialize_review(review) for review in self.list_reviews(novel.id)]
        payload["lore_entries"] = [self.serialize_lore_entry(entry) for entry in self.list_lore_entries(novel.id)]
        return payload

    def list_reviews(self, novel_id: int, *, user_id: int | None = None):
        query = CinemaNovelReview.query.filter(
            CinemaNovelReview.novel_id == novel_id,
            CinemaNovelReview.deleted_at.is_(None),
        )
        if user_id:
            query = query.filter(CinemaNovelReview.user_id == user_id)
        return query.order_by(CinemaNovelReview.updated_at.desc(), CinemaNovelReview.id.desc()).all()

    def serialize_review(self, review) -> dict | None:
        if not review:
            return None
        character = Character.query.get(review.character_id)
        thumbnail_id = getattr(character, "thumbnail_asset_id", None) or getattr(character, "base_asset_id", None)
        return {
            "id": review.id,
            "novel_id": review.novel_id,
            "character_id": review.character_id,
            "user_id": review.user_id,
            "feed_post_id": review.feed_post_id,
            "memory_note_id": review.memory_note_id,
            "review_text": review.review_text,
            "memory_note": review.memory_note,
            "rating_label": review.rating_label,
            "status": review.status,
            "metadata": self._load_json(review.metadata_json, default={}),
            "impressions": [
                self.serialize_character_impression(impression)
                for impression in self.list_character_impressions(
                    review.novel_id,
                    reviewer_character_id=review.character_id,
                    user_id=review.user_id,
                )
            ],
            "character": {
                "id": character.id,
                "name": character.name,
                "nickname": character.nickname,
                "thumbnail_asset": self._serialize_asset(thumbnail_id),
            } if character else None,
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }

    def create_character_review(self, novel_id: int, user_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        novel = self.get_novel(novel_id)
        if not novel:
            return None
        try:
            character_id = int(payload.get("character_id") or 0)
        except (TypeError, ValueError):
            raise ValueError("character_id is required")
        character = Character.query.filter(
            Character.id == character_id,
            Character.project_id == novel.project_id,
            Character.deleted_at.is_(None),
        ).first()
        if not character:
            raise ValueError("character was not found")
        existing = CinemaNovelReview.query.filter(
            CinemaNovelReview.novel_id == novel.id,
            CinemaNovelReview.character_id == character.id,
            CinemaNovelReview.user_id == user_id,
            CinemaNovelReview.deleted_at.is_(None),
        ).first()
        lore_entries = self.ensure_novel_lore(novel.id)
        result = self._generate_character_review(novel, character)
        review_text = str(result.get("feed_review") or "").strip()
        memory_note_text = str(result.get("memory_note") or "").strip()
        rating_label = str(result.get("rating_label") or "").strip()[:80] or None
        if not review_text:
            raise RuntimeError("review response did not include review text")
        if not memory_note_text:
            memory_note_text = self._fallback_review_memory_note(novel, character, review_text)
        feed_post = self._upsert_review_feed_post(
            novel=novel,
            character=character,
            user_id=user_id,
            review_text=review_text,
            existing_feed_post_id=existing.feed_post_id if existing else None,
        )
        memory_note = self._upsert_review_memory_note(
            novel=novel,
            character=character,
            user_id=user_id,
            note_text=memory_note_text,
            existing_memory_note_id=existing.memory_note_id if existing else None,
        )
        impressions = self._generate_and_upsert_character_impressions(
            novel=novel,
            character=character,
            user_id=user_id,
            lore_entries=lore_entries,
        )
        impression_memory = self._upsert_impression_memory_note(
            novel=novel,
            character=character,
            user_id=user_id,
            impressions=impressions,
        )
        if impression_memory:
            for impression in impressions:
                impression.memory_note_id = impression_memory.id
            db.session.commit()
        metadata = {
            "source": "cinema_novel_review",
            "model": result.get("model"),
            "usage": result.get("usage"),
            "review_summary": result.get("review_summary"),
            "lore_entry_count": len(lore_entries or []),
            "impression_count": len(impressions or []),
        }
        if existing:
            existing.feed_post_id = feed_post.id if feed_post else None
            existing.memory_note_id = memory_note.id if memory_note else None
            existing.review_text = review_text
            existing.memory_note = memory_note_text
            existing.rating_label = rating_label
            existing.status = "published"
            existing.metadata_json = json_util.dumps(metadata)
            db.session.commit()
            return existing
        review = CinemaNovelReview(
            novel_id=novel.id,
            character_id=character.id,
            user_id=user_id,
            feed_post_id=feed_post.id if feed_post else None,
            memory_note_id=memory_note.id if memory_note else None,
            review_text=review_text,
            memory_note=memory_note_text,
            rating_label=rating_label,
            status="published",
            metadata_json=json_util.dumps(metadata),
        )
        db.session.add(review)
        db.session.commit()
        return review

    def list_lore_entries(self, novel_id: int):
        return CinemaNovelLoreEntry.query.filter(
            CinemaNovelLoreEntry.novel_id == novel_id,
            CinemaNovelLoreEntry.deleted_at.is_(None),
        ).order_by(CinemaNovelLoreEntry.sort_order.asc(), CinemaNovelLoreEntry.id.asc()).all()

    def serialize_lore_entry(self, entry) -> dict | None:
        if not entry:
            return None
        return {
            "id": entry.id,
            "novel_id": entry.novel_id,
            "lore_type": entry.lore_type,
            "name": entry.name,
            "summary": entry.summary,
            "role_note": entry.role_note,
            "source_note": entry.source_note,
            "sort_order": entry.sort_order,
            "metadata": self._load_json(entry.metadata_json, default={}),
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }

    def list_character_impressions(
        self,
        novel_id: int,
        *,
        reviewer_character_id: int | None = None,
        user_id: int | None = None,
    ):
        query = CinemaNovelCharacterImpression.query.filter(
            CinemaNovelCharacterImpression.novel_id == novel_id,
            CinemaNovelCharacterImpression.deleted_at.is_(None),
        )
        if reviewer_character_id:
            query = query.filter(CinemaNovelCharacterImpression.reviewer_character_id == reviewer_character_id)
        if user_id:
            query = query.filter(CinemaNovelCharacterImpression.user_id == user_id)
        return query.order_by(CinemaNovelCharacterImpression.id.asc()).all()

    def serialize_character_impression(self, impression) -> dict | None:
        if not impression:
            return None
        target = Character.query.get(impression.target_character_id) if impression.target_character_id else None
        return {
            "id": impression.id,
            "novel_id": impression.novel_id,
            "reviewer_character_id": impression.reviewer_character_id,
            "user_id": impression.user_id,
            "target_name": impression.target_name,
            "target_character_id": impression.target_character_id,
            "target_character": {
                "id": target.id,
                "name": target.name,
                "nickname": target.nickname,
            } if target else None,
            "impression_text": impression.impression_text,
            "talk_hint": impression.talk_hint,
            "memory_note_id": impression.memory_note_id,
            "metadata": self._load_json(impression.metadata_json, default={}),
            "created_at": impression.created_at.isoformat() if impression.created_at else None,
            "updated_at": impression.updated_at.isoformat() if impression.updated_at else None,
        }

    def ensure_novel_lore(self, novel_id: int, *, force: bool = False):
        novel = self.get_novel(novel_id)
        if not novel:
            return []
        existing = self.list_lore_entries(novel.id)
        if existing and not force:
            return existing
        result = self._generate_novel_lore(novel)
        entries = result.get("entries") if isinstance(result, dict) else []
        if not isinstance(entries, list):
            entries = []
        saved = []
        for index, item in enumerate(entries[:40], start=1):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()[:255]
            summary = str(item.get("summary") or "").strip()
            if not name or not summary:
                continue
            lore_type = str(item.get("lore_type") or "other").strip().lower()[:50] or "other"
            entry = CinemaNovelLoreEntry.query.filter(
                CinemaNovelLoreEntry.novel_id == novel.id,
                CinemaNovelLoreEntry.lore_type == lore_type,
                CinemaNovelLoreEntry.name == name,
            ).first()
            if not entry:
                entry = CinemaNovelLoreEntry(novel_id=novel.id, lore_type=lore_type, name=name)
            entry.summary = summary[:1600]
            entry.role_note = str(item.get("role_note") or "").strip()[:1200] or None
            entry.source_note = str(item.get("source_note") or "").strip()[:1200] or None
            entry.sort_order = index
            entry.metadata_json = json_util.dumps(
                {
                    "source": "cinema_novel_lore_generation",
                    "model": result.get("model"),
                    "usage": result.get("usage"),
                }
            )
            entry.deleted_at = None
            db.session.add(entry)
            saved.append(entry)
        db.session.commit()
        return self.list_lore_entries(novel.id)

    def serialize_chapter(self, chapter):
        if not chapter:
            return None
        scenes = self._load_json(chapter.scene_json, default=[])
        if isinstance(scenes, list):
            scenes = [self._serialize_scene(scene) for scene in scenes]
        return {
            "id": chapter.id,
            "novel_id": chapter.novel_id,
            "chapter_no": chapter.chapter_no,
            "title": chapter.title,
            "body_markdown": chapter.body_markdown,
            "scene_json": scenes,
            "cover_asset_id": chapter.cover_asset_id,
            "cover_asset": self._serialize_asset(chapter.cover_asset_id),
            "generated_assets": self._chapter_generated_assets(chapter),
            "sort_order": chapter.sort_order,
            "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
            "updated_at": chapter.updated_at.isoformat() if chapter.updated_at else None,
        }

    def _serialize_scene(self, scene):
        if not isinstance(scene, dict):
            return scene
        payload = dict(scene)
        payload["background_asset"] = self._serialize_asset(payload.get("background_asset_id"))
        payload["still_asset"] = self._serialize_asset(payload.get("still_asset_id"))
        return payload

    def _chapter_generated_assets(self, chapter):
        novel = self.get_novel(chapter.novel_id)
        if not novel:
            return []
        assets = Asset.query.filter(
            Asset.project_id == novel.project_id,
            Asset.deleted_at.is_(None),
            Asset.asset_type.in_(["cinema_novel_chapter_cover", "cinema_novel_scene_still"]),
        ).order_by(Asset.created_at.asc(), Asset.id.asc()).all()
        payload = []
        seen_asset_ids = set()
        for asset in assets:
            metadata = self._load_json(asset.metadata_json, default={})
            if not isinstance(metadata, dict) or int(metadata.get("chapter_id") or 0) != int(chapter.id):
                continue
            serialized = self._serialize_asset(asset.id)
            if not serialized or asset.id in seen_asset_ids:
                continue
            seen_asset_ids.add(asset.id)
            source = metadata.get("source") or asset.asset_type
            scene_index = metadata.get("scene_index")
            if source == "cinema_novel_chapter_cover":
                label = "章扉"
            elif isinstance(scene_index, int):
                label = f"scene {scene_index + 1}"
            else:
                label = "劇中スチル"
            serialized["label"] = label
            serialized["source"] = source
            serialized["scene_index"] = scene_index
            payload.append(serialized)
        return payload

    def get_progress(self, user_id: int, novel_id: int):
        return CinemaNovelProgress.query.filter_by(user_id=user_id, novel_id=novel_id).first()

    def serialize_progress(self, progress):
        if not progress:
            return None
        return {
            "id": progress.id,
            "user_id": progress.user_id,
            "novel_id": progress.novel_id,
            "chapter_id": progress.chapter_id,
            "scene_index": progress.scene_index,
            "page_index": progress.page_index,
            "updated_at": progress.updated_at.isoformat() if progress.updated_at else None,
        }

    def save_progress(self, user_id: int, novel_id: int, payload: dict | None):
        payload = dict(payload or {})
        novel = self.get_novel(novel_id)
        if not novel:
            return None
        try:
            chapter_id = int(payload.get("chapter_id") or 0)
            scene_index = max(0, int(payload.get("scene_index") or 0))
            page_index = max(0, int(payload.get("page_index") or 0))
        except (TypeError, ValueError):
            raise ValueError("invalid progress")
        chapter = self.get_chapter(chapter_id)
        if not chapter or chapter.novel_id != novel.id:
            raise ValueError("invalid chapter")
        scenes = self._load_json(chapter.scene_json, default=[])
        if scenes:
            scene_index = min(scene_index, len(scenes) - 1)
        progress = self.get_progress(user_id, novel.id)
        if not progress:
            progress = CinemaNovelProgress(user_id=user_id, novel_id=novel.id, chapter_id=chapter.id)
            db.session.add(progress)
        progress.chapter_id = chapter.id
        progress.scene_index = scene_index
        progress.page_index = page_index
        db.session.commit()
        return progress

    def import_markdown_folder(self, project_id: int, user_id: int, payload: dict | None):
        payload = dict(payload or {})
        source_path = str(payload.get("source_path") or "").strip()
        if not source_path:
            raise ValueError("source_path is required")
        folder = self._resolve_book_folder(source_path)
        chapter_files = self._chapter_files(folder)
        if not chapter_files:
            raise ValueError("chapter markdown files were not found")
        title = str(payload.get("title") or folder.name).strip() or folder.name
        existing = CinemaNovel.query.filter(
            CinemaNovel.project_id == project_id,
            CinemaNovel.title == title,
            CinemaNovel.source_path == str(folder),
            CinemaNovel.deleted_at.is_(None),
        ).first()
        if existing:
            return existing
        novel = CinemaNovel(
            project_id=project_id,
            created_by_user_id=user_id,
            title=title,
            subtitle=str(payload.get("subtitle") or "ノベル作品").strip() or None,
            description=str(payload.get("description") or "").strip() or None,
            status=str(payload.get("status") or "published").strip() or "published",
            mode="cinema_novel",
            source_path=str(folder),
            production_json=json_util.dumps(
                {
                    "source": "markdown_folder",
                    "reader": "prebuilt",
                    "generation_mode": "build_then_publish",
                    "image_generation": "prebuilt_only",
                }
            ),
        )
        if novel.status not in self.VALID_STATUSES:
            novel.status = "draft"
        db.session.add(novel)
        db.session.flush()
        for index, path in enumerate(chapter_files, start=1):
            body = path.read_text(encoding="utf-8").strip()
            chapter_no, chapter_title = self._extract_chapter_heading(path, body, index)
            db.session.add(
                CinemaNovelChapter(
                    novel_id=novel.id,
                    chapter_no=chapter_no,
                    title=chapter_title,
                    body_markdown=body,
                    scene_json=json_util.dumps(self._markdown_to_scenes(body, chapter_no=chapter_no)),
                    sort_order=index,
                )
            )
        db.session.commit()
        return novel

    def generate_production_outline(self, project_id: int, payload: dict | None):
        payload = dict(payload or {})
        settings = self._user_setting_service.apply_cinema_novel_text_generation_settings(payload.get("text_options") or {})
        title = str(payload.get("title") or "無題のノベル作品").strip()
        main_character = str(payload.get("main_character") or "").strip()
        theme = str(payload.get("theme") or "").strip()
        genre = str(payload.get("genre") or "映画ノベル").strip()
        chapter_count = int(payload.get("chapter_count") or 5)
        chapter_count = max(3, min(12, chapter_count))
        chapter_target_chars = int(payload.get("chapter_target_chars") or settings.get("chapter_target_chars") or 3500)
        registered_character_context = self._registered_character_context(project_id, main_character=main_character)
        prompt = "\n".join(
            [
                "日本語で、ノベル再生用の事前生成ノベルゲーム作品の制作設計書を作成してください。",
                "これはリアルタイム生成ではなく、章立て、各章本文、各章画像を制作モードで事前生成してから公開する作品です。",
                "読者は鑑賞モードで待ち時間なく読み進めます。",
                "章数は短く濃くしてください。標準は5章で、導入、展開、転機、クライマックス、余韻の読み切り構成を優先してください。",
                "各章は長文説明よりも、短い本文と多めの画像でテンポよく読ませる前提にしてください。",
                "登場人物は、主人公を除き、可能な限り下記のDB登録済みキャラクターだけを使ってください。",
                "主人公は指定名を優先してよく、DB未登録でも構いません。ただし脇役、敵役、組織代表、関係者は登録済みキャラクターから選んでください。",
                "知らない新キャラクターを安易に増やさないでください。新キャラクターが必要な場合は、なぜ既存キャラクターで代替できないかを明記してください。",
                "",
                f"タイトル: {title}",
                f"ジャンル: {genre}",
                f"主役: {main_character or '未指定'}",
                f"テーマ: {theme or '未指定'}",
                f"章数: {chapter_count}",
                f"各章の目標文字数: {chapter_target_chars}",
                "",
                "DB登録済みキャラクター:",
                registered_character_context or "登録済みキャラクターなし",
                "",
                "必ず以下の構成で出力してください。",
                "1. ログライン",
                "2. 作品コンセプト",
                "3. 主要キャラクターの演出メモ",
                "4. 全体構成",
                "5. 章立て一覧。各章に、章タイトル、目的、主要シーン、劇中スチル案を含める",
                "6. 深掘り生成方針。各章をどう膨らませるか",
                "7. ノベルゲーム化方針。シーン分割、話者名、栞、画像プリロードの前提",
                "説明だけでなく、このまま制作ジョブに渡せる具体度にしてください。",
            ]
        )
        result = self._text_ai_client.generate_text(
            prompt,
            model=settings.get("model"),
            temperature=0.75,
            max_tokens=32000,
        )
        return {
            "model": result.get("model"),
            "chapter_target_chars": chapter_target_chars,
            "outline_markdown": result.get("text") or "",
            "usage": result.get("usage"),
        }

    def generate_production_premise(self, project_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        settings = self._user_setting_service.apply_cinema_novel_text_generation_settings(payload.get("text_options") or {})
        project = Project.query.get(project_id)
        world = World.query.filter_by(project_id=project_id).first()
        current_input = payload.get("current_input") or {}
        requested_main_character = str(current_input.get("main_character") or "").strip()
        requested_genre = str(current_input.get("genre") or "").strip()
        character_context = self._registered_character_context(project_id, main_character=requested_main_character)
        prompt = "\n".join(
            [
                "Return only JSON.",
                "ノベル用の長編企画を、日本語で1案だけ提案してください。",
                "ユーザーが手入力しなくても章立て制作設計へ進めるための、入力欄の初期案を作ります。",
                "DB登録済みキャラクターを可能な限り使ってください。主人公も登録済みキャラから選ぶのを優先します。",
                "ただし、物語上どうしても必要なら主人公だけは新規名でも構いません。その場合も理由を protagonist_reason に書いてください。",
                "知らない脇役や敵役を増やさず、既存キャラの関係性・思想・口調・弱点を活かしてください。",
                "Required JSON keys: title, main_character, protagonist_reason, genre, chapter_count, theme, concept_note.",
                "chapter_count は 5 を基本にし、必要な場合だけ 3, 4, 6, 8 のいずれかにしてください。",
                "ユーザー指定ジャンルがある場合は必ず反映してください。",
                "ユーザー指定主役がある場合は必ずそのキャラクターを主人公にしてください。",
                "",
                "User current input:",
                f"title: {str(current_input.get('title') or '').strip()}",
                f"main_character: {requested_main_character or 'AI選定'}",
                f"genre: {requested_genre or 'AI提案'}",
                f"chapter_count: {str(current_input.get('chapter_count') or '5').strip()}",
                f"theme: {str(current_input.get('theme') or '').strip()}",
                "",
                "Project:",
                f"title: {getattr(project, 'title', '') or ''}",
                f"summary: {getattr(project, 'summary', '') or ''}",
                "",
                "World setting:",
                f"name: {getattr(world, 'name', '') or ''}",
                f"tone: {getattr(world, 'tone', '') or ''}",
                f"era: {getattr(world, 'era_description', '') or ''}",
                f"overview: {getattr(world, 'overview', '') or ''}",
                f"technology: {getattr(world, 'technology_level', '') or ''}",
                f"social_structure: {getattr(world, 'social_structure', '') or ''}",
                f"rules: {getattr(world, 'rules_json', '') or ''}",
                f"forbidden: {getattr(world, 'forbidden_json', '') or ''}",
                "",
                "DB registered characters:",
                character_context or "登録済みキャラクターなし",
            ]
        )
        result = self._text_ai_client.generate_text(
            prompt,
            model=settings.get("model"),
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=6000,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("production premise response is invalid")
        chapter_count = parsed.get("chapter_count")
        try:
            chapter_count = int(chapter_count)
        except (TypeError, ValueError):
            chapter_count = 5
        if chapter_count not in {3, 4, 5, 6, 8}:
            chapter_count = 5
        return {
            "title": str(parsed.get("title") or "").strip(),
            "main_character": str(parsed.get("main_character") or "").strip(),
            "protagonist_reason": str(parsed.get("protagonist_reason") or "").strip(),
            "genre": str(parsed.get("genre") or "映画ノベル").strip() or "映画ノベル",
            "chapter_count": chapter_count,
            "theme": str(parsed.get("theme") or "").strip(),
            "concept_note": str(parsed.get("concept_note") or "").strip(),
            "model": result.get("model"),
            "usage": result.get("usage"),
        }

    def _registered_character_context(self, project_id: int, *, main_character: str = "") -> str:
        characters = Character.query.filter(
            Character.project_id == project_id,
            Character.deleted_at.is_(None),
        ).order_by(Character.id.asc()).all()
        if not characters:
            return ""
        main_name = str(main_character or "").strip().lower()
        lines = []
        for character in characters[:60]:
            role_note = "主人公候補または主要人物"
            if main_name and main_name in {str(character.name or "").strip().lower(), str(character.nickname or "").strip().lower()}:
                role_note = "指定主人公と同一または近い登録キャラクター"
            lines.extend(
                [
                    f"- id={character.id} name={character.name or ''} nickname={character.nickname or ''} role_note={role_note}",
                    f"  overview={self._shorten_for_prompt(getattr(character, 'character_summary', None), 900)}",
                    f"  personality={self._shorten_for_prompt(character.personality, 500)}",
                    f"  first_person={character.first_person or ''}",
                    f"  second_person={character.second_person or ''}",
                    f"  speech_style={self._shorten_for_prompt(character.speech_style, 350)}",
                    f"  speech_sample={self._shorten_for_prompt(character.speech_sample, 500)}",
                    f"  appearance={self._shorten_for_prompt(character.appearance_summary, 350)}",
                    f"  ng_rules={self._shorten_for_prompt(character.ng_rules, 250)}",
                ]
            )
        return "\n".join(lines)

    def _generate_character_review(self, novel, character) -> dict:
        settings = self._user_setting_service.apply_cinema_novel_text_generation_settings({})
        novel_context = self._novel_review_context(novel)
        lore_context = self._lore_prompt_context(self.list_lore_entries(novel.id))
        character_context = "\n".join(
            [
                f"name: {character.name or ''}",
                f"nickname: {character.nickname or ''}",
                f"first_person: {character.first_person or ''}",
                f"second_person: {character.second_person or ''}",
                f"summary: {self._shorten_for_prompt(getattr(character, 'character_summary', None), 1000)}",
                f"personality: {self._shorten_for_prompt(character.personality, 900)}",
                f"speech_style: {self._shorten_for_prompt(character.speech_style, 700)}",
                f"speech_sample: {self._shorten_for_prompt(character.speech_sample, 700)}",
                f"ng_rules: {self._shorten_for_prompt(character.ng_rules, 400)}",
            ]
        )
        prompt = "\n".join(
            [
                "Return only JSON.",
                "A registered character has read/watched the following visual novel as an in-world cinema work.",
                "Create a public Feed review and a private memory note for future chat.",
                "Japanese only.",
                "Required keys: feed_review, memory_note, rating_label, review_summary.",
                "feed_review: 80-220 Japanese characters. Write as the character posting to Feed, in their voice. Mention one specific memorable element from the novel.",
                "memory_note: 120-360 Japanese characters. Third-person memory for AI prompt. It must say this character has read/watched the work, what they remember, and how they tend to talk about it.",
                "rating_label: short Japanese label such as 爆笑, 傑作, 怪作, 刺さった, 困惑.",
                "Do not change the character's permanent personality. This is a viewing experience memory.",
                "Do not invent facts that contradict the novel context.",
                "",
                "Character:",
                character_context,
                "",
                "Novel context:",
                novel_context,
                "",
                "Known novel lore:",
                lore_context or "(none yet)",
            ]
        )
        result = self._text_ai_client.generate_text(
            prompt,
            model=settings.get("model"),
            response_format={"type": "json_object"},
            temperature=0.8,
            max_tokens=2000,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed["model"] = result.get("model")
        parsed["usage"] = result.get("usage")
        return parsed

    def _generate_novel_lore(self, novel) -> dict:
        settings = self._user_setting_service.apply_cinema_novel_text_generation_settings({})
        prompt = "\n".join(
            [
                "Return only JSON.",
                "Extract reusable in-world knowledge from this visual novel for future character chats.",
                "Japanese only.",
                "Required shape: {\"entries\":[{\"lore_type\":\"character|term|event|location|scene|theme|other\",\"name\":\"...\",\"summary\":\"...\",\"role_note\":\"...\",\"source_note\":\"...\"}]}",
                "Focus on characters, named concepts, important incidents, iconic scenes, relationships, jokes, and emotional hooks.",
                "Character entries must explain how the character appears in this novel, what they want, what makes them funny or memorable, and how they relate to other entries.",
                "Term/event entries must be understandable later without rereading the novel.",
                "Do not invent facts that are not supported by the novel context.",
                "Create 8-24 compact entries.",
                "",
                "Novel context:",
                self._novel_review_context(novel),
            ]
        )
        result = self._text_ai_client.generate_text(
            prompt,
            model=settings.get("model"),
            response_format={"type": "json_object"},
            temperature=0.35,
            max_tokens=5000,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed["model"] = result.get("model")
        parsed["usage"] = result.get("usage")
        return parsed

    def _generate_character_impressions(self, novel, character, lore_entries: list) -> dict:
        settings = self._user_setting_service.apply_cinema_novel_text_generation_settings({})
        character_context = "\n".join(
            [
                f"name: {character.name or ''}",
                f"nickname: {character.nickname or ''}",
                f"first_person: {character.first_person or ''}",
                f"summary: {self._shorten_for_prompt(getattr(character, 'character_summary', None), 1000)}",
                f"personality: {self._shorten_for_prompt(character.personality, 900)}",
                f"speech_style: {self._shorten_for_prompt(character.speech_style, 700)}",
                f"speech_sample: {self._shorten_for_prompt(character.speech_sample, 700)}",
            ]
        )
        prompt = "\n".join(
            [
                "Return only JSON.",
                "A registered character has watched this visual novel. Create that character's private impressions of the novel's characters, terms, and iconic scenes.",
                "Japanese only.",
                "Required shape: {\"impressions\":[{\"target_name\":\"...\",\"impression_text\":\"...\",\"talk_hint\":\"...\"}]}",
                "target_name must match an entry name from Known novel lore when possible.",
                "impression_text: 80-260 Japanese characters. Write in third person. Explain how the reviewing character interprets or reacts to that target.",
                "talk_hint: 40-160 Japanese characters. How this reviewing character should bring it up in future chats.",
                "Prefer 4-10 memorable targets. Include important registered characters and the funniest or most emotionally useful concepts.",
                "Do not change the reviewing character's permanent personality. This is a viewing experience memory.",
                "",
                "Reviewing character:",
                character_context,
                "",
                "Novel:",
                f"title: {novel.title or ''}",
                f"description: {novel.description or ''}",
                "",
                "Known novel lore:",
                self._lore_prompt_context(lore_entries) or "(none)",
            ]
        )
        result = self._text_ai_client.generate_text(
            prompt,
            model=settings.get("model"),
            response_format={"type": "json_object"},
            temperature=0.55,
            max_tokens=4000,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed["model"] = result.get("model")
        parsed["usage"] = result.get("usage")
        return parsed

    def _lore_prompt_context(self, entries: list) -> str:
        lines = []
        for entry in entries or []:
            if isinstance(entry, dict):
                lore_type = entry.get("lore_type") or "other"
                name = entry.get("name") or ""
                summary = entry.get("summary") or ""
                role_note = entry.get("role_note") or ""
            else:
                lore_type = entry.lore_type
                name = entry.name
                summary = entry.summary
                role_note = entry.role_note
            if not name or not summary:
                continue
            lines.append(f"- [{lore_type}] {name}: {self._shorten_for_prompt(summary, 600)}")
            if role_note:
                lines.append(f"  role_note={self._shorten_for_prompt(role_note, 300)}")
        return "\n".join(lines)[:9000]

    def _resolve_lore_target_character_id(self, project_id: int, target_name: str) -> int | None:
        normalized = str(target_name or "").strip().lower()
        if not normalized:
            return None
        characters = Character.query.filter(
            Character.project_id == project_id,
            Character.deleted_at.is_(None),
        ).all()
        for character in characters:
            names = {str(character.name or "").strip().lower(), str(character.nickname or "").strip().lower()}
            if normalized in names:
                return character.id
        return None

    def _generate_and_upsert_character_impressions(self, *, novel, character, user_id: int, lore_entries: list):
        result = self._generate_character_impressions(novel, character, lore_entries)
        impressions = result.get("impressions") if isinstance(result, dict) else []
        if not isinstance(impressions, list):
            impressions = []
        saved = []
        for item in impressions[:12]:
            if not isinstance(item, dict):
                continue
            target_name = str(item.get("target_name") or "").strip()[:255]
            impression_text = str(item.get("impression_text") or "").strip()
            if not target_name or not impression_text:
                continue
            row = CinemaNovelCharacterImpression.query.filter(
                CinemaNovelCharacterImpression.novel_id == novel.id,
                CinemaNovelCharacterImpression.reviewer_character_id == character.id,
                CinemaNovelCharacterImpression.user_id == user_id,
                CinemaNovelCharacterImpression.target_name == target_name,
            ).first()
            if not row:
                row = CinemaNovelCharacterImpression(
                    novel_id=novel.id,
                    reviewer_character_id=character.id,
                    user_id=user_id,
                    target_name=target_name,
                )
            row.target_character_id = self._resolve_lore_target_character_id(novel.project_id, target_name)
            row.impression_text = impression_text[:1200]
            row.talk_hint = str(item.get("talk_hint") or "").strip()[:800] or None
            row.metadata_json = json_util.dumps(
                {
                    "source": "cinema_novel_character_impression",
                    "model": result.get("model"),
                    "usage": result.get("usage"),
                }
            )
            row.deleted_at = None
            db.session.add(row)
            saved.append(row)
        db.session.commit()
        return self.list_character_impressions(novel.id, reviewer_character_id=character.id, user_id=user_id)

    def _novel_review_context(self, novel) -> str:
        production = self._load_json(novel.production_json, default={})
        lines = [
            f"title: {novel.title or ''}",
            f"subtitle: {novel.subtitle or ''}",
            f"description: {novel.description or ''}",
        ]
        source_input = production.get("source_input") if isinstance(production, dict) else {}
        if isinstance(source_input, dict):
            premise = source_input.get("premise") if isinstance(source_input.get("premise"), dict) else {}
            if premise:
                lines.extend(
                    [
                        f"genre: {premise.get('genre') or ''}",
                        f"theme: {premise.get('theme') or ''}",
                        f"concept: {premise.get('concept_note') or ''}",
                    ]
                )
        outline = str((production or {}).get("outline_markdown") or "").strip()
        if outline:
            lines.append("production_outline:")
            lines.append(self._shorten_for_prompt(outline, 4500))
        chapters = self.list_chapters(novel.id)
        if chapters:
            lines.append("chapters:")
            for chapter in chapters[:8]:
                body = str(chapter.body_markdown or "").strip()
                lines.append(f"- {chapter.chapter_no}. {chapter.title}: {self._shorten_for_prompt(body, 1200)}")
        return "\n".join(lines)[:12000]

    def _fallback_review_memory_note(self, novel, character, review_text: str) -> str:
        return (
            f"{character.name}はラプ・シネマの上映作品『{novel.title}』を鑑賞済み。"
            f"印象に残った感想として「{review_text[:180]}」という反応を持っている。"
            "今後この作品が話題に出たら、鑑賞済みの体験として自分の口調で反応できる。"
        )

    def _upsert_review_feed_post(self, *, novel, character, user_id: int, review_text: str, existing_feed_post_id: int | None):
        post = FeedPost.query.filter(
            FeedPost.id == existing_feed_post_id,
            FeedPost.deleted_at.is_(None),
        ).first() if existing_feed_post_id else None
        generation_state = json_util.dumps(
            {
                "source": "cinema_novel_review",
                "cinema_novel_id": novel.id,
                "cinema_novel_title": novel.title,
                "character_id": character.id,
            }
        )
        if post:
            post.body = review_text
            post.character_id = character.id
            post.status = "published"
            post.generation_state_json = generation_state
            if not post.published_at:
                post.published_at = datetime.utcnow()
            db.session.commit()
            return post
        post = FeedPost(
            project_id=novel.project_id,
            character_id=character.id,
            created_by_user_id=user_id,
            body=review_text,
            status="published",
            like_count=0,
            generation_state_json=generation_state,
            published_at=datetime.utcnow(),
        )
        db.session.add(post)
        db.session.commit()
        return post

    def _upsert_review_memory_note(self, *, novel, character, user_id: int, note_text: str, existing_memory_note_id: int | None):
        note = CharacterMemoryNote.query.filter(
            CharacterMemoryNote.id == existing_memory_note_id,
            CharacterMemoryNote.user_id == user_id,
            CharacterMemoryNote.character_id == character.id,
        ).first() if existing_memory_note_id else None
        source_ref = f"cinema_novel:{novel.id}"
        if note:
            note.category = "fun_fact"
            note.note = note_text[:1000]
            note.source_type = "cinema_novel_review"
            note.source_ref = source_ref
            note.confidence = 1.0
            note.enabled = True
            db.session.commit()
            return note
        note = CharacterMemoryNote.query.filter(
            CharacterMemoryNote.user_id == user_id,
            CharacterMemoryNote.character_id == character.id,
            CharacterMemoryNote.source_type == "cinema_novel_review",
            CharacterMemoryNote.source_ref == source_ref,
        ).first()
        if note:
            note.note = note_text[:1000]
            note.enabled = True
            db.session.commit()
            return note
        note = CharacterMemoryNote(
            user_id=user_id,
            character_id=character.id,
            category="fun_fact",
            note=note_text[:1000],
            source_type="cinema_novel_review",
            source_ref=source_ref,
            confidence=1.0,
            enabled=True,
            pinned=False,
        )
        db.session.add(note)
        db.session.commit()
        return note

    def _upsert_impression_memory_note(self, *, novel, character, user_id: int, impressions: list):
        if not impressions:
            return None
        lines = []
        for impression in impressions[:8]:
            if not impression.impression_text:
                continue
            hint = f" 話題化: {impression.talk_hint}" if impression.talk_hint else ""
            lines.append(f"- {impression.target_name}: {impression.impression_text}{hint}")
        if not lines:
            return None
        note_text = (
            f"{character.name}は『{novel.title}』の登場人物・用語について次の鑑賞印象を持っている。\n"
            + "\n".join(lines)
        )[:1000]
        source_ref = f"cinema_novel:{novel.id}:impressions"
        note = CharacterMemoryNote.query.filter(
            CharacterMemoryNote.user_id == user_id,
            CharacterMemoryNote.character_id == character.id,
            CharacterMemoryNote.source_type == "cinema_novel_character_impression",
            CharacterMemoryNote.source_ref == source_ref,
        ).first()
        if not note:
            note = CharacterMemoryNote(
                user_id=user_id,
                character_id=character.id,
                category="fun_fact",
                source_type="cinema_novel_character_impression",
                source_ref=source_ref,
                confidence=1.0,
                enabled=True,
                pinned=False,
        )
        note.note = note_text
        note.enabled = True
        db.session.add(note)
        db.session.commit()
        return note

    def _shorten_for_prompt(self, value, limit: int = 500) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def save_production_outline(self, project_id: int, user_id: int, payload: dict | None):
        payload = dict(payload or {})
        title = str(payload.get("title") or "無題のノベル作品").strip() or "無題のノベル作品"
        outline_markdown = str(payload.get("outline_markdown") or "").strip()
        if not outline_markdown:
            raise ValueError("outline_markdown is required")
        source_input = payload.get("source_input") if isinstance(payload.get("source_input"), dict) else {}
        existing = CinemaNovel.query.filter(
            CinemaNovel.project_id == project_id,
            CinemaNovel.title == title,
            CinemaNovel.source_path.is_(None),
            CinemaNovel.deleted_at.is_(None),
        ).first()
        production_payload = {
            "source": "production_outline",
            "reader": "prebuilt",
            "generation_mode": "build_then_publish",
            "image_generation": "prebuilt_only",
            "source_input": source_input,
            "outline_markdown": outline_markdown,
            "model": payload.get("model"),
            "chapter_target_chars": payload.get("chapter_target_chars"),
            "usage": payload.get("usage"),
        }
        if existing:
            existing.subtitle = str(payload.get("subtitle") or existing.subtitle or "ノベル制作設計").strip() or None
            existing.description = str(payload.get("description") or source_input.get("theme") or existing.description or "").strip() or None
            existing.status = str(payload.get("status") or existing.status or "draft").strip() or "draft"
            existing.production_json = json_util.dumps(production_payload)
            db.session.commit()
            return existing
        novel = CinemaNovel(
            project_id=project_id,
            created_by_user_id=user_id,
            title=title,
            subtitle=str(payload.get("subtitle") or "ノベル制作設計").strip() or None,
            description=str(payload.get("description") or source_input.get("theme") or "").strip() or None,
            status=str(payload.get("status") or "draft").strip() or "draft",
            mode="cinema_novel",
            production_json=json_util.dumps(production_payload),
        )
        if novel.status not in self.VALID_STATUSES:
            novel.status = "draft"
        db.session.add(novel)
        db.session.commit()
        return novel

    def create_chapters_from_production_outline(self, novel_id: int):
        novel = self.get_novel(novel_id)
        if not novel:
            return None
        existing_chapters = self.list_chapters(novel.id)
        if existing_chapters:
            return existing_chapters
        production = self._load_json(novel.production_json, default={})
        outline = str((production or {}).get("outline_markdown") or "").strip()
        if not outline:
            raise ValueError("production outline is required")
        chapter_items = self._extract_chapter_items_from_outline(outline)
        if not chapter_items:
            raise ValueError("chapter list could not be detected from production outline")
        chapters = []
        for index, item in enumerate(chapter_items, start=1):
            chapter_no = int(item.get("chapter_no") or index)
            title = str(item.get("title") or f"第{chapter_no}章").strip()
            body = "\n".join(
                [
                    f"# {chapter_no:02d}. {title}",
                    "",
                    "## 制作設計メモ",
                    str(item.get("outline") or "").strip(),
                    "",
                    "## 本文",
                    "この章はまだ本文生成前です。制作パネルの「この章を深掘り生成」から本文を作成してください。",
                ]
            ).strip()
            chapter = CinemaNovelChapter(
                novel_id=novel.id,
                chapter_no=chapter_no,
                title=title,
                body_markdown=body,
                scene_json=json_util.dumps(self._markdown_to_scenes(body, chapter_no=chapter_no)),
                sort_order=index,
            )
            db.session.add(chapter)
            chapters.append(chapter)
        db.session.commit()
        return chapters

    def generate_title_image(self, novel_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        novel = self.get_novel(novel_id)
        if not novel:
            return None
        production = self._load_json(novel.production_json, default={})
        outline = str((production or {}).get("outline_markdown") or "").strip()
        source_input = (production or {}).get("source_input") if isinstance((production or {}).get("source_input"), dict) else {}
        premise = str(payload.get("premise") or source_input.get("theme") or novel.description or "").strip()
        options = self._user_setting_service.apply_cinema_novel_image_generation_settings(
            payload.get("image_options") or payload
        )
        references = self._matching_character_references(
            novel.project_id,
            "\n".join([novel.title or "", premise, outline[:2500]]),
            limit=4,
        )
        reference_ids = [item.get("base_asset_id") for item in references if item.get("base_asset_id")]
        reference_paths, reference_asset_ids = self._resolve_reference_image_paths(reference_ids)
        prompt = "\n".join(
            [
                f"ノベルゲーム『{novel.title}』のタイトル画像、オープニング画像。",
                "作品起動時に最初に表示される派手なキービジュアル。横長16:9。",
                "日本のビジュアルノベル、映画ポスター、ゲームタイトル画面の雰囲気。",
                "タイトルロゴを大きく中央または上部に配置。発光、金属感、ネオン、粒子、強いコントラストで印象的に。",
                "キャラクターがいる場合は、参考画像の顔立ち、髪型、衣装、雰囲気を保つ。",
                "読める文字は作品タイトルだけにする。余計な英字、透かし、出版社ロゴ、UIは入れない。",
                f"タイトル: {novel.title}",
                f"企画: {premise[:1200]}",
                f"章立て・世界観: {outline[:2500]}",
            ]
        )
        asset = self._generate_cinema_asset(
            project_id=novel.project_id,
            asset_type="cinema_novel_title_image",
            file_prefix=f"cinema_novel_{novel.id}_title",
            prompt=prompt,
            image_options=options,
            metadata={
                "source": "cinema_novel_title_image",
                "novel_id": novel.id,
                "reference_asset_ids": reference_asset_ids,
            },
            reference_paths=reference_paths,
        )
        novel.cover_asset_id = asset.id
        novel.poster_asset_id = asset.id
        db.session.commit()
        return {
            "novel": self.serialize_novel(novel, include_chapters=True),
            "asset": self._serialize_asset(asset.id),
            "reference_asset_ids": reference_asset_ids,
            "image_options": {
                "provider": options.get("provider"),
                "model": options.get("model"),
                "quality": options.get("quality"),
                "size": options.get("size"),
            },
        }

    def _extract_chapter_items_from_outline(self, outline: str):
        lines = outline.splitlines()
        chapter_section_lines = []
        in_chapter_section = False
        for line in lines:
            stripped = line.strip()
            if "章立て一覧" in stripped:
                in_chapter_section = True
                continue
            if in_chapter_section and stripped.startswith("#") and re.match(r"^#{1,6}\s*\d+\.", stripped):
                break
            if in_chapter_section:
                chapter_section_lines.append(line)
        if chapter_section_lines:
            lines = chapter_section_lines
        items = []
        current = None
        chapter_pattern = re.compile(
            r"^\s*(?:#{1,6}\s*)?(?:[-\*]\s*)?第\s*(\d{1,2})\s*(?:章|話|幕)\s*(.+?)\s*$"
        )
        for line in lines:
            stripped = line.strip()
            match = chapter_pattern.match(stripped)
            if match and not re.search(r"(章数|目標文字数|ターン|ステップ|候補|画像|章扉|劇中スチル|案)$", stripped):
                if current:
                    items.append(current)
                title = re.sub(r"^[「『【\[]|[」』】\]]$", "", match.group(2).strip(" -:："))
                title = re.split(r"\s{2,}|[｜|]", title, 1)[0].strip()
                current = {
                    "chapter_no": int(match.group(1)),
                    "title": title[:120] or f"第{int(match.group(1))}章",
                    "outline_lines": [stripped],
                }
                continue
            if current and stripped:
                current["outline_lines"].append(stripped)
        if current:
            items.append(current)
        normalized = []
        seen = set()
        for item in items:
            chapter_no = item.get("chapter_no")
            if not chapter_no or chapter_no in seen:
                continue
            seen.add(chapter_no)
            normalized.append(
                {
                    "chapter_no": chapter_no,
                    "title": item.get("title"),
                    "outline": "\n".join(item.get("outline_lines") or []),
                }
            )
        return normalized[:80]

    def generate_chapter_deepening_draft(self, payload: dict | None):
        payload = dict(payload or {})
        settings = self._user_setting_service.apply_cinema_novel_text_generation_settings(payload.get("text_options") or {})
        chapter_title = str(payload.get("chapter_title") or "無題の章").strip()
        outline = str(payload.get("outline") or "").strip()
        source_text = str(payload.get("source_text") or "").strip()
        character_notes = str(payload.get("character_notes") or "").strip()
        chapter_target_chars = int(settings.get("chapter_target_chars") or 3500)
        if not (payload.get("text_options") or {}).get("chapter_target_chars"):
            chapter_target_chars = min(chapter_target_chars, 4000)
        prompt = "\n".join(
            [
                "日本語で、ノベルゲーム風に再生するための長編小説の章本文を深掘りしてください。",
                "生成しながら読む作品ではなく、事前生成済み作品として保存される前提です。",
                "地の文とセリフをシーン単位に分けやすいように、短めの段落と明確な話者のセリフを使ってください。",
                "キャラクターの口調を強く出してください。ドルが出る場合は関西弁で、うち/あんた/せや/やで/へん を自然に使います。",
                "キャラクター演出メモに first_person, second_person, speech_style, speech_sample がある場合は最優先で守ってください。",
                "登録済みキャラクターの一人称・二人称・語尾・口癖を勝手に標準語へ均さないでください。",
                "",
                f"章タイトル: {chapter_title}",
                f"目標文字数: {chapter_target_chars}",
                "",
                "章の設計:",
                outline or "未指定",
                "",
                "既存本文または素材:",
                source_text or "未指定",
                "",
                "キャラクター演出メモ:",
                character_notes or "未指定",
                "",
                "出力は章本文のみ。解説や箇条書きではなく、読める本文として書いてください。",
            ]
        )
        result = self._text_ai_client.generate_text(
            prompt,
            model=settings.get("model"),
            temperature=0.85,
            max_tokens=32000,
        )
        return {
            "model": result.get("model"),
            "chapter_target_chars": chapter_target_chars,
            "chapter_markdown": result.get("text") or "",
            "usage": result.get("usage"),
        }

    def generate_chapter_deepening_for_chapter(self, novel_id: int, chapter_id: int, payload: dict | None):
        payload = dict(payload or {})
        novel = self.get_novel(novel_id)
        chapter = self.get_chapter(chapter_id)
        if not novel or not chapter or chapter.novel_id != novel.id:
            return None
        result = self.generate_chapter_deepening_draft(
            {
                "chapter_title": chapter.title,
                "source_text": chapter.body_markdown,
                "outline": payload.get("outline") or self._chapter_outline_hint(novel, chapter),
                "character_notes": payload.get("character_notes") or self._registered_character_context(novel.project_id),
                "text_options": payload.get("text_options") or {},
            }
        )
        if payload.get("apply"):
            chapter.body_markdown = result.get("chapter_markdown") or chapter.body_markdown
            chapter.scene_json = json_util.dumps(self._markdown_to_scenes(chapter.body_markdown or "", chapter_no=chapter.chapter_no))
            db.session.commit()
            result["chapter"] = self.serialize_chapter(chapter)
        return result

    def update_chapter_markdown(self, novel_id: int, chapter_id: int, payload: dict | None):
        payload = dict(payload or {})
        novel = self.get_novel(novel_id)
        chapter = self.get_chapter(chapter_id)
        if not novel or not chapter or chapter.novel_id != novel.id:
            return None
        body = str(payload.get("body_markdown") or "").strip()
        if not body:
            raise ValueError("body_markdown is required")
        title = str(payload.get("title") or chapter.title or "").strip()
        chapter.body_markdown = body
        if title:
            chapter.title = title
        chapter.scene_json = json_util.dumps(self._markdown_to_scenes(body, chapter_no=chapter.chapter_no))
        db.session.commit()
        return chapter

    def generate_chapter_image_plan(self, novel_id: int, chapter_id: int):
        novel = self.get_novel(novel_id)
        chapter = self.get_chapter(chapter_id)
        if not novel or not chapter or chapter.novel_id != novel.id:
            return None
        scenes = self._load_json(chapter.scene_json, default=[])
        sample = "\n".join(str(scene.get("text") or "") for scene in scenes[:12] if isinstance(scene, dict))[:1800]
        cover_references = self._matching_character_references(novel.project_id, "\n".join([chapter.title or "", chapter.body_markdown or "", sample]))
        visual_scenes = self._select_visual_scene_candidates(novel.project_id, scenes, limit=20)

        def character_plan_lines(references):
            if not references:
                return [
                    "登場キャラクター: 章本文からDB登録キャラクター名を特定できませんでした。",
                    "参照画像: なし。必要なら本文にキャラクター名を明記してから画像案を作り直してください。",
                ]
            return [
                "登場キャラクター: " + "、".join(item["name"] for item in references),
                "参照画像ID: " + "、".join(str(item["base_asset_id"]) for item in references if item.get("base_asset_id")),
                "参照画像の顔立ち、髪型、服装、キャラクターデザインを優先して維持する。",
            ]

        return {
            "chapter_id": chapter.id,
            "chapter_no": chapter.chapter_no,
            "title": chapter.title,
            "character_references": cover_references,
            "cover_prompt": "\n".join(
                [
                    f"ノベル作品『{novel.title}』第{chapter.chapter_no}章「{chapter.title}」の章扉画像。",
                    *character_plan_lines(cover_references),
                    "ノベルゲーム用の事前生成スチル。読み込み時に即表示できる横長シネマ構図。",
                    "キャラクターデザインを保ち、章の象徴的な場面を一枚にまとめる。",
                    "画像内に読める文字、ロゴ、透かしは入れない。",
                    f"章本文抜粋: {sample}",
                ]
            ),
            "still_prompts": [
                {
                    "scene_index": item["scene_index"],
                    "character_references": item["character_references"],
                    "prompt": "\n".join(
                        [
                            f"ノベル作品『{novel.title}』第{chapter.chapter_no}章「{chapter.title}」の劇中スチル。",
                            *character_plan_lines(item["character_references"]),
                            "ノベルゲーム再生用の横長映画スチル。キャラクター表情と場所の空気を重視。",
                            "画像内に読める文字、ロゴ、透かしは入れない。",
                            f"シーン本文: {item['text'][:900]}",
                        ]
                    ),
                }
                for item in visual_scenes
            ],
        }

    def generate_chapter_images(self, novel_id: int, chapter_id: int, payload: dict | None):
        payload = dict(payload or {})
        novel = self.get_novel(novel_id)
        chapter = self.get_chapter(chapter_id)
        if not novel or not chapter or chapter.novel_id != novel.id:
            return None
        image_plan = self.generate_chapter_image_plan(novel_id, chapter_id)
        if not image_plan:
            return None

        options = self._user_setting_service.apply_cinema_novel_image_generation_settings(
            payload.get("image_options") or payload
        )
        still_count = max(0, min(20, int(payload.get("still_count") or 20)))
        generate_cover = payload.get("generate_cover", False) is True
        overwrite = bool(payload.get("overwrite"))
        extra_reference_ids = payload.get("reference_asset_ids") or []
        if not isinstance(extra_reference_ids, list):
            extra_reference_ids = []
        cover_reference_ids = [
            item.get("base_asset_id")
            for item in image_plan.get("character_references") or []
            if item.get("base_asset_id")
        ]
        if not cover_reference_ids:
            cover_reference_ids = self._chapter_character_reference_asset_ids(novel.project_id, chapter)
        cover_reference_ids.extend(extra_reference_ids)
        cover_reference_paths, cover_reference_asset_ids = self._resolve_reference_image_paths(cover_reference_ids)
        used_reference_asset_ids = []

        scenes = self._load_json(chapter.scene_json, default=[])
        if not isinstance(scenes, list):
            scenes = []
        image_jobs = []
        if generate_cover and (overwrite or not chapter.cover_asset_id):
            image_jobs.append(
                {
                    "kind": "cover",
                    "project_id": novel.project_id,
                    "asset_type": "cinema_novel_chapter_cover",
                    "file_prefix": f"cinema_novel_{novel.id}_chapter_{chapter.id}_cover",
                    "prompt": image_plan.get("cover_prompt") or "",
                    "image_options": options,
                    "metadata": {
                        "source": "cinema_novel_chapter_cover",
                        "novel_id": novel.id,
                        "chapter_id": chapter.id,
                        "chapter_no": chapter.chapter_no,
                        "reference_asset_ids": cover_reference_asset_ids,
                    },
                    "reference_paths": cover_reference_paths,
                    "reference_asset_ids": cover_reference_asset_ids,
                }
            )
        for item in (image_plan.get("still_prompts") or [])[:still_count]:
            scene_index = item.get("scene_index")
            if not isinstance(scene_index, int) or scene_index < 0 or scene_index >= len(scenes):
                continue
            scene = scenes[scene_index]
            if not isinstance(scene, dict):
                continue
            if scene.get("still_asset_id") and not overwrite:
                continue
            still_reference_ids = [
                reference.get("base_asset_id")
                for reference in item.get("character_references") or []
                if reference.get("base_asset_id")
            ]
            still_reference_ids.extend(extra_reference_ids)
            still_reference_paths, still_reference_asset_ids = self._resolve_reference_image_paths(still_reference_ids)
            image_jobs.append(
                {
                    "kind": "still",
                    "scene_index": scene_index,
                    "project_id": novel.project_id,
                    "asset_type": "cinema_novel_scene_still",
                    "file_prefix": f"cinema_novel_{novel.id}_chapter_{chapter.id}_scene_{scene_index + 1}",
                    "prompt": item.get("prompt") or "",
                    "image_options": options,
                    "metadata": {
                        "source": "cinema_novel_scene_still",
                        "novel_id": novel.id,
                        "chapter_id": chapter.id,
                        "chapter_no": chapter.chapter_no,
                        "scene_index": scene_index,
                        "scene_id": scene.get("id"),
                        "reference_asset_ids": still_reference_asset_ids,
                    },
                    "reference_paths": still_reference_paths,
                    "reference_asset_ids": still_reference_asset_ids,
                }
            )

        created_assets = []
        failed_assets = []
        generated_results = self._generate_cinema_asset_jobs(image_jobs, parallel=payload.get("parallel", True) is not False)
        for job, result, error_message in generated_results:
            if error_message or result is None:
                failed_assets.append(
                    {
                        "kind": job.get("kind"),
                        "scene_index": job.get("scene_index"),
                        "message": error_message or "画像生成に失敗しました。",
                    }
                )
                continue
            asset = self._create_cinema_asset_from_result(
                project_id=job["project_id"],
                asset_type=job["asset_type"],
                file_prefix=job["file_prefix"],
                image_options=job["image_options"],
                metadata=job["metadata"],
                result=result,
            )
            if job["kind"] == "cover":
                chapter.cover_asset_id = asset.id
            elif job["kind"] == "still":
                scenes[job["scene_index"]]["still_asset_id"] = asset.id
            created_assets.append(self._serialize_asset(asset.id))
            used_reference_asset_ids.extend(job.get("reference_asset_ids") or [])

        chapter.scene_json = json_util.dumps(scenes)
        db.session.commit()
        return {
            "chapter": self.serialize_chapter(chapter),
            "assets": created_assets,
            "failed_assets": failed_assets,
            "reference_asset_ids": list(dict.fromkeys(used_reference_asset_ids)),
            "image_options": {
                "provider": options.get("provider"),
                "model": options.get("model"),
                "quality": options.get("quality"),
                "size": options.get("size"),
            },
        }

    def _chapter_outline_hint(self, novel, chapter):
        return "\n".join(
            [
                f"作品タイトル: {novel.title}",
                f"章番号: {chapter.chapter_no}",
                f"章タイトル: {chapter.title}",
                "既存章を3倍以上に膨らませる前提で、葛藤、会話、場所の描写、章の転換点を強める。",
            ]
        )

    def _default_character_notes(self):
        return "\n".join(
            [
                "ノア: 静かでやさしい観測者。照れると否定するが、本音がにじむ。",
                "ドル: 関西弁の赤金の女王。うち/あんた/せや/やで/へん を自然に使う。市場と欲望を笑いながら転がす。",
                "ぱぱぱ: ノアを価格ではなく本人として見る相棒。短い言葉で支える。",
                "ラプラス: 都市の最適化の声。冷たすぎず、論理で人を傷つける。",
            ]
        )

    def _resolve_book_folder(self, source_path: str):
        repo_root = Path(current_app.root_path).parent.resolve()
        candidate = Path(source_path)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        folder = candidate.resolve()
        docs_root = (repo_root / "docs" / "book").resolve()
        if docs_root not in [folder, *folder.parents]:
            raise ValueError("source_path must be inside docs/book")
        if not folder.exists() or not folder.is_dir():
            raise ValueError("source_path folder was not found")
        return folder

    def _chapter_files(self, folder: Path):
        files = []
        for path in sorted(folder.glob("*.md")):
            if path.name.startswith("00_"):
                continue
            if re.match(r"^\d{2}_", path.name):
                files.append(path)
        return files

    def _extract_chapter_heading(self, path: Path, body: str, fallback_no: int):
        first_heading = next((line.strip() for line in body.splitlines() if line.strip().startswith("# ")), "")
        match = re.match(r"^#\s*(\d+)[\.\s]+(.+)$", first_heading)
        if match:
            return int(match.group(1)), match.group(2).strip()
        file_match = re.match(r"^(\d{2})_(.+)\.md$", path.name)
        if file_match:
            return int(file_match.group(1)), file_match.group(2).strip()
        return fallback_no, path.stem

    def _markdown_to_scenes(self, body: str, *, chapter_no: int):
        lines = [line.rstrip() for line in body.splitlines()]
        chunks = []
        current = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    chunks.append("\n".join(current).strip())
                    current = []
                continue
            if stripped.startswith("#"):
                continue
            current.append(stripped)
        if current:
            chunks.append("\n".join(current).strip())
        scenes = []
        for index, text in enumerate(chunk for chunk in chunks if chunk):
            speaker = ""
            scene_type = "narration"
            dialogue = re.match(r"^「(.+)」$", text, re.S)
            if dialogue:
                scene_type = "dialogue"
                speaker = self._guess_speaker(dialogue.group(1))
                text = dialogue.group(1)
            scenes.append(
                {
                    "id": f"{chapter_no:02d}-{index + 1:03d}",
                    "type": scene_type,
                    "speaker": speaker,
                    "text": text,
                    "background_asset_id": None,
                    "still_asset_id": None,
                    "choice_list": [],
                }
            )
        return scenes

    def _guess_speaker(self, text: str):
        if any(token in text for token in ["うち", "あんた", "せや", "やで", "へん", "金融や"]):
            return "ドル"
        if any(token in text for token in ["旧人類", "暑いだけ", "興味ない", "観測", "わたし"]):
            return "ノア"
        return ""

    def _serialize_asset(self, asset_id: int | None):
        if not asset_id:
            return None
        asset = Asset.query.get(asset_id)
        if not asset or getattr(asset, "deleted_at", None):
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "media_url": self._media_url(asset.file_path),
            "width": asset.width,
            "height": asset.height,
        }

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
        try:
            rel = Path(file_path).resolve().relative_to(storage_root).as_posix()
        except Exception:
            return None
        return f"/media/{rel}"

    def _load_json(self, value, *, default=None):
        if not value:
            return default if default is not None else {}
        try:
            return json_util.loads(value)
        except Exception:
            return default if default is not None else {}

    def _resolve_reference_image_paths(self, raw_asset_ids):
        reference_paths = []
        reference_asset_ids = []
        if not isinstance(raw_asset_ids, list):
            return reference_paths, reference_asset_ids
        seen_asset_ids = set()
        for raw_asset_id in raw_asset_ids[:5]:
            try:
                asset_id = int(raw_asset_id)
            except (TypeError, ValueError):
                continue
            if asset_id in seen_asset_ids:
                continue
            asset = Asset.query.get(asset_id)
            if asset and not getattr(asset, "deleted_at", None) and asset.file_path and os.path.exists(asset.file_path):
                seen_asset_ids.add(asset.id)
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        return reference_paths, reference_asset_ids

    def _select_visual_scene_candidates(self, project_id: int, scenes, *, limit: int = 20) -> list[dict]:
        if not isinstance(scenes, list):
            return []
        candidates = []
        visual_words = [
            "見上げ",
            "立ち止ま",
            "歩",
            "扉",
            "窓",
            "ネオン",
            "広告",
            "画面",
            "部屋",
            "街",
            "雨",
            "光",
            "赤金",
            "観測塔",
            "表情",
            "横顔",
            "手",
            "目",
        ]
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            text = str(scene.get("text") or "").strip()
            if not text:
                continue
            references = self._matching_character_references(project_id, text)
            score = min(len(text), 800) / 100
            if references:
                score += 20
            if scene.get("speaker"):
                score += 4
            if any(word in text for word in visual_words):
                score += 5
            if len(text) < 25 and not references:
                score -= 10
            candidates.append(
                {
                    "scene_index": index,
                    "text": text,
                    "character_references": references,
                    "score": score,
                }
            )
        if len(candidates) <= limit:
            return sorted(candidates, key=lambda item: item["scene_index"])
        buckets = [[] for _ in range(limit)]
        for item in candidates:
            bucket_index = min(limit - 1, int((item["scene_index"] / max(1, len(scenes))) * limit))
            buckets[bucket_index].append(item)
        selected = []
        selected_indexes = set()
        for bucket in buckets:
            if not bucket:
                continue
            best = max(bucket, key=lambda item: (item["score"], -item["scene_index"]))
            selected.append(best)
            selected_indexes.add(best["scene_index"])
        if len(selected) < limit:
            for item in sorted(candidates, key=lambda item: (-item["score"], item["scene_index"])):
                if item["scene_index"] in selected_indexes:
                    continue
                selected.append(item)
                selected_indexes.add(item["scene_index"])
                if len(selected) >= limit:
                    break
        return sorted(selected[:limit], key=lambda item: item["scene_index"])

    def _chapter_character_reference_asset_ids(self, project_id: int, chapter) -> list[int]:
        scenes = self._load_json(chapter.scene_json, default=[])
        scene_text = "\n".join(str(scene.get("text") or "") for scene in scenes if isinstance(scene, dict))
        searchable_text = "\n".join([str(chapter.title or ""), str(chapter.body_markdown or ""), scene_text])
        return [item["base_asset_id"] for item in self._matching_character_references(project_id, searchable_text)]

    def _matching_character_references(self, project_id: int, searchable_text: str, *, limit: int = 5) -> list[dict]:
        characters = Character.query.filter(
            Character.project_id == project_id,
            Character.deleted_at.is_(None),
        ).order_by(Character.id.asc()).all()
        scored = []
        lowered = searchable_text.lower()
        for character in characters:
            asset_id = getattr(character, "base_asset_id", None)
            if not asset_id:
                continue
            names = [
                str(character.name or "").strip(),
                str(character.nickname or "").strip(),
            ]
            names = [name for name in names if name]
            if not names:
                continue
            score = 0
            for name in names:
                score += searchable_text.count(name)
                score += lowered.count(name.lower())
            if score > 0:
                scored.append((score, character.id, character, asset_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "id": character.id,
                "name": character.name,
                "nickname": character.nickname,
                "base_asset_id": asset_id,
            }
            for _score, _character_id, character, asset_id in scored[:limit]
        ]

    def _generate_cinema_asset(
        self,
        *,
        project_id: int,
        asset_type: str,
        file_prefix: str,
        prompt: str,
        image_options: dict,
        metadata: dict,
        reference_paths: list[str],
    ):
        result = self._generate_cinema_image_result(prompt, image_options, reference_paths)
        return self._create_cinema_asset_from_result(
            project_id=project_id,
            asset_type=asset_type,
            file_prefix=file_prefix,
            image_options=image_options,
            metadata=metadata,
            result=result,
        )

    def _generate_cinema_asset_jobs(self, jobs: list[dict], *, parallel: bool = True):
        if not jobs:
            return []
        if not parallel or len(jobs) == 1:
            results = []
            for job in jobs:
                try:
                    results.append((job, self._generate_cinema_image_result(job["prompt"], job["image_options"], job["reference_paths"]), None))
                except Exception as exc:
                    results.append((job, None, self._friendly_image_error_message(exc)))
            return results
        results = []
        max_workers = min(len(jobs), 2)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {
                executor.submit(
                    self._generate_cinema_image_result,
                    job["prompt"],
                    job["image_options"],
                    job["reference_paths"],
                ): job
                for job in jobs
            }
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    results.append((job, future.result(), None))
                except Exception as exc:
                    results.append((job, None, self._friendly_image_error_message(exc)))
        job_order = {id(job): index for index, job in enumerate(jobs)}
        results.sort(key=lambda item: job_order.get(id(item[0]), 0))
        return results

    def _generate_cinema_image_result(self, prompt: str, image_options: dict, reference_paths: list[str]):
        final_prompt = prompt
        if reference_paths:
            final_prompt = "\n".join(
                [
                    prompt,
                    "",
                    "添付された参照画像のキャラクターデザイン、顔立ち、髪型、服装の特徴を優先して維持してください。",
                    "別人に見える改変を避け、映画スチルとして構図・光・背景だけを場面に合わせてください。",
                ]
            )
        result = None
        last_error = None
        for attempt in range(1, 4):
            try:
                result = self._image_ai_client.generate_image(
                    final_prompt,
                    size=image_options.get("size") or "1536x1024",
                    quality=image_options.get("quality") or "medium",
                    model=image_options.get("model") or image_options.get("image_ai_model"),
                    provider=image_options.get("provider") or image_options.get("image_ai_provider"),
                    output_format="png",
                    background="opaque",
                    input_image_paths=reference_paths,
                    input_fidelity="high" if reference_paths else None,
                )
                break
            except RuntimeError as exc:
                last_error = exc
                if not self._is_transient_image_error(exc) or attempt >= 3:
                    raise RuntimeError(self._friendly_image_error_message(exc)) from exc
                time.sleep(2 * attempt)
        if result is None:
            raise RuntimeError(self._friendly_image_error_message(last_error))
        result["final_prompt"] = final_prompt
        return result

    def _is_transient_image_error(self, error: Exception | None) -> bool:
        message = str(error or "").lower()
        return any(token in message for token in ("502", "503", "504", "bad gateway", "gateway", "timed out", "timeout"))

    def _friendly_image_error_message(self, error: Exception | None) -> str:
        message = str(error or "")
        lowered = message.lower()
        if "<!doctype html" in lowered or "<html" in lowered or "bad gateway" in lowered or "502" in lowered:
            return "画像生成APIが一時的に失敗しました (502 Bad Gateway)。本文は反映済みです。少し待ってから画像生成だけ再実行してください。"
        if "timed out" in lowered or "timeout" in lowered:
            return "画像生成がタイムアウトしました。本文は反映済みです。少し待ってから画像生成だけ再実行してください。"
        return message[:500] or "画像生成に失敗しました。本文は反映済みです。画像生成だけ再実行してください。"

    def _create_cinema_asset_from_result(
        self,
        *,
        project_id: int,
        asset_type: str,
        file_prefix: str,
        image_options: dict,
        metadata: dict,
        result: dict,
    ):
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        file_name, file_path, file_size, checksum, width, height = self._store_generated_cinema_image(
            project_id=project_id,
            asset_type=asset_type,
            file_prefix=file_prefix,
            image_base64=image_base64,
        )
        metadata_payload = dict(metadata)
        metadata_payload.update(
            {
                "prompt": result.get("final_prompt") or metadata.get("prompt") or "",
                "revised_prompt": result.get("revised_prompt"),
                "provider": result.get("provider"),
                "model": result.get("model"),
                "quality": result.get("quality"),
                "size": image_options.get("size"),
                "operation": result.get("operation"),
            }
        )
        return self._asset_service.create_asset(
            project_id,
            {
                "asset_type": asset_type,
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "checksum": checksum,
                "width": width,
                "height": height,
                "metadata_json": json_util.dumps(metadata_payload),
            },
        )

    def _store_generated_cinema_image(
        self,
        *,
        project_id: int,
        asset_type: str,
        file_prefix: str,
        image_base64: str,
    ):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "generated", "cinema_novels", asset_type)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_prefix).strip("_") or "cinema_novel"
        file_name = f"{safe_prefix}_{timestamp}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        width = None
        height = None
        try:
            from PIL import Image

            with Image.open(file_path) as image:
                width, height = image.size
        except Exception:
            width = None
            height = None
        return file_name, file_path, len(raw_bytes), hashlib.sha256(raw_bytes).hexdigest(), width, height

    def __init__(
        self,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        asset_service: AssetService | None = None,
        user_setting_service: UserSettingService | None = None,
    ):
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._asset_service = asset_service or AssetService()
        self._user_setting_service = user_setting_service or UserSettingService()
