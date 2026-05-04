import json
import os
import re

from flask import Blueprint, current_app, request, session

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError, json_response
from ...models import User
from ...services.asset_service import AssetService
from ...services.authorization_service import AuthorizationService
from ...services.chat_message_service import ChatMessageService
from ...services.chat_session_service import ChatSessionService
from ...services.character_affinity_reward_service import CharacterAffinityRewardService
from ...services.character_intel_hint_service import CharacterIntelHintService
from ...services.live_chat_room_service import LiveChatRoomService
from ...services.live_chat_service import LiveChatService
from ...services.inventory_service import InventoryService
from ...services.letter_service import LetterService
from ...services.point_billing_service import PointBillingService
from ...services.project_service import ProjectService
from ...services.session_character_affinity_service import SessionCharacterAffinityService
from ...services.session_state_service import SessionStateService
from ...services.user_setting_service import UserSettingService


chat_bp = Blueprint("chat", __name__)
live_chat_service = LiveChatService()
inventory_service = InventoryService()
letter_service = LetterService()
project_service = ProjectService()
asset_service = AssetService()
chat_session_service = ChatSessionService()
chat_message_service = ChatMessageService()
character_affinity_reward_service = CharacterAffinityRewardService()
character_intel_hint_service = CharacterIntelHintService()
live_chat_room_service = LiveChatRoomService()
session_character_affinity_service = SessionCharacterAffinityService()
session_state_service = SessionStateService()
authorization_service = AuthorizationService()
user_setting_service = UserSettingService()
point_billing_service = PointBillingService()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


def _require_project(project_id: int, *, for_chat_create: bool = False, for_manage: bool = False):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if for_manage and not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    if for_chat_create and not authorization_service.can_create_chat_session(user, project):
        raise ForbiddenError()
    if not for_manage and not for_chat_create and not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return project, user


def _require_session(session_id: int, *, include_body: bool = True, for_manage: bool = False):
    user = _current_user()
    chat_session = chat_session_service.get_session(session_id)
    if not chat_session:
        raise NotFoundError()
    project = project_service.get_project(chat_session.project_id)
    if not project:
        raise NotFoundError()
    allowed = (
        authorization_service.can_manage_chat_session(user, chat_session)
        if for_manage
        else authorization_service.can_view_chat_session(user, chat_session, project, include_body=include_body)
    )
    if not allowed:
        raise NotFoundError() if include_body else ForbiddenError()
    return chat_session, project, user


def _require_room(room_id: int, *, for_manage: bool = False, published_only: bool = False):
    user = _current_user()
    room = live_chat_room_service.get_room(room_id)
    if not room:
        raise NotFoundError()
    project = project_service.get_project(room.project_id)
    if not project:
        raise NotFoundError()
    if for_manage:
        if not authorization_service.can_manage_project(user, project):
            raise ForbiddenError()
    else:
        if not authorization_service.can_view_project(user, project):
            raise NotFoundError()
        if published_only and room.status != "published" and not authorization_service.can_manage_project(user, project):
            raise NotFoundError()
    return room, project, user


def _active_character_id_from_context(context: dict | None) -> int | None:
    characters = (context or {}).get("characters") or []
    if not characters:
        return None
    try:
        return int((characters[0] or {}).get("id") or 0) or None
    except (TypeError, ValueError):
        return None


def _affinity_score_from_context(context: dict | None, character_id: int) -> int:
    memory = ((context or {}).get("character_user_memories") or {}).get(str(character_id)) or {}
    try:
        return int(memory.get("affinity_score") or 0)
    except (TypeError, ValueError):
        return 0


def _event_image_prompt(context: dict, character_id: int) -> str:
    character = next(
        (item for item in (context.get("characters") or []) if int(item.get("id") or 0) == int(character_id)),
        {},
    )
    state_json = ((context.get("state") or {}).get("state_json") or {})
    world = context.get("world") or {}
    name = character.get("name") or "キャラクター"
    profile = character.get("memory_profile") or {}
    personality = character.get("personality") or character.get("description") or ""
    likes = ", ".join([str(item) for item in (profile.get("likes") or [])[:8]])
    return "\n".join(
        [
            "好感度100達成の記念イベントCG。",
            f"キャラクター: {name}",
            f"性格・設定: {personality}",
            f"好きなもの: {likes}",
            f"世界観: {world.get('name') or ''} {world.get('overview') or ''}",
            f"現在の場所: {state_json.get('location') or ''}",
            f"現在の背景: {state_json.get('background') or ''}",
            "キャラクターがプレイヤーを深く愛していると一目でわかる、情熱的で幸福感のあるビジュアルノベル風イベント画像。",
            "大量のハートマーク、頬を染めた表情、プレイヤーへまっすぐ向ける愛情、記念スチルらしいドラマチックな光。",
            "露骨な性的描写、裸、局部、文字、ロゴ、透かしは禁止。安全でロマンチックな範囲にする。",
        ]
    )


