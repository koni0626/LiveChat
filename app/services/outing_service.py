from __future__ import annotations

import os
import base64
import binascii
import uuid
from datetime import datetime

from flask import current_app

from ..clients.text_ai_client import TextAIClient
from ..clients.image_ai_client import ImageAIClient
from ..repositories.asset_repository import AssetRepository
from ..repositories.character_repository import CharacterRepository
from ..repositories.letter_repository import LetterRepository
from ..repositories.outing_session_repository import OutingSessionRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..utils import json_util
from .asset_service import AssetService
from .closet_service import ClosetService
from .project_service import ProjectService
from .user_setting_service import UserSettingService
from .world_service import WorldService
from .world_news_service import WorldNewsService


class OutingService:
    def __init__(
        self,
        outing_repository: OutingSessionRepository | None = None,
        character_repository: CharacterRepository | None = None,
        location_repository: WorldLocationRepository | None = None,
        asset_repository: AssetRepository | None = None,
        letter_repository: LetterRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        asset_service: AssetService | None = None,
        user_setting_service: UserSettingService | None = None,
        world_news_service: WorldNewsService | None = None,
        closet_service: ClosetService | None = None,
    ):
        self._outings = outing_repository or OutingSessionRepository()
        self._characters = character_repository or CharacterRepository()
        self._locations = location_repository or WorldLocationRepository()
        self._assets = asset_repository or AssetRepository()
        self._letters = letter_repository or LetterRepository()
        self._projects = project_service or ProjectService()
        self._worlds = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._asset_service = asset_service or AssetService()
        self._user_setting_service = user_setting_service or UserSettingService()
        self._world_news_service = world_news_service or WorldNewsService()
        self._closet_service = closet_service or ClosetService()

    def options(self, project_id: int, user_id: int) -> dict:
        return {
            "characters": [self._serialize_character(character) for character in self._characters.list_by_project(project_id)],
            "locations": [self._serialize_location(location) for location in self._locations.list_by_project(project_id)],
            "outfits": self._closet_service.list_project_outfits(project_id).get("outfits", []),
            "recent_outings": self.list_outings(project_id, user_id, limit=8),
        }

    def list_outings(self, project_id: int, user_id: int, *, limit: int = 30) -> list[dict]:
        return [self.serialize_outing(row, compact=True) for row in self._outings.list_by_project_user(project_id, user_id, limit=limit)]

    def get_outing(self, outing_id: int, user_id: int):
        row = self._outings.get(outing_id)
        if not row or row.user_id != user_id:
            return None
        return self.serialize_outing(row)

    def start_outing(self, project_id: int, user_id: int, payload: dict):
        character_id = int(payload.get("character_id") or 0)
        location_id = int(payload.get("location_id") or 0)
        mood = str(payload.get("mood") or "おまかせ").strip()[:100]
        outfit_id = int(payload.get("outfit_id") or 0) or None
        max_steps = max(2, min(5, int(payload.get("max_steps") or 3)))
        character = self._characters.get(character_id)
        location = self._locations.get(location_id)
        if not character or character.project_id != project_id:
            raise ValueError("キャラクターを選択してください。")
        if not location or location.project_id != project_id:
            raise ValueError("施設を選択してください。")

        outfit = self._closet_service.resolve_outfit(character.id, outfit_id)
        if outfit and outfit.project_id != project_id:
            outfit = None

        state = {
            "steps": [],
            "choices": [],
            "memory_notes": [],
            "selected_choices": [],
            "selected_outfit_id": outfit.id if outfit else None,
        }
        title = f"{character.name}と{location.name}へ"
        row = self._outings.create(
            {
                "project_id": project_id,
                "user_id": user_id,
                "character_id": character.id,
                "location_id": location.id,
                "title": title,
                "mood": mood,
                "max_steps": max_steps,
                "state_json": json_util.dumps(state),
            }
        )
        step = self._generate_step(row, character, location, state, selected_choice=None)
        step = self._attach_step_image(row, character, location, step, user_id=user_id)
        state["steps"].append(step)
        state["choices"] = step.get("choices") or []
        row = self._outings.update(
            row.id,
            {
                "summary": step.get("narration"),
                "state_json": json_util.dumps(state),
            },
        )
        return self.serialize_outing(row)

    def choose(self, outing_id: int, user_id: int, payload: dict):
        row = self._outings.get(outing_id)
        if not row or row.user_id != user_id:
            return None
        if row.status == "completed":
            return self.serialize_outing(row)
        state = self._load_state(row.state_json)
        choices = state.get("choices") or []
        choice_id = str(payload.get("choice_id") or "").strip()
        selected = next((choice for choice in choices if str(choice.get("id")) == choice_id), None)
        if not selected:
            raise ValueError("選択肢を選んでください。")

        character = self._characters.get(row.character_id)
        location = self._locations.get(row.location_id)
        if not character or not location:
            raise LookupError("not_found")

        state.setdefault("selected_choices", []).append(selected)
        state.setdefault("memory_notes", []).append(str(selected.get("intent") or selected.get("label") or "").strip())
        next_step_index = int(row.current_step or 0) + 1
        is_final = next_step_index >= int(row.max_steps or 3)
        step = self._generate_step(row, character, location, state, selected_choice=selected, is_final=is_final)
        step = self._attach_step_image(row, character, location, step, user_id=user_id, selected_choice=selected, is_final=is_final)
        state.setdefault("steps", []).append(step)
        state["choices"] = [] if is_final else (step.get("choices") or [])
        if step.get("memory_delta"):
            state.setdefault("memory_notes", []).append(step.get("memory_delta"))

        updates = {
            "current_step": next_step_index,
            "summary": step.get("narration"),
            "state_json": json_util.dumps(state),
        }
        if is_final:
            updates.update(
                {
                    "status": "completed",
                    "memory_title": step.get("memory_title") or f"{location.name}での思い出",
                    "memory_summary": step.get("memory_summary") or self._fallback_memory_summary(row, character, location, state),
                    "completed_at": datetime.utcnow(),
                }
            )
        row = self._outings.update(row.id, updates)
        if is_final:
            self._send_completion_letter(row, character, location, state, step)
            self._create_completion_news(row, character, location, state)
        return self.serialize_outing(row)

    def serialize_outing(self, row, *, compact: bool = False) -> dict:
        if not row:
            return None
        state = self._load_state(row.state_json)
        data = {
            "id": row.id,
            "project_id": row.project_id,
            "user_id": row.user_id,
            "character_id": row.character_id,
            "location_id": row.location_id,
            "title": row.title,
            "status": row.status,
            "current_step": row.current_step,
            "max_steps": row.max_steps,
            "mood": row.mood,
            "summary": row.summary,
            "memory_title": row.memory_title,
            "memory_summary": row.memory_summary,
            "character": self._serialize_character(self._characters.get(row.character_id)),
            "location": self._serialize_location(self._locations.get(row.location_id)),
            "selected_outfit": self._closet_service.serialize_outfit(
                self._closet_service.resolve_outfit(row.character_id, state.get("selected_outfit_id"))
            ),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
        if not compact:
            data["state"] = state
            data["steps"] = self._hydrate_steps(state.get("steps") or [])
            data["choices"] = state.get("choices") or []
        return data

    def _hydrate_steps(self, steps: list[dict]) -> list[dict]:
        hydrated = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            item = dict(step)
            item["image_asset"] = self._serialize_asset(self._assets.get(item.get("image_asset_id"))) if item.get("image_asset_id") else None
            hydrated.append(item)
        return hydrated

    def _generate_step(self, row, character, location, state: dict, *, selected_choice: dict | None, is_final: bool = False) -> dict:
        try:
            prompt = self._build_step_prompt(row, character, location, state, selected_choice, is_final=is_final)
            result = self._text_ai_client.generate_text(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.8,
                max_tokens=1200,
            )
            parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
            return self._normalize_step(parsed, row, character, location, is_final=is_final)
        except Exception:
            return self._fallback_step(row, character, location, selected_choice, is_final=is_final)

    def _build_step_prompt(self, row, character, location, state: dict, selected_choice: dict | None, *, is_final: bool) -> str:
        project = self._projects.get_project(row.project_id)
        world = self._worlds.get_world(row.project_id)
        previous_steps = state.get("steps") or []
        selected_choices = state.get("selected_choices") or []
        return f"""
Return only JSON.
Create one step for an independent "おでかけ" mini event. This is not free chat and not a long story.
The event should feel like a short date/outing scene at a selected world-map facility.

Required JSON keys:
{{
  "scene_title": "短い見出し",
  "narration": "地の文。180〜320字。二人の行動、場所の空気、距離感を描く。",
  "character_line": "キャラクターの一言。日本語。",
  "location_note": "施設ならではの描写。60〜140字。",
  "choices": [{{"id":"a","label":"選択肢", "intent":"選んだ意味"}}],
  "memory_delta": "この場面で残った小さな記憶",
  "memory_title": "完了時のみ。思い出タイトル",
  "memory_summary": "完了時のみ。思い出要約"
}}

Rules:
- All values must be Japanese strings except choices array.
- choices must be 2 or 3 items when is_final=false.
- choices must be [] when is_final=true.
- Keep it compact and interactive. Do not write a full chapter.
- Preserve character personality and speech style.
- Use the facility as the main source of events.
- Avoid explicit sexual content.

is_final: {str(is_final).lower()}
project: {getattr(project, "title", "") or ""}
project_summary: {getattr(project, "summary", "") or ""}
world_overview: {getattr(world, "overview", "") if world else ""}
world_tone: {getattr(world, "tone", "") if world else ""}
character_name: {character.name or ""}
character_nickname: {character.nickname or ""}
character_personality: {character.personality or ""}
character_speech_style: {character.speech_style or ""}
character_memory: {character.memory_notes or ""}
location_name: {location.name or ""}
location_region: {location.region or ""}
location_type: {location.location_type or ""}
location_description: {location.description or ""}
mood: {row.mood or ""}
current_step: {row.current_step or 0}
max_steps: {row.max_steps or 3}
selected_choice: {json_util.dumps(selected_choice or {})}
selected_choices_so_far: {json_util.dumps(selected_choices)}
previous_steps: {json_util.dumps(previous_steps[-3:])}
""".strip()

    def _normalize_step(self, parsed: dict, row, character, location, *, is_final: bool) -> dict:
        choices = parsed.get("choices") if isinstance(parsed.get("choices"), list) else []
        normalized_choices = []
        if not is_final:
            for index, choice in enumerate(choices[:3]):
                if not isinstance(choice, dict):
                    continue
                label = str(choice.get("label") or "").strip()
                if not label:
                    continue
                normalized_choices.append(
                    {
                        "id": str(choice.get("id") or chr(ord("a") + index))[:12],
                        "label": label[:60],
                        "intent": str(choice.get("intent") or label).strip()[:160],
                    }
                )
            if len(normalized_choices) < 2:
                normalized_choices = self._fallback_choices(location)
        return {
            "scene_title": str(parsed.get("scene_title") or f"{location.name}での時間").strip()[:120],
            "narration": str(parsed.get("narration") or "").strip() or self._fallback_narration(character, location),
            "character_line": str(parsed.get("character_line") or f"「{location.name}、一緒に来られてよかった。」").strip()[:500],
            "location_note": str(parsed.get("location_note") or location.description or "").strip()[:300],
            "choices": [] if is_final else normalized_choices,
            "memory_delta": str(parsed.get("memory_delta") or "").strip()[:240],
            "memory_title": str(parsed.get("memory_title") or "").strip()[:160],
            "memory_summary": str(parsed.get("memory_summary") or "").strip()[:700],
        }

    def _fallback_step(self, row, character, location, selected_choice: dict | None, *, is_final: bool) -> dict:
        action = str((selected_choice or {}).get("label") or "誘いに応える").strip()
        if is_final:
            return {
                "scene_title": f"{location.name}の帰り道",
                "narration": f"{action}。その選択をきっかけに、{location.name}で過ごした時間は静かにまとまっていく。{character.name}は少し名残惜しそうに周囲を見渡し、今日の景色を忘れないように胸にしまった。",
                "character_line": f"「今日は来てよかった。{location.name}のこと、前より好きになった気がする」",
                "location_note": str(location.description or f"{location.name}の空気が、帰り際まで二人の余韻を残している。")[:300],
                "choices": [],
                "memory_delta": f"{location.name}で一緒に過ごした余韻",
                "memory_title": f"{location.name}で過ごした日",
                "memory_summary": self._fallback_memory_summary(row, character, location, {}),
            }
        return {
            "scene_title": f"{location.name}へ",
            "narration": f"{character.name}と一緒に{location.name}を訪れる。{location.description or 'その場所には、普段の会話だけでは触れられない空気が流れている。'} 二人は歩調を合わせながら、今日ここで何をするかを自然に探し始めた。",
            "character_line": f"「せっかく来たんだし、少し見て回ろう？」",
            "location_note": str(location.description or f"{location.name}ならではの雰囲気がある。")[:300],
            "choices": self._fallback_choices(location),
            "memory_delta": f"{character.name}と{location.name}を訪れた",
            "memory_title": "",
            "memory_summary": "",
        }

    def _fallback_choices(self, location) -> list[dict]:
        return [
            {"id": "a", "label": "ゆっくり見て回る", "intent": f"{location.name}の雰囲気を一緒に味わう"},
            {"id": "b", "label": "相手の反応を聞く", "intent": "キャラクターがこの場所をどう感じているか尋ねる"},
            {"id": "c", "label": "記念になることを探す", "intent": "今日だけの小さな思い出を作る"},
        ]

    def _fallback_narration(self, character, location) -> str:
        return f"{character.name}と{location.name}を歩く。周囲の空気や音が、いつもの会話とは違う距離感を作っていく。"

    def _fallback_memory_summary(self, row, character, location, state: dict) -> str:
        return f"{character.name}と{location.name}へ出かけた。{row.mood or '自然な流れ'}の雰囲気で過ごし、施設の空気と二人の距離感が少しだけ特別な記憶として残った。"

    def _attach_step_image(
        self,
        row,
        character,
        location,
        step: dict,
        *,
        user_id: int,
        selected_choice: dict | None = None,
        is_final: bool = False,
    ) -> dict:
        try:
            state = self._load_state(row.state_json)
            outfit = self._closet_service.resolve_outfit(character.id, state.get("selected_outfit_id"))
            prompt = self._build_step_image_prompt(row, character, location, step, selected_choice=selected_choice, is_final=is_final)
            reference_paths, reference_asset_ids = self._step_reference_paths(character, location, outfit=outfit)
            image_options = self._user_setting_service.apply_image_generation_settings(
                user_id,
                {"size": "1024x1536", "quality": current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium")},
            )
            result = self._image_ai_client.generate_image(
                prompt,
                size=image_options.get("size") or "1024x1536",
                quality=image_options.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
                model=image_options.get("model"),
                provider=image_options.get("provider"),
                input_image_paths=reference_paths,
                input_fidelity="high" if reference_paths else None,
                output_format="png",
                background="opaque",
            )
            image_base64 = result.get("image_base64")
            if not image_base64:
                raise RuntimeError("outing image generation response did not include image_base64")
            file_name, file_path, file_size = self._store_generated_outing_image(row.project_id, row.id, image_base64)
            asset = self._asset_service.create_asset(
                row.project_id,
                {
                    "asset_type": "outing_image",
                    "file_name": file_name,
                    "file_path": file_path,
                    "mime_type": "image/png",
                    "file_size": file_size,
                    "metadata_json": json_util.dumps(
                        {
                            "source": "outing_step_image",
                            "outing_id": row.id,
                            "location_id": location.id,
                            "character_id": character.id,
                            "provider": result.get("provider"),
                            "model": result.get("model"),
                            "quality": result.get("quality") or image_options.get("quality"),
                            "size": image_options.get("size") or "1024x1536",
                            "aspect_ratio": result.get("aspect_ratio"),
                            "prompt": prompt,
                            "revised_prompt": result.get("revised_prompt"),
                            "reference_asset_ids": reference_asset_ids,
                            "outfit_id": getattr(outfit, "id", None),
                            "safety_retry": result.get("safety_retry"),
                        }
                    ),
                },
            )
            step = dict(step)
            step["image_asset_id"] = asset.id
            return step
        except Exception as exc:
            step = dict(step)
            step["image_error"] = str(exc)[:300]
            return step

    def _build_step_image_prompt(self, row, character, location, step: dict, *, selected_choice: dict | None, is_final: bool) -> str:
        mood = row.mood or ""
        choice_label = (selected_choice or {}).get("label") or ""
        state = self._load_state(row.state_json)
        outfit = self._closet_service.resolve_outfit(character.id, state.get("selected_outfit_id"))
        return "\n".join(
            [
                "Create a polished visual novel event CG for an independent outing mini event.",
                "Use portrait visual novel event CG framing, 1024x1536 vertical composition, no text, no captions, no UI, no logos.",
                "Show the selected world-map facility as a recognizable place, not a generic background.",
                "Include the selected character naturally in the scene when a character reference is provided.",
                "Use the character face reference image as the highest-priority identity reference when it is provided.",
                "Preserve the exact character face identity, eye shape, facial proportions, hairstyle, hair accessories, body impression, outfit direction, colors, and art style from reference images.",
                *self._closet_service.outfit_prompt_lines(outfit),
                "If the scene asks for a bird's-eye view, use a gentle high-angle or three-quarter overhead composition where the face remains readable. Do not make the character so small or top-down that the face becomes generic.",
                "If a facility reference image is provided, preserve the facility's recognizable architecture, mood, and visual identity.",
                "The image should change pose, expression, camera, lighting, and local staging to match this step.",
                "Keep it romantic and commercially appealing, but avoid explicit nudity, sexual acts, nipples, genitals, fetish framing, transparent clothing emphasis, or hands on breasts/genitals.",
                f"Character: {character.name or ''}",
                f"Character appearance: {character.appearance_summary or ''}",
                f"Character personality: {character.personality or ''}",
                f"Location: {location.name or ''}",
                f"Location type/region: {location.location_type or ''} / {location.region or ''}",
                f"Location description: {location.description or ''}",
                f"Outing mood: {mood}",
                f"Selected choice: {choice_label}",
                f"Final step: {str(is_final).lower()}",
                f"Scene title: {step.get('scene_title') or ''}",
                f"Narration: {step.get('narration') or ''}",
                f"Character line: {step.get('character_line') or ''}",
                f"Location note: {step.get('location_note') or ''}",
            ]
        )

    def _step_reference_paths(self, character, location, *, outfit=None) -> tuple[list[str], list[int]]:
        pairs = []
        seen_asset_ids = set()
        for asset_id in (
            getattr(character, "thumbnail_asset_id", None),
            getattr(character, "base_asset_id", None),
            getattr(outfit, "asset_id", None),
            getattr(location, "image_asset_id", None),
        ):
            if not asset_id:
                continue
            if asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(asset_id)
            asset = self._assets.get(asset_id)
            if asset and asset.file_path and os.path.exists(asset.file_path):
                pairs.append((asset.file_path, asset.id))
        return [path for path, _asset_id in pairs], [asset_id for _path, asset_id in pairs]

    def _send_completion_letter(self, row, character, location, state: dict, final_step: dict) -> None:
        try:
            content = self._build_completion_letter_content(row, character, location, state, final_step)
            body = str(content.get("body") or "").strip()
            if not body:
                return
            self._letters.create(
                {
                    "project_id": row.project_id,
                    "room_id": None,
                    "session_id": None,
                    "recipient_user_id": row.user_id,
                    "sender_character_id": character.id,
                    "subject": str(content.get("subject") or f"{location.name}の帰り道に").strip()[:255],
                    "body": body,
                    "summary": str(content.get("summary") or row.memory_summary or "").strip() or None,
                    "image_asset_id": final_step.get("image_asset_id"),
                    "status": "unread",
                    "trigger_type": "outing_completed",
                    "trigger_reason": f"{location.name}へのおでかけが完了したため。",
                    "generation_state_json": json_util.dumps(
                        {
                            "outing_id": row.id,
                            "location_id": location.id,
                            "character_id": character.id,
                            "memory_title": row.memory_title,
                            "memory_summary": row.memory_summary,
                            "return_url": f"/projects/{row.project_id}/outings",
                            "generated_at": datetime.utcnow().isoformat(),
                        }
                    ),
                }
            )
        except Exception:
            return

    def _create_completion_news(self, row, character, location, state: dict) -> None:
        try:
            self._world_news_service.create_for_outing_completed(row, character, location, state)
        except Exception:
            return

    def _build_completion_letter_content(self, row, character, location, state: dict, final_step: dict) -> dict:
        try:
            prompt = f"""
Return only JSON.
Write a short after-date email from the character to the user.
It should arrive after an independent おでかけ mini event ends.
Keep it intimate but light, not a business report and not a long story.

Required keys:
{{
  "subject": "件名",
  "body": "本文。改行可。160〜360字程度",
  "summary": "一覧表示用の短い要約"
}}

Character name: {character.name or ""}
Nickname: {character.nickname or ""}
First person: {character.first_person or ""}
Second person: {character.second_person or ""}
Personality: {character.personality or ""}
Speech style: {character.speech_style or ""}
Speech sample: {character.speech_sample or ""}
Location: {location.name or ""}
Location description: {location.description or ""}
Outing mood: {row.mood or ""}
Memory title: {row.memory_title or ""}
Memory summary: {row.memory_summary or ""}
Final scene: {json_util.dumps(final_step)}
Selected choices: {json_util.dumps(state.get("selected_choices") or [])}
""".strip()
            result = self._text_ai_client.generate_text(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.75,
                max_tokens=900,
            )
            parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {
                "subject": f"{location.name}、楽しかったね",
                "body": (
                    f"今日は{location.name}に一緒に来てくれてありがとう。\n\n"
                    f"帰ってからも、さっきの景色とか、話したことを少し思い出してた。"
                    f"いつもの時間とは違って、ちゃんと二人で出かけた感じがして、私はけっこう嬉しかった。\n\n"
                    "また、どこか一緒に行こうね。"
                ),
                "summary": f"{location.name}で過ごした時間の余韻が届いています。",
            }

    def _store_generated_outing_image(self, project_id: int, outing_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated outing image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "generated", "outings", str(outing_id))
        os.makedirs(output_dir, exist_ok=True)
        file_name = f"outing_{outing_id}_{uuid.uuid4().hex[:12]}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def _load_state(self, value) -> dict:
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _serialize_character(self, character) -> dict | None:
        if not character:
            return None
        thumbnail = self._assets.get(character.thumbnail_asset_id) if character.thumbnail_asset_id else None
        base_asset = self._assets.get(character.base_asset_id) if character.base_asset_id else None
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "personality": character.personality,
            "thumbnail_asset": self._serialize_asset(thumbnail),
            "base_asset": self._serialize_asset(base_asset),
        }

    def _serialize_location(self, location) -> dict | None:
        if not location:
            return None
        image_asset = self._assets.get(location.image_asset_id) if location.image_asset_id else None
        return {
            "id": location.id,
            "name": location.name,
            "region": location.region,
            "location_type": location.location_type,
            "description": location.description,
            "owner_character_id": location.owner_character_id,
            "image_asset": self._serialize_asset(image_asset),
        }

    def _serialize_asset(self, asset) -> dict | None:
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

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        try:
            if os.path.commonpath([normalized_path, normalized_root]) != normalized_root:
                return None
        except ValueError:
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"
