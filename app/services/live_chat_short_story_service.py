from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from . import live_chat_image_support as image_support
from . import live_chat_prompt_support as prompt_support


class LiveChatShortStoryService:
    def __init__(
        self,
        *,
        text_ai_client: TextAIClient,
        context_provider,
        image_ai_client: ImageAIClient | None = None,
        chat_session_service=None,
        asset_service=None,
        session_image_service=None,
        serialize_session_image=None,
    ):
        self._text_ai_client = text_ai_client
        self._context_provider = context_provider
        self._image_ai_client = image_ai_client
        self._chat_session_service = chat_session_service
        self._asset_service = asset_service
        self._session_image_service = session_image_service
        self._serialize_session_image = serialize_session_image

    def generate_short_story(self, session_id: int, payload: dict | None = None) -> dict | None:
        context = self._context_provider(session_id) if self._context_provider else None
        if not context:
            return None

        payload = dict(payload or {})
        messages = self._story_messages(context.get("messages") or [])
        if len(messages) < 2:
            raise ValueError("ショートストーリー化するには会話ログが2件以上必要です")

        prompt = self._build_prompt(context, messages, payload)
        try:
            result = self._text_ai_client.generate_text(
                prompt,
                temperature=0.7,
                response_format={"type": "json_object"},
                max_tokens=2600,
            )
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if not isinstance(parsed, dict):
                raise RuntimeError("short story response is invalid")
            story = self._normalize_story(parsed)
            story["source_message_count"] = len(messages)
            story["model"] = result.get("model")
            story["tone"] = str(payload.get("tone") or "余韻のあるビジュアルノベル調").strip()
            story["length"] = str(payload.get("length") or "1200〜1800字").strip()
            story["instruction"] = str(payload.get("instruction") or "").strip()
            if self._should_generate_images(payload):
                story["images"] = self._safe_generate_story_images(session_id, context, story, payload)
            return story
        except Exception:
            story = self._fallback_story(context, messages)
            story["source_message_count"] = len(messages)
            story["model"] = None
            story["fallback"] = True
            story["tone"] = str(payload.get("tone") or "余韻のあるビジュアルノベル調").strip()
            story["length"] = str(payload.get("length") or "1200〜1800字").strip()
            story["instruction"] = str(payload.get("instruction") or "").strip()
            if self._should_generate_images(payload):
                story["images"] = self._safe_generate_story_images(session_id, context, story, payload)
            return story

    def save_short_story(self, session_id: int, payload: dict | None = None):
        if not self._chat_session_service:
            raise RuntimeError("chat session service is not configured")
        payload = dict(payload or {})
        story = payload.get("story") if isinstance(payload.get("story"), dict) else payload
        normalized = self._normalize_saved_story(story)
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        settings = self._load_settings(getattr(session, "settings_json", None))
        saved = settings.setdefault("saved_short_stories", [])
        if not isinstance(saved, list):
            saved = []
            settings["saved_short_stories"] = saved
        saved_story = {
            **normalized,
            "id": payload.get("id") or f"short_story_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        saved.append(saved_story)
        settings["saved_short_stories"] = saved[-20:]
        self._chat_session_service.update_session(session_id, {"settings_json": settings})
        return {"saved_story": saved_story, "saved_count": len(settings["saved_short_stories"])}

    def _story_messages(self, messages: list[dict]) -> list[dict]:
        useful = []
        for message in messages:
            text = str(message.get("message_text") or "").strip()
            if not text:
                continue
            sender_type = str(message.get("sender_type") or "").strip()
            speaker = str(message.get("speaker_name") or "").strip()
            useful.append(
                {
                    "speaker": speaker or ("プレイヤー" if sender_type == "user" else sender_type or "不明"),
                    "sender_type": sender_type,
                    "text": text,
                }
            )
        return useful[-80:]

    def _build_prompt(self, context: dict, messages: list[dict], payload: dict) -> str:
        session = context.get("session") or {}
        project = context.get("project") or {}
        world = context.get("world") or {}
        tone = str(payload.get("tone") or "余韻のあるビジュアルノベル調").strip()
        length = str(payload.get("length") or "1200〜1800字").strip()
        instruction = str(payload.get("instruction") or "").strip()
        lines = [
            "あなたはライブチャットの会話ログを、読み切りのショートストーリーへ再構成する小説家です。",
            "JSONオブジェクトのみを返してください。",
            "必須キー: title, synopsis, body, afterword。",
            "キー名は翻訳せず、上記の英語表記をそのまま使ってください。",
            "title は自然な日本語タイトルにしてください。",
            "synopsis は80〜160字の日本語要約にしてください。",
            "body は日本語の短編本文にしてください。",
            "afterword は、この短編がどの会話の流れを拾ったかを短く日本語で説明してください。",
            f"文体: {tone}",
            f"本文の長さ: {length}",
            "追加指示がある場合は、会話ログの事実と安全性を優先したうえで反映してください。",
            "会話ログの事実、関係性、呼び方、世界観を尊重してください。",
            "会話をそのまま台本化するのではなく、地の文、情景、感情の揺れ、短い会話を織り交ぜて短編として読める形にしてください。",
            "ログにない重大事件、告白、関係の確定、設定変更は勝手に足さないでください。",
            "露骨な性的描写は避け、必要なら視線、間、余韻、距離感で表現してください。",
            "18歳未満と思われる人物や、同意が確認できない関係について性的な描写を足さないでください。",
            f"プロジェクト: {project.get('title') or 'Untitled'}",
            f"セッション: {session.get('title') or ''}",
            f"プレイヤー名: {session.get('player_name') or 'プレイヤー'}",
            f"世界観: {world.get('overview') or world.get('name') or ''}",
        ]
        if instruction:
            lines.append(f"追加指示: {instruction}")
        room = context.get("room") or {}
        objective = (
            ((session.get("room_snapshot_json") or {}) if isinstance(session.get("room_snapshot_json"), dict) else {}).get("conversation_objective")
            or room.get("conversation_objective")
            or ((session.get("settings_json") or {}) if isinstance(session.get("settings_json"), dict) else {}).get("conversation_objective")
            or ""
        )
        if objective:
            lines.append(f"会話の目的: {objective}")
        lines.append("登場キャラクター:")
        for character in context.get("characters") or []:
            lines.append(
                f"- {character.get('name')}: 性格={character.get('personality') or ''}, 口調={character.get('speech_style') or ''}, 一人称={character.get('first_person') or ''}, 二人称={character.get('second_person') or ''}"
            )
        lines.append("会話ログ:")
        for message in messages:
            lines.append(f"- {message['speaker']}: {message['text']}")
        return "\n".join(lines)

    def _should_generate_images(self, payload: dict) -> bool:
        value = payload.get("generate_images", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _safe_generate_story_images(self, session_id: int, context: dict, story: dict, payload: dict) -> dict:
        try:
            return self._generate_story_images(session_id, context, story, payload)
        except Exception as exc:
            return {"error": str(exc), "opening": None, "ending": None}

    def _generate_story_images(self, session_id: int, context: dict, story: dict, payload: dict) -> dict:
        if not all([self._image_ai_client, self._chat_session_service, self._asset_service, self._session_image_service]):
            raise RuntimeError("short story image generation is not configured")
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return {"opening": None, "ending": None}
        reference_paths, reference_asset_ids = self._collect_reference_assets(context)
        common = {
            "quality": payload.get("image_quality") or payload.get("quality") or "low",
            "size": payload.get("image_size") or payload.get("size") or "1536x1024",
            "model": payload.get("model") or payload.get("image_ai_model"),
            "provider": payload.get("provider") or payload.get("image_ai_provider"),
        }
        opening_prompt = self._build_story_image_prompt(context, story, payload, image_role="opening")
        ending_prompt = self._build_story_image_prompt(context, story, payload, image_role="ending")
        return {
            "opening": self._generate_one_story_image(
                session,
                opening_prompt,
                "short_story_opening",
                reference_paths,
                reference_asset_ids,
                common,
            ),
            "ending": self._generate_one_story_image(
                session,
                ending_prompt,
                "short_story_ending",
                reference_paths,
                reference_asset_ids,
                common,
            ),
        }

    def _collect_reference_assets(self, context: dict):
        characters = context.get("characters") or []
        return image_support.collect_reference_assets(characters, limit=2)

    def _build_story_image_prompt(self, context: dict, story: dict, payload: dict, *, image_role: str) -> str:
        session = context.get("session") or {}
        project = context.get("project") or {}
        world = context.get("world") or {}
        characters = []
        for character in context.get("characters") or []:
            characters.append(
                f"- {character.get('name')}: 外見={character.get('appearance_summary') or ''}, 性格={character.get('personality') or ''}, 口調={character.get('speech_style') or ''}"
            )
        role_line = (
            "オープニング画像。短編が始まる直前の期待感、舞台、登場人物の関係性が伝わる1枚。"
            if image_role == "opening"
            else "エンディング画像。短編本文の最後の余韻、感情の着地点、印象的なラストシーンが伝わる1枚。"
        )
        body_excerpt = str(story.get("body") or "")
        if image_role == "opening":
            body_excerpt = body_excerpt[:900]
        else:
            body_excerpt = body_excerpt[-1200:]
        prompt = "\n".join(
            [
                "ライブチャットから生成されたショートストーリーに挿入する横長のビジュアルノベルCGを生成してください。",
                role_line,
                "画像内に文字、タイトル、字幕、ロゴ、UI、透かしは入れないでください。",
                "参照画像がある場合は、同じキャラクター、顔立ち、髪型、体型、年齢感、画風、質感を維持してください。",
                "ただの立ち絵ではなく、前景・中景・背景・光で物語の場面として見せてください。",
                "露骨な性的描写、裸体、局部や胸部の過度な強調、未成年に見える性的表現は禁止です。",
                f"作風指定: {payload.get('tone') or '余韻のあるビジュアルノベル調'}",
                f"プロジェクト: {project.get('title') or ''}",
                f"セッション: {session.get('title') or ''}",
                f"世界観: {world.get('overview') or world.get('name') or ''}",
                f"短編タイトル: {story.get('title') or ''}",
                f"要約: {story.get('synopsis') or ''}",
                "登場キャラクター:",
                "\n".join(characters) or "- なし",
                "画像化する本文の手がかり:",
                body_excerpt,
            ]
        )
        return prompt_support.forbid_text_in_image(prompt)

    def _generate_one_story_image(
        self,
        session,
        prompt: str,
        image_type: str,
        reference_paths: list[str],
        reference_asset_ids: list[int],
        options: dict,
    ):
        result = self._image_ai_client.generate_image(
            prompt,
            size=options["size"],
            quality=options["quality"],
            model=options.get("model"),
            provider=options.get("provider"),
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("short story image generation response did not include image_base64")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=self._storage_root(),
            project_id=session.project_id,
            session_id=session.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            session.project_id,
            {
                "asset_type": "short_story_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "live_chat_short_story",
                        "image_type": image_type,
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "quality": options["quality"],
                        "size": options["size"],
                        "reference_asset_ids": reference_asset_ids,
                        "revised_prompt": result.get("revised_prompt"),
                    }
                ),
            },
        )
        row = self._session_image_service.create_session_image(
            session.id,
            {
                "asset_id": asset.id,
                "image_type": image_type,
                "prompt_text": result.get("revised_prompt") or prompt,
                "state_json": {
                    "source": "live_chat_short_story",
                    "image_type": image_type,
                    "reference_asset_ids": reference_asset_ids,
                },
                "quality": options["quality"],
                "size": options["size"],
                "is_selected": 0,
                "is_reference": 0,
            },
        )
        if self._serialize_session_image:
            return self._serialize_session_image(row)
        return {"id": row.id, "asset_id": asset.id, "image_type": image_type}

    def _storage_root(self):
        try:
            return current_app.config.get("STORAGE_ROOT") or "storage"
        except RuntimeError:
            return "storage"

    def _load_settings(self, value):
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _normalize_saved_story(self, story: dict) -> dict:
        title = str(story.get("title") or "").strip()
        body = str(story.get("body") or "").strip()
        if not title:
            raise ValueError("title is required")
        if not body:
            raise ValueError("body is required")
        images = story.get("images") if isinstance(story.get("images"), dict) else {}
        return {
            "title": title,
            "synopsis": str(story.get("synopsis") or "").strip(),
            "body": body,
            "afterword": str(story.get("afterword") or "").strip(),
            "source_message_count": int(story.get("source_message_count") or 0),
            "model": story.get("model"),
            "tone": story.get("tone"),
            "length": story.get("length"),
            "instruction": story.get("instruction"),
            "images": images,
        }

    def _normalize_story(self, parsed: dict) -> dict:
        title = str(parsed.get("title") or "チャットから生まれた短編").strip()
        synopsis = str(parsed.get("synopsis") or "").strip()
        body = str(parsed.get("body") or "").strip()
        afterword = str(parsed.get("afterword") or "").strip()
        if not body:
            raise RuntimeError("short story body is empty")
        return {
            "title": title or "チャットから生まれた短編",
            "synopsis": synopsis,
            "body": body,
            "afterword": afterword,
        }

    def _fallback_story(self, context: dict, messages: list[dict]) -> dict:
        title = f"{(context.get('session') or {}).get('title') or 'ライブチャット'}の短い記録"
        excerpt_lines = []
        for message in messages[-12:]:
            excerpt_lines.append(f"{message['speaker']}は言った。「{message['text']}」")
        body = "\n".join(excerpt_lines)
        return {
            "title": title,
            "synopsis": "会話ログをもとに、直近のやりとりを短い読み物として整えました。",
            "body": body,
            "afterword": "AI生成が使えなかったため、会話ログを読みやすい形に整えた簡易版です。",
        }
