from flask import Blueprint, request

from ...api import NotFoundError, ValidationError, json_response
from ...services.user_setting_service import UserSettingService
from ...services.x_observation_reply_service import XObservationReplyService
from ...services.x_publishing_service import XPublishingService
from ...services.x_timeline_digest_service import XTimelineDigestService
from ..access import require_project_manage, require_project_view


observations_bp = Blueprint("observations", __name__)
timeline_service = XTimelineDigestService()
user_setting_service = UserSettingService()
x_publishing_service = XPublishingService()
x_observation_reply_service = XObservationReplyService()


@observations_bp.route("/projects/<int:project_id>/observations/x/recent", methods=["GET"])
def recent_x_posts(project_id: int):
    require_project_view(project_id)
    hours = request.args.get("hours", default=24, type=int)
    max_users = request.args.get("max_users", default=50, type=int)
    user_sample_pool = request.args.get("user_sample_pool", default=1000, type=int)
    tweets_per_user = request.args.get("tweets_per_user", default=1, type=int)
    source = request.args.get("source") or "home_timeline"
    randomize_users = str(source or "").lower() not in {"home", "home_timeline", "timeline"}
    posts = timeline_service.collect_recent_posts(
        hours=hours,
        max_users=max_users,
        user_sample_pool=user_sample_pool,
        tweets_per_user=tweets_per_user,
        include_replies=False,
        include_reposts=False,
        source=source,
        randomize_users=randomize_users,
    )
    items = [timeline_service.serialize_post(post) for post in posts]
    x_observation_reply_service.apply_to_posts(project_id, items)
    return json_response(
        {
            "items": items,
            "filters": {
                "hours": hours,
                "max_users": max_users,
                "user_sample_pool": user_sample_pool,
                "tweets_per_user": tweets_per_user,
                "source": source,
                "randomize_users": randomize_users,
                "include_replies": False,
                "include_reposts": False,
            },
        }
    )


@observations_bp.route("/projects/<int:project_id>/observations/x/posts/<tweet_id>", methods=["GET"])
def x_post_detail(project_id: int, tweet_id: str):
    require_project_view(project_id)
    try:
        post = timeline_service.get_post_detail(tweet_id, project_id=project_id)
    except RuntimeError as exc:
        raise NotFoundError(str(exc))
    data = timeline_service.serialize_post(post)
    reply = x_observation_reply_service.latest_by_tweet_id(project_id, tweet_id)
    data["observation_reply"] = reply
    data["is_replied"] = bool(reply)
    return json_response(data)


@observations_bp.route("/projects/<int:project_id>/observations/x/posts/<tweet_id>/comment", methods=["POST"])
def generate_x_comment(project_id: int, tweet_id: str):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    text_options = user_setting_service.apply_global_text_generation_settings(payload)
    try:
        result = timeline_service.generate_reply_for_post(
            project_id=project_id,
            tweet_id=tweet_id,
            character_id=int(payload.get("character_id") or 0),
            model=text_options.get("model"),
        )
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    return json_response(result)


@observations_bp.route("/projects/<int:project_id>/observations/x/posts/<tweet_id>/reply", methods=["POST"])
def publish_x_reply(project_id: int, tweet_id: str):
    _project, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    character_id = payload.get("character_id")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    try:
        if not text:
            raise ValueError("reply text is required")
        result = x_publishing_service.publish_reply(tweet_id, text)
        reply = x_observation_reply_service.create_from_target_data(
            project_id=project_id,
            target=target,
            tweet_id=tweet_id,
            reply_text=text,
            published=result,
            replied_by_user_id=user.id,
            character_id=int(character_id) if character_id else None,
        )
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    result["observation_reply"] = x_observation_reply_service.serialize(reply)
    return json_response(result, status=201)


@observations_bp.route("/projects/<int:project_id>/observations/x/posts/<tweet_id>/mark-replied", methods=["POST"])
def mark_x_reply_done(project_id: int, tweet_id: str):
    _project, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    character_id = payload.get("character_id")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    try:
        if not text:
            raise ValueError("reply text is required")
        result = {
            "x_post_id": "",
            "in_reply_to_tweet_id": str(tweet_id),
            "text": text,
            "url": "",
            "manual": True,
        }
        reply = x_observation_reply_service.create_from_target_data(
            project_id=project_id,
            target=target,
            tweet_id=tweet_id,
            reply_text=text,
            published=result,
            replied_by_user_id=user.id,
            character_id=int(character_id) if character_id else None,
        )
    except ValueError as exc:
        raise ValidationError(str(exc))
    result["observation_reply"] = x_observation_reply_service.serialize(reply)
    return json_response(result, status=201)


@observations_bp.route("/projects/<int:project_id>/observations/x/follow-cleanup/candidates", methods=["GET"])
def x_follow_cleanup_candidates(project_id: int):
    require_project_manage(project_id)
    max_users = request.args.get("max_users", default=5000, type=int)
    try:
        candidates = timeline_service.list_non_mutual_following(max_users=max_users)
    except RuntimeError as exc:
        raise ValidationError(str(exc))
    return json_response(
        {
            "items": [timeline_service.serialize_follow_user(user) for user in candidates],
            "count": len(candidates),
            "max_users": max_users,
        }
    )


@observations_bp.route("/projects/<int:project_id>/observations/x/follow-cleanup/unfollow", methods=["POST"])
def x_follow_cleanup_unfollow(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids") if isinstance(payload.get("user_ids"), list) else []
    try:
        results = timeline_service.unfollow_users(user_ids)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    return json_response(
        {
            "results": results,
            "success_count": len([item for item in results if item.get("ok")]),
            "failure_count": len([item for item in results if not item.get("ok")]),
        }
    )
