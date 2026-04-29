from ..extensions import db
from ..models.story_image import StoryImage
from ..models.story_session import StorySession


class StoryImageRepository:
    def list_by_session(self, session_id: int):
        return (
            StoryImage.query.filter(StoryImage.session_id == session_id)
            .order_by(StoryImage.created_at.desc(), StoryImage.id.desc())
            .all()
        )

    def list_costumes_for_session_library(self, session_id: int):
        session = StorySession.query.get(session_id)
        if not session:
            return []
        return (
            StoryImage.query.join(StorySession, StorySession.id == StoryImage.session_id)
            .filter(
                StoryImage.visual_type.in_(("costume_initial", "costume_reference")),
                StorySession.story_id == session.story_id,
                StorySession.owner_user_id == session.owner_user_id,
            )
            .order_by((StoryImage.session_id == session_id).desc(), StoryImage.id.desc())
            .all()
        )

    def get(self, image_id: int):
        return StoryImage.query.get(image_id)

    def create(self, payload: dict):
        row = StoryImage(
            session_id=payload["session_id"],
            asset_id=payload["asset_id"],
            source_message_id=payload.get("source_message_id"),
            visual_type=payload.get("visual_type") or "scene",
            subject=payload.get("subject"),
            prompt_text=payload.get("prompt_text"),
            reference_asset_ids_json=payload.get("reference_asset_ids_json"),
            metadata_json=payload.get("metadata_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def delete_costume(self, session_id: int, image_id: int):
        row = StoryImage.query.get(image_id)
        if not row or row.session_id != session_id or row.visual_type != "costume_reference":
            return None
        deleted_id = row.id
        db.session.delete(row)
        db.session.commit()
        return {"deleted_id": deleted_id}