def _character_from_context(context: dict | None, character_id: int) -> dict:
    return next(
        (item for item in ((context or {}).get("characters") or []) if int(item.get("id") or 0) == int(character_id)),
        {},
    )


def _affinity_100_clear_line(context: dict | None, character_id: int) -> tuple[str, str]:
    character = _character_from_context(context, character_id)
    name = character.get("name") or "キャラクター"
    return (
        name,
        "……やっと、ちゃんと言える。あなたのことが本当に好き。"
        "ここまで私を見つけてくれたこと、絶対に忘れない。これからは、もっと近くで一緒にいさせて。",
    )


def _character_intel_line(selected: dict, *, source_name: str | None = None, target_name: str | None = None) -> str:
    def plain(value: str | None) -> str:
        text = str(value or "").strip()
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"(`{1,3})(.*?)\1", r"\2", text)
        text = re.sub(r"[*_~#>`|-]+", "", text)
        return re.sub(r"\s+", " ", text).strip()

    source = plain(source_name or selected.get("source_character_name") or "私")
    target = plain(target_name or selected.get("target_character_name") or "あの子")
    topic = plain(selected.get("topic") or "")
    hint_text = plain(selected.get("hint_text") or "")
    if hint_text:
        return f"そういえば、{target}のことなんだけど。{hint_text} 覚えておくと、きっと話しやすくなると思う。"
    if topic:
        return f"そういえば、{target}は「{topic}」の話題に反応しやすいみたい。{source}から見ても、そこは大事にしてあげるといいと思う。"
    return f"そういえば、{target}のことで少し話しておきたいことがあるんだ。"


