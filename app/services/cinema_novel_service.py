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
from ..models import Asset, Character, CinemaNovel, CinemaNovelChapter, CinemaNovelProgress, Project, World
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
        return payload

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
