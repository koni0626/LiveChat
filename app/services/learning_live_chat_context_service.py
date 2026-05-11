from __future__ import annotations

from .live_chat_context_service import LiveChatContextService


class LearningLiveChatContextService(LiveChatContextService):
    """Learning-mode context builder.

    This intentionally strips romance/world-facility context before prompts see it.
    """

    def _create_opening_message(self, session, context: dict):
        context = self._filter_learning_context(context)
        characters = context.get("characters") or []
        speaker_name = (characters[0] or {}).get("name") if characters else None
        speaker_name = speaker_name or "先生"
        objective = (((context.get("room") or {}).get("conversation_objective")) or "").strip()
        topic = objective.splitlines()[0].strip("#- * ") if objective else "今日のテーマ"
        message = (
            f"{topic}から始めましょう。まず要点を黒板に整理して、"
            "ひとつずつ確認していきます。わからないところはその場で止めてください。"
        )
        self._chat_message_service.create_message(
            session.id,
            {
                "sender_type": "character",
                "speaker_name": speaker_name,
                "message_text": message,
                "message_role": "assistant",
                "state_snapshot_json": {"learning_opening": True},
            },
        )

    def _world_map_context(self, project_id: int):
        return {"locations": [], "prompt_context": ""}

    def _world_activity_context(self, project_id: int, user_id: int, characters: list[dict] | None = None):
        return {"news": [], "feed_posts": [], "outings": [], "prompt_context": ""}

    def get_session_context(self, session_id: int):
        context = super().get_session_context(session_id)
        return self._filter_learning_context(context)

    def _filter_learning_context(self, context: dict | None):
        if not context:
            return context
        filtered = dict(context)
        filtered["live_chat_genre"] = "learning"
        filtered["world_map"] = {"locations": [], "prompt_context": ""}
        filtered["world_activity"] = {"news": [], "feed_posts": [], "outings": [], "prompt_context": ""}
        filtered["character_user_memories"] = {}
        filtered["affinity_rewards"] = {}
        filtered["character_intel"] = {"available_hints": [], "learned_hints_for_active_targets": []}
        filtered["project_characters"] = []
        filtered["session_objective_notes"] = []
        filtered["session_objective_prompt_block"] = ""
        filtered["player_profile_prompt_block"] = ""
        return filtered