def _extract_outfit_id(result: dict | None) -> int | None:
    if not isinstance(result, dict):
        return None
    state_json = ((result.get("costume_image") or {}).get("state_json") or {})
    for key in ("outfit_id", "closet_outfit_id"):
        try:
            value = int(state_json.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    return None


def _closet_unlocked_for_context(user_id: int, context: dict | None) -> tuple[bool, int | None]:
    character_id = _active_character_id_from_context(context)
    if not character_id:
        return False, None
    reward = character_affinity_reward_service.get_reward(user_id, character_id)
    return bool(reward and reward.event_claimed_at), character_id


@chat_bp.route("/projects/<int:project_id>/chat/rooms", methods=["GET"])
def list_project_chat_rooms(project_id: int):
    project, user = _require_project(project_id)
    include_unpublished = authorization_service.can_manage_project(user, project)
    rooms = live_chat_room_service.list_rooms(project_id, include_unpublished=include_unpublished)
    return json_response(
        live_chat_room_service.serialize_rooms(
            rooms,
            include_counts=True,
            owner_user_id=user.id,
        )
    )


@chat_bp.route("/projects/<int:project_id>/chat/rooms", methods=["POST"])
def create_project_chat_room(project_id: int):
    _, user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        room = live_chat_room_service.create_room(project_id, payload, created_by_user_id=user.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not room:
        raise NotFoundError()
    return json_response(live_chat_room_service.serialize_room(room, include_counts=True), status=201)


@chat_bp.route("/projects/<int:project_id>/chat/rooms/objective-draft", methods=["POST"])
def build_project_chat_room_objective_draft(project_id: int):
    _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        draft = live_chat_room_service.build_objective_draft(project_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(draft)


@chat_bp.route("/projects/<int:project_id>/chat/rooms/description-draft", methods=["POST"])
def build_project_chat_room_description_draft(project_id: int):
    _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        draft = live_chat_room_service.build_description_draft(project_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response(draft)


@chat_bp.route("/projects/<int:project_id>/chat/available-rooms", methods=["GET"])
def list_available_chat_rooms(project_id: int):
    project, user = _require_project(project_id)
    include_unpublished = authorization_service.can_manage_project(user, project)
    rooms = live_chat_room_service.list_rooms(project_id, include_unpublished=include_unpublished)
    return json_response(
        live_chat_room_service.serialize_rooms(
            rooms,
            include_counts=True,
            owner_user_id=user.id,
        )
    )


@chat_bp.route("/chat/rooms/<int:room_id>", methods=["GET"])
def get_chat_room(room_id: int):
    room, _, user = _require_room(room_id)
    return json_response(live_chat_room_service.serialize_room(room, include_counts=True, owner_user_id=user.id))


@chat_bp.route("/chat/rooms/<int:room_id>", methods=["PATCH"])
def update_chat_room(room_id: int):
    _require_room(room_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        room = live_chat_room_service.update_room(room_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not room:
        raise NotFoundError()
    return json_response(live_chat_room_service.serialize_room(room, include_counts=True))


@chat_bp.route("/chat/rooms/<int:room_id>", methods=["DELETE"])
def delete_chat_room(room_id: int):
    _require_room(room_id, for_manage=True)
    if not live_chat_room_service.delete_room(room_id):
        raise NotFoundError()
    return json_response({"room_id": room_id, "deleted": True})


@chat_bp.route("/chat/rooms/<int:room_id>/my-sessions", methods=["GET"])
def list_my_room_sessions(room_id: int):
    room, _, user = _require_room(room_id, published_only=True)
    return json_response(live_chat_service.list_sessions(room.project_id, owner_user_id=user.id, room_id=room.id))


@chat_bp.route("/chat/rooms/<int:room_id>/sessions", methods=["POST"])
def create_room_chat_session(room_id: int):
    room, project, user = _require_room(room_id, published_only=True)
    payload = request.get_json(silent=True) or {}
    try:
        created = live_chat_service.create_session_from_room(room_id, payload, owner_user_id=user.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not created:
        raise NotFoundError()
    try:
        requested_size = str(payload.get("size") or "").strip()
        valid_sizes = {"1024x1024", "1024x1536", "1536x1024"}
        image_payload = {"quality": "low"}
        if requested_size in valid_sizes:
            image_payload["size"] = requested_size
        point_billing_service.ensure_image_generation_balance(user)
        initial_image = live_chat_service.generate_image(
            created["session"]["id"],
            user_setting_service.apply_global_image_generation_settings(image_payload),
        )
        initial_image = point_billing_service.charge_image_generation(
            user,
            project_id=project.id,
            session_id=created["session"]["id"],
            result=initial_image,
            action_type="image_generation_initial",
            detail={"source": "room_session_create", "room_id": room.id, **image_payload},
        )
        created["initial_image"] = initial_image
    except Exception as exc:  # Keep the session usable even when the image API is temporarily unavailable.
        current_app.logger.exception("initial live chat image generation failed")
        created["image_generation_error"] = str(exc)
    return json_response(created, status=201)


@chat_bp.route("/chat/sessions", methods=["GET"])
def list_chat_sessions():
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        raise ValidationError("project_id is required")
    project, user = _require_project(project_id)
    if authorization_service.can_manage_project(user, project):
        include_private_details = authorization_service.is_superuser(user)
        return json_response(
            live_chat_service.list_sessions(
                project_id,
                owner_user_id=None,
                include_private_details=include_private_details,
                detail_owner_user_id=user.id,
            )
        )
    return json_response(live_chat_service.list_sessions(project_id, owner_user_id=user.id))


@chat_bp.route("/chat/sessions", methods=["POST"])
def create_chat_session():
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if not project_id:
        raise ValidationError("project_id is required")
    _, user = _require_project(int(project_id), for_chat_create=True)
    created = live_chat_service.create_session(int(project_id), payload, owner_user_id=user.id)
    if not created:
        raise NotFoundError()
    return json_response(created, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["GET"])
def get_chat_session(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    if not context:
        raise NotFoundError()
    return json_response(context)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["PATCH"])
def update_chat_session(session_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    updated = live_chat_service.update_session(session_id, payload)
    if not updated:
        raise NotFoundError()
    return json_response(updated)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["DELETE"])
def delete_chat_session(session_id: int):
    _require_session(session_id, for_manage=True)
    deleted = chat_session_service.delete_session(session_id)
    if not deleted:
        raise NotFoundError()
    return json_response({"session_id": session_id, "deleted": True})


@chat_bp.route("/chat/sessions/<int:session_id>/messages", methods=["GET"])
def list_chat_messages(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    return json_response(context["messages"], meta={"count": len(context["messages"])})


@chat_bp.route("/chat/sessions/<int:session_id>/messages", methods=["POST"])
def post_chat_message(session_id: int):
    _chat_session, project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    point_billing_service.ensure_chat_message_balance(user)
    result = live_chat_service.post_message(session_id, payload)
    if not result:
        raise NotFoundError()
    result = point_billing_service.charge_chat_message(
        user,
        project_id=project.id,
        session_id=session_id,
        result=result,
        detail={"source": "live_chat", "has_message_text": bool(str(payload.get("message_text") or "").strip())},
    )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/proxy-player-message", methods=["POST"])
def generate_proxy_player_message(session_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    result = live_chat_service.generate_player_proxy_message(session_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/idle-message", methods=["POST"])
def post_idle_character_message(session_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.post_idle_character_message(session_id)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/player-reaction", methods=["POST"])
def analyze_chat_player_reaction(session_id: int):
    _require_session(session_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    result = live_chat_service.analyze_player_reaction(session_id, upload_file)
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/short-story", methods=["POST"])
def generate_chat_short_story(session_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = live_chat_service.generate_short_story(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/short-stories/save", methods=["POST"])
def save_chat_short_story(session_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = live_chat_service.save_short_story(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/messages/<int:message_id>", methods=["DELETE"])
def delete_chat_message(session_id: int, message_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.delete_message(session_id, message_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/choices/<choice_id>/execute", methods=["POST"])
def execute_chat_scene_choice(session_id: int, choice_id: str):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    result = live_chat_service.execute_scene_choice(session_id, choice_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/locations/<int:location_id>/move", methods=["POST"])
def move_chat_session_location(session_id: int, location_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    point_billing_service.ensure_image_generation_balance(user)
    try:
        result = live_chat_service.move_to_location(session_id, location_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    if point_billing_service.result_image_id(result):
        result = point_billing_service.charge_image_generation(
            user,
            project_id=_project.id,
            session_id=session_id,
            result=result,
            action_type="image_generation_location_move",
            detail={"location_id": location_id, "size": payload.get("size"), "quality": payload.get("quality")},
        )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/location-services/<int:service_id>/select", methods=["POST"])
def select_chat_location_service(session_id: int, service_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    point_billing_service.ensure_image_generation_balance(user)
    try:
        result = live_chat_service.select_location_service(session_id, service_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    if point_billing_service.result_image_id(result):
        result = point_billing_service.charge_image_generation(
            user,
            project_id=_project.id,
            session_id=session_id,
            result=result,
            action_type="image_generation_location_service",
            detail={"service_id": service_id, "size": payload.get("size"), "quality": payload.get("quality")},
        )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/photo-mode/shoot", methods=["POST"])
def generate_chat_photo_mode_shoot(session_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload["mode"] = "photo_only"
    context = live_chat_service.get_session_context(session_id)
    character_id = _active_character_id_from_context(context)
    reward = character_affinity_reward_service.get_reward(user.id, character_id) if character_id else None
    if not reward or not reward.event_claimed_at:
        raise ValidationError("撮影モードは好感度100クリア後に開放されます。")
    payload = user_setting_service.apply_image_generation_settings(user.id, payload)
    point_billing_service.ensure_image_generation_balance(user)
    try:
        result = live_chat_service.generate_lccd_photo_shoot(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    result = point_billing_service.charge_image_generation(
        user,
        project_id=_project.id,
        session_id=session_id,
        result=result,
        action_type="image_generation_photo_mode",
        detail={"size": payload.get("size"), "quality": payload.get("quality")},
    )
    return json_response(result, status=201)

def _claim_affinity_reward_payload(chat_session, project, user, context: dict, character_id: int):
    session_id = chat_session.id
    existing = character_affinity_reward_service.get_reward(user.id, character_id)
    if existing and existing.event_claimed_at:
        return (
            {
                "claimed": False,
                "reward": character_affinity_reward_service.serialize_reward(existing, session_id=session_id),
                "event_image": None,
                "letter": None,
                "context": context,
            },
            200,
        )
    event_image = None
    try:
        event_image = live_chat_service.generate_image(
            chat_session.id,
            {
                "image_type": "affinity_100_event",
                "prompt_text": _event_image_prompt(context, character_id),
                "use_existing_prompt": True,
                "size": "1536x1024",
                "quality": "medium",
            },
        )
    except Exception as exc:
        current_app.logger.exception("affinity 100 event image generation failed")
        raise ValidationError(f"好感度100イベント画像の生成に失敗しました: {exc}")
    reward, claimed = character_affinity_reward_service.claim_affinity_100_reward(
        user_id=user.id,
        project_id=project.id,
        character_id=character_id,
        event_image_id=(event_image or {}).get("id"),
    )
    letter = None
    clear_message = None
    if claimed:
        speaker_name, message_text = _affinity_100_clear_line(context, character_id)
        clear_message = chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": speaker_name,
                "message_text": message_text,
                "message_role": "assistant",
                "state_snapshot_json": {
                    "affinity_100_reward": True,
                    "character_id": character_id,
                    "event_image_id": (event_image or {}).get("id"),
                },
            },
        )
        letter = letter_service.create_affinity_100_letter(
            chat_session,
            context,
            character_id,
            (event_image or {}).get("asset_id"),
        )
    return (
        {
            "claimed": claimed,
            "reward": character_affinity_reward_service.serialize_reward(reward, session_id=session_id),
            "event_image": event_image,
            "letter": letter,
            "message": live_chat_service._serialize_message(clear_message) if clear_message else None,
            "context": live_chat_service.get_session_context(session_id),
        },
        201 if claimed else 200,
    )


@chat_bp.route("/chat/sessions/<int:session_id>/affinity-rewards/<int:character_id>/claim", methods=["POST"])
def claim_chat_affinity_reward(session_id: int, character_id: int):
    chat_session, project, user = _require_session(session_id, for_manage=True)
    context = live_chat_service.get_session_context(session_id)
    active_ids = {int(item.get("id") or 0) for item in (context or {}).get("characters") or []}
    if int(character_id) not in active_ids:
        raise ValidationError("このセッションのキャラクターではありません。")
    if _affinity_score_from_context(context, character_id) < 100:
        raise ValidationError("好感度100に到達していません。")
    payload, status = _claim_affinity_reward_payload(chat_session, project, user, context, character_id)
    return json_response(payload, status=status)


@chat_bp.route("/chat/sessions/<int:session_id>/debug/affinity-clear", methods=["POST"])
def debug_clear_chat_affinity(session_id: int):
    debug_password = (os.getenv("DEBUG") or "").strip()
    if not debug_password:
        raise NotFoundError()
    payload = request.get_json(silent=True) or {}
    if str(payload.get("password") or "") != debug_password:
        raise ForbiddenError("DEBUG password is invalid.")
    chat_session, project, user = _require_session(session_id, for_manage=True)
    context = live_chat_service.get_session_context(session_id)
    active_ids = {int(item.get("id") or 0) for item in (context or {}).get("characters") or []}
    character_id = int(payload.get("character_id") or _active_character_id_from_context(context) or 0)
    if character_id not in active_ids:
        raise ValidationError("このセッションのキャラクターではありません。")
    session_character_affinity_service.force_affinity_100(
        session_id=session_id,
        user_id=user.id,
        project_id=project.id,
        character_id=character_id,
        reason="debug shortcut clear",
    )
    context = live_chat_service.get_session_context(session_id)
    response_payload, status = _claim_affinity_reward_payload(chat_session, project, user, context, character_id)
    response_payload["debug"] = {"affinity_forced": True, "character_id": character_id}
    return json_response(response_payload, status=status)

@chat_bp.route("/chat/sessions/<int:session_id>/state", methods=["GET"])
def get_chat_state(session_id: int):
    _require_session(session_id)
    state = session_state_service.get_state(session_id)
    return json_response(live_chat_service._serialize_state(state))


@chat_bp.route("/chat/sessions/<int:session_id>/images", methods=["GET"])
def list_chat_images(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    return json_response(context["images"], meta={"count": len(context["images"])})


@chat_bp.route("/chat/sessions/<int:session_id>/costumes", methods=["GET"])
def list_chat_costumes(session_id: int):
    _require_session(session_id)
    costumes = live_chat_service.list_costumes(session_id)
    return json_response(costumes, meta={"count": len(costumes)})


@chat_bp.route("/chat/sessions/<int:session_id>/closet-outfits", methods=["GET"])
def list_chat_closet_outfits(session_id: int):
    _chat_session, _project, user = _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    unlocked, character_id = _closet_unlocked_for_context(user.id, context)
    if not unlocked:
        return json_response(
            {
                "outfits": [],
                "locked": True,
                "unlock_label": "好感度100で開放",
                "character_id": character_id,
            }
        )
    result = live_chat_service.list_closet_outfits(session_id)
    result["locked"] = False
    result["unlock_label"] = ""
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/closet-outfits/<int:outfit_id>/select", methods=["POST"])
def select_chat_closet_outfit(session_id: int, outfit_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    context = live_chat_service.get_session_context(session_id)
    unlocked, _character_id = _closet_unlocked_for_context(user.id, context)
    if not unlocked:
        raise ValidationError("クローゼット選択は好感度100で開放されます。")
    result = live_chat_service.select_closet_outfit(session_id, outfit_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/costumes/<int:image_id>/select", methods=["POST"])
def select_chat_costume(session_id: int, image_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    context = live_chat_service.get_session_context(session_id)
    unlocked, _character_id = _closet_unlocked_for_context(user.id, context)
    if not unlocked:
        raise ValidationError("衣装の選択は好感度100で開放されます。")
    result = live_chat_service.select_costume(session_id, image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/costumes/<int:image_id>", methods=["DELETE"])
def delete_chat_costume(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.delete_costume(session_id, image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/images/generate", methods=["POST"])
def generate_chat_image(session_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    point_billing_service.ensure_image_generation_balance(user)
    try:
        result = live_chat_service.generate_image(session_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not result:
        raise NotFoundError()
    result = point_billing_service.charge_image_generation(
        user,
        project_id=_project.id,
        session_id=session_id,
        result=result,
        action_type="image_generation",
        detail={"size": payload.get("size"), "quality": payload.get("quality"), "image_type": payload.get("image_type")},
    )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/images/upload", methods=["POST"])
def upload_chat_image(session_id: int):
    chat_session, project, _ = _require_session(session_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    asset = asset_service.create_asset(
        project.id,
        {
            "asset_type": "uploaded_live_chat_image",
            "upload_file": upload_file,
            "metadata_json": '{"source":"manual_upload","mode":"live_chat"}',
        },
    )
    state_json = request.form.get("state_json")
    if state_json:
        try:
            state_json = json.loads(state_json)
        except ValueError:
            pass
    result = live_chat_service.register_uploaded_image(
        chat_session.id,
        asset.id,
        {
            "image_type": request.form.get("image_type") or "live_scene",
            "prompt_text": request.form.get("prompt_text") or None,
            "quality": request.form.get("quality") or "external",
            "size": request.form.get("size") or "uploaded",
            "state_json": state_json,
            "is_selected": str(request.form.get("is_selected", "1")).lower() in {"1", "true", "yes", "on"},
        },
    )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/gifts/upload", methods=["POST"])
def upload_chat_gift(session_id: int):
    chat_session, project, _ = _require_session(session_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    asset = asset_service.create_asset(
        project.id,
        {
            "asset_type": "uploaded_live_chat_gift",
            "upload_file": upload_file,
            "metadata_json": '{"source":"gift_upload","mode":"live_chat"}',
        },
    )
    result = live_chat_service.upload_gift(
        chat_session.id,
        asset.id,
        {
            "character_id": request.form.get("character_id", type=int),
            "message_text": request.form.get("message_text") or None,
        },
    )
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/projects/<int:project_id>/inventory", methods=["GET"])
def list_project_inventory(project_id: int):
    _, user = _require_project(project_id)
    return json_response({"items": inventory_service.list_items(user_id=user.id, project_id=project_id)})


@chat_bp.route("/projects/<int:project_id>/inventory/generate", methods=["POST"])
def generate_project_inventory_item(project_id: int):
    _, user = _require_project(project_id)
    payload = request.get_json(silent=True) or {}
    point_billing_service.ensure_image_generation_balance(user)
    try:
        item = inventory_service.generate_item(
            user_id=user.id,
            project_id=project_id,
            payload=user_setting_service.apply_global_image_generation_settings(payload),
        )
    except ValueError as exc:
        raise ValidationError(str(exc))
    result = {"item": item}
    result = point_billing_service.charge_image_generation(
        user,
        project_id=project_id,
        session_id=int(payload.get("session_id") or 0),
        result=result,
        action_type="inventory_item_generation",
        detail={"inventory_item_id": item.get("id") if item else None},
    )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/inventory/<int:item_id>/give", methods=["POST"])
def give_inventory_item(session_id: int, item_id: int):
    chat_session, project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    item = inventory_service.get_available_item(
        item_id=item_id,
        user_id=user.id,
        project_id=project.id,
    )
    if not item:
        raise NotFoundError()
    tags = inventory_service.serialize_item(item).get("tags") if item else []
    result = live_chat_service.upload_gift(
        chat_session.id,
        item.asset_id,
        {
            "character_id": payload.get("character_id") or item.target_character_id,
            "message_text": payload.get("message_text") or f"{item.name}を渡した。",
            "recognized_label": item.name,
            "recognized_tags": tags,
            "inventory_item_id": item.id,
        },
    )
    if not result:
        raise NotFoundError()
    used_item = inventory_service.mark_used(
        item_id=item.id,
        user_id=user.id,
        session_id=chat_session.id,
        character_id=payload.get("character_id") or item.target_character_id,
    )
    result["inventory_item"] = used_item
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/intel/reveal", methods=["POST"])
def reveal_character_intel_hint(session_id: int):
    chat_session, project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    context = live_chat_service.get_session_context(chat_session.id)
    available = ((context.get("character_intel") or {}).get("available_hints") or [])
    try:
        source_character_id = int(payload.get("source_character_id") or 0)
        target_character_id = int(payload.get("target_character_id") or 0)
    except (TypeError, ValueError):
        raise ValidationError("invalid character intel request")
    topic = str(payload.get("topic") or "").strip()
    selected = None
    for hint in available:
        if int(hint.get("source_character_id") or 0) != source_character_id:
            continue
        if int(hint.get("target_character_id") or 0) != target_character_id:
            continue
        if str(hint.get("topic") or "").strip() != topic:
            continue
        selected = hint
        break
    if not selected:
        raise NotFoundError()
    row = character_intel_hint_service.upsert_revealed_hint(
        user_id=int(user.id),
        project_id=int(project.id),
        target_character_id=target_character_id,
        source_character_id=source_character_id,
        topic=topic,
        hint_text=str(selected.get("hint_text") or "").strip(),
        reveal_threshold=int(selected.get("reveal_threshold") or 40),
    )
    if not row:
        raise ValidationError("character intel hint could not be revealed")
    characters = {int(item.get("id") or 0): item.get("name") for item in context.get("project_characters") or []}
    hint = character_intel_hint_service.serialize_hint(
        row,
        target_name=characters.get(target_character_id),
        source_name=characters.get(source_character_id),
    )
    message = chat_message_service.create_message(
        chat_session.id,
        {
            "sender_type": "character",
            "speaker_name": hint.get("source_character_name") or selected.get("source_character_name") or "Character",
            "message_text": _character_intel_line(
                selected,
                source_name=hint.get("source_character_name"),
                target_name=hint.get("target_character_name"),
            ),
            "message_role": "assistant",
            "state_snapshot_json": {
                "character_intel_reveal": True,
                "hint_id": row.id,
                "source_character_id": source_character_id,
                "target_character_id": target_character_id,
                "topic": topic,
            },
        },
    )
    updated_context = live_chat_service.get_session_context(chat_session.id)
    live_chat_service._update_session_memory(chat_session.id, updated_context)
    updated_context = live_chat_service.get_session_context(chat_session.id)
    live_chat_service._update_conversation_evaluation(chat_session.id, updated_context)
    updated_context = live_chat_service.get_session_context(chat_session.id)
    return json_response(
        {
            "hint": hint,
            "message": live_chat_service._serialize_message(message),
            "context": updated_context,
        }
    )


@chat_bp.route("/chat/sessions/<int:session_id>/images/<int:image_id>/select", methods=["POST"])
def select_chat_image(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.select_image(image_id, session_id=session_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/images/<int:image_id>/reference", methods=["POST"])
def set_chat_image_reference(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    is_reference = str(payload.get("is_reference", "true")).lower() in {"1", "true", "yes", "on"}
    result = live_chat_service.set_reference_image(session_id, image_id, is_reference)
    if not result:
        raise NotFoundError()
    return json_response(result)


