from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerIntentDefinition:
    id: str
    label: str
    description: str
    tone: str = ""
    intensity: int | None = None
    min_affinity: int = 0
    event_narration: str = ""
    relationship_meaning: str = ""
    accepted_result: str = ""
    boundary_result: str = ""


class LiveChatPlayerIntentService:
    """Normalize structured player input before it reaches conversation logic."""

    _ALLOWED_TYPES = {"message", "action", "emotion"}

    _ACTION_DEFINITIONS = {
        "hold_hands": PlayerIntentDefinition(
            id="hold_hands",
            label="手をつなぐ",
            description="プレイヤーがキャラクターへ穏やかに手を差し出し、手をつなごうとする。",
            tone="gentle",
            intensity=2,
            min_affinity=40,
            event_narration=(
                "プレイヤーは相手の手元へ視線を落とし、急がずに手を差し出す。"
                "触れてもいいか確かめる間を置いてから、そっと手をつなぐ。"
            ),
            relationship_meaning="会話だけでは足りない好意を、穏やかな接触で伝える行動。",
            accepted_result="相手が手を握り返すなら、互いに近づく意思を確認した場面になる。",
            boundary_result="相手がためらうなら、無理に握らず境界線を尊重する場面になる。",
        ),
        "hug_softly": PlayerIntentDefinition(
            id="hug_softly",
            label="そっと抱きしめる",
            description="プレイヤーが相手の反応を大切にしながら、安心させるようにそっと抱きしめる。",
            tone="warm",
            intensity=3,
            min_affinity=60,
            event_narration=(
                "プレイヤーは相手の反応を見ながら、急に引き寄せず、ゆっくり距離を詰める。"
                "逃げられる余地を残したまま、安心させるようにそっと抱きしめる。"
            ),
            relationship_meaning="支配や強引さではなく、今ここで相手を大切にしたい、近くで支えたいという気持ちの表現。",
            accepted_result="相手が受け入れるなら、安心感と親密さが大きく進む。",
            boundary_result="相手が固まる、離れたがる、待ってと言う場合は、境界線を確認する重要な場面になる。",
        ),
        "move_closer": PlayerIntentDefinition(
            id="move_closer",
            label="近くに寄る",
            description="プレイヤーが会話の距離を少し縮めるように、キャラクターの近くへ寄る。",
            tone="soft",
            intensity=2,
            min_affinity=20,
            event_narration="プレイヤーは会話の流れを壊さないよう、相手の表情を見ながら一歩だけ距離を詰める。",
            relationship_meaning="もっと近くで話したいという関心を、控えめな身体距離の変化で示す行動。",
            accepted_result="相手がその距離を許すなら、会話の空気は少し親密になる。",
            boundary_result="相手が身を引くなら、それ以上踏み込まず距離を戻す場面になる。",
        ),
        "sit_next": PlayerIntentDefinition(
            id="sit_next",
            label="隣に座る",
            description="プレイヤーがキャラクターの隣に腰を下ろし、同じ景色を共有する。",
            tone="calm",
            intensity=2,
            min_affinity=20,
            event_narration="プレイヤーは相手の隣に静かに腰を下ろし、同じ景色を見られる距離に並ぶ。",
            relationship_meaning="正面から迫るのではなく、隣にいる安心感を共有したいという行動。",
            accepted_result="相手が隣を許すなら、二人だけの落ち着いた空気が生まれる。",
            boundary_result="相手が距離を置きたがるなら、座る位置を少し離して尊重する場面になる。",
        ),
        "gaze_at": PlayerIntentDefinition(
            id="gaze_at",
            label="見つめる",
            description="プレイヤーが言葉を止めて、キャラクターの表情をまっすぐ見つめる。",
            tone="intimate",
            intensity=2,
            event_narration="プレイヤーは言葉を止め、相手の表情をまっすぐ見つめる。視線だけで、今の感情を確かめようとする。",
            relationship_meaning="相手を異性または大切な存在として意識していることを、沈黙と視線で伝える行動。",
            accepted_result="相手が視線を受け止めるなら、短い沈黙にも意味が生まれる。",
            boundary_result="相手が視線を避けるなら、照れや警戒を尊重して空気をゆるめる場面になる。",
        ),
        "smile_at": PlayerIntentDefinition(
            id="smile_at",
            label="微笑みかける",
            description="プレイヤーが言葉を足さず、やわらかい笑顔で気持ちを伝える。",
            tone="bright",
            intensity=1,
            event_narration="プレイヤーは言葉を重ねず、やわらかく微笑みかける。",
            relationship_meaning="安心してほしい、好意的に受け止めているという軽い合図。",
            accepted_result="相手が笑みを返すなら、空気が少し明るくほどける。",
            boundary_result="相手が反応に困るなら、無理に踏み込まず会話へ戻る。",
        ),
        "cheer": PlayerIntentDefinition(
            id="cheer",
            label="応援する",
            description="プレイヤーがキャラクターを前向きに励まし、背中を押す。",
            tone="encouraging",
            intensity=2,
            event_narration="プレイヤーは相手を否定せず、前に進めるように明るく励ます。",
            relationship_meaning="相手の味方でいたい、力になりたいという支援の行動。",
            accepted_result="相手が受け取るなら、信頼や安心が少し増える。",
            boundary_result="相手が励ましを重く感じるなら、押しつけず聞く姿勢に戻る。",
        ),
        "pat_head": PlayerIntentDefinition(
            id="pat_head",
            label="頭をなでる",
            description="プレイヤーが親しみといたわりを込めて、キャラクターの頭をやさしくなでる。",
            tone="tender",
            intensity=2,
            min_affinity=40,
            event_narration="プレイヤーは相手の反応を確かめながら、親しみといたわりを込めて頭をやさしくなでる。",
            relationship_meaning="守りたい、かわいいと思っている、安心させたいという気持ちを含む接触。",
            accepted_result="相手が受け入れるなら、甘えや照れが出やすい親密な場面になる。",
            boundary_result="相手が子ども扱いを嫌がるなら、すぐに手を止めて尊重する場面になる。",
        ),
        "snuggle": PlayerIntentDefinition(
            id="snuggle",
            label="寄り添う",
            description="プレイヤーがキャラクターのそばに寄り添い、静かに安心感を分け合う。",
            tone="warm",
            intensity=3,
            min_affinity=60,
            event_narration="プレイヤーは言葉を急がず、相手のそばに寄り添って同じ静けさを分け合う。",
            relationship_meaning="恋愛的な熱だけでなく、一緒にいる安心感を確かめる行動。",
            accepted_result="相手が寄り添い返すなら、二人の距離は自然に一段近づく。",
            boundary_result="相手が落ち着かないなら、少し距離を戻して安心を優先する場面になる。",
        ),
        "touch_cheek": PlayerIntentDefinition(
            id="touch_cheek",
            label="頬に触れる",
            description="プレイヤーが相手の反応を確かめながら、そっと頬に触れる。",
            tone="tender",
            intensity=3,
            min_affinity=80,
            event_narration=(
                "プレイヤーは相手の表情を見つめ、拒まれないことを確かめてから、"
                "指先でそっと頬に触れる。"
            ),
            relationship_meaning="かなり近い距離で、相手を異性として大切に見ていることを伝える高緊張の接触。",
            accepted_result="相手が受け入れるなら、照れや沈黙を伴う強い親密イベントになる。",
            boundary_result="相手が戸惑うなら、境界線を試した場面として慎重に扱う。",
        ),
        "interlace_fingers": PlayerIntentDefinition(
            id="interlace_fingers",
            label="指を絡める",
            description="プレイヤーがつないだ手にもう少し気持ちを込めるように、そっと指を絡める。",
            tone="intimate",
            intensity=4,
            min_affinity=80,
            event_narration=(
                "プレイヤーは相手の手をそっと取り、拒まれないことを確かめてから、"
                "指先をゆっくり重ねる。逃げ道を残すように力を込めすぎず、そっと指を絡める。"
            ),
            relationship_meaning="軽い接触ではなく、相手を異性として強く意識し、もっと近い関係になりたいことを静かに伝える行動。",
            accepted_result="相手が受け入れるなら、二人の距離は明確に一段近づき、恋人距離に近い意味を持つ。",
            boundary_result="相手がためらうなら、踏み込みすぎた可能性を認めて手をゆるめる境界線イベントになる。",
        ),
        "wave": PlayerIntentDefinition(
            id="wave",
            label="手を振る",
            description="プレイヤーが明るく手を振って、親しみや合図を送る。",
            tone="bright",
            intensity=1,
            event_narration="プレイヤーは明るく手を振り、親しみや合図を送る。",
            relationship_meaning="重くない好意や注意を向けていることを示す軽い行動。",
            accepted_result="相手が反応するなら、会話の入口が明るくなる。",
            boundary_result="相手が反応しないなら、空気を読んで別の話題へ移る。",
        ),
    }

    _EMOTION_DEFINITIONS = {
        "happy": PlayerIntentDefinition(
            id="happy",
            label="うれしい",
            description="プレイヤーは今の会話や相手の言葉をうれしく感じている。",
            tone="happy",
            intensity=2,
        ),
        "sad": PlayerIntentDefinition(
            id="sad",
            label="悲しい",
            description="プレイヤーは少し悲しい、または寂しい気持ちになっている。",
            tone="sad",
            intensity=2,
        ),
        "embarrassed": PlayerIntentDefinition(
            id="embarrassed",
            label="照れている",
            description="プレイヤーは相手との距離感や言葉に照れている。",
            tone="shy",
            intensity=2,
        ),
        "lonely": PlayerIntentDefinition(
            id="lonely",
            label="寂しい",
            description="プレイヤーは相手にもう少し寄り添ってほしいと感じている。",
            tone="lonely",
            intensity=2,
        ),
        "worried": PlayerIntentDefinition(
            id="worried",
            label="心配",
            description="プレイヤーはキャラクターや状況のことを心配している。",
            tone="worried",
            intensity=2,
        ),
        "relieved": PlayerIntentDefinition(
            id="relieved",
            label="安心",
            description="プレイヤーは相手の言葉や状況に安心している。",
            tone="relieved",
            intensity=2,
        ),
        "grateful": PlayerIntentDefinition(
            id="grateful",
            label="感謝",
            description="プレイヤーはキャラクターへ感謝を伝えたいと思っている。",
            tone="grateful",
            intensity=2,
        ),
    }

    def normalize(self, payload: dict | None, raw_message_text: str = "", context: dict | None = None) -> dict:
        payload = dict(payload or {})
        raw_intent = payload.get("player_intent")
        if not isinstance(raw_intent, dict):
            raw_intent = {}

        intent_type = str(raw_intent.get("type") or payload.get("intent_type") or "message").strip().lower()
        if intent_type not in self._ALLOWED_TYPES:
            intent_type = "message"

        raw_id = str(raw_intent.get("id") or "").strip()
        definition = self._definition(intent_type, raw_id)
        if intent_type in {"action", "emotion"} and definition is None:
            intent_type = "message"

        target_character_id = self._resolve_target_character_id(
            raw_intent.get("target_character_id") or payload.get("target_character_id"),
            context,
        )
        if intent_type == "action" and definition is not None:
            affinity_score = self._affinity_score(context, target_character_id)
            if affinity_score < definition.min_affinity:
                intent_type = "message"

        raw_text = str(raw_message_text or "").strip()
        if intent_type == "message":
            label = "メッセージ"
            intent_id = raw_id if raw_id in {"free_text", "proxy_generated"} else "free_text"
            description = ""
            tone = ""
            intensity = None
            event_narration = ""
            relationship_meaning = ""
            accepted_result = ""
            boundary_result = ""
        else:
            label = definition.label
            intent_id = definition.id
            description = definition.description
            tone = definition.tone
            intensity = self._clamp_int(raw_intent.get("intensity"), default=definition.intensity)
            event_narration = definition.event_narration
            relationship_meaning = definition.relationship_meaning
            accepted_result = definition.accepted_result
            boundary_result = definition.boundary_result

        return {
            "type": intent_type,
            "id": intent_id,
            "label": label,
            "description": description,
            "event_narration": event_narration,
            "relationship_meaning": relationship_meaning,
            "accepted_result": accepted_result,
            "boundary_result": boundary_result,
            "tone": tone,
            "target_character_id": target_character_id,
            "intensity": intensity,
            "raw_message_text": raw_text,
        }

    def render_message_text(self, intent: dict, raw_message_text: str = "") -> str:
        raw = str(raw_message_text or intent.get("raw_message_text") or "").strip()
        intent_type = str(intent.get("type") or "message").strip().lower()
        if intent_type == "action":
            label = str(intent.get("label") or "行動する").strip()
            return raw or f"{label}。"
        if intent_type == "emotion":
            label = str(intent.get("label") or "今の気持ち").strip()
            return raw or f"{label}気持ちを伝える。"
        return raw

    def prompt_text(self, intent: dict, message_text: str) -> str:
        intent_type = str(intent.get("type") or "message").strip().lower()
        if intent_type == "action":
            details = self._details(intent)
            event_lines = [
                f"[Player action] {message_text}{details}",
            ]
            if intent.get("event_narration"):
                event_lines.append(f"Internal event narration: {intent['event_narration']}")
            if intent.get("relationship_meaning"):
                event_lines.append(f"Relationship meaning: {intent['relationship_meaning']}")
            if intent.get("accepted_result"):
                event_lines.append(f"If accepted: {intent['accepted_result']}")
            if intent.get("boundary_result"):
                event_lines.append(f"If resisted or uncomfortable: {intent['boundary_result']}")
            event_lines.append(
                "Treat this as a concrete scene event, not as a vague short utterance. "
                "The character should react to the action, consent/boundary, emotion, and relationship shift."
            )
            return "\n".join(event_lines)
        if intent_type == "emotion":
            details = self._details(intent)
            return f"[Player emotion] {message_text}{details}"
        return message_text

    def _definition(self, intent_type: str, intent_id: str) -> PlayerIntentDefinition | None:
        if intent_type == "action":
            return self._ACTION_DEFINITIONS.get(intent_id)
        if intent_type == "emotion":
            return self._EMOTION_DEFINITIONS.get(intent_id)
        return None

    def _details(self, intent: dict) -> str:
        parts = []
        if intent.get("label"):
            parts.append(f"label={intent['label']}")
        if intent.get("description"):
            parts.append(f"description={intent['description']}")
        if intent.get("relationship_meaning"):
            parts.append(f"relationship_meaning={intent['relationship_meaning']}")
        if intent.get("tone"):
            parts.append(f"tone={intent['tone']}")
        if intent.get("intensity") is not None:
            parts.append(f"intensity={intent['intensity']}")
        if intent.get("target_character_id"):
            parts.append(f"target_character_id={intent['target_character_id']}")
        return f" ({', '.join(parts)})" if parts else ""

    def _affinity_score(self, context: dict | None, target_character_id: int | None) -> int:
        if not isinstance(context, dict):
            return 0
        memories = context.get("character_user_memories") or {}
        candidates = []
        if target_character_id:
            candidates.append(memories.get(str(target_character_id)) or memories.get(target_character_id))
        candidates.extend(memories.values() if isinstance(memories, dict) else [])
        scores = []
        for memory in candidates:
            if not isinstance(memory, dict):
                continue
            parsed = self._to_int(memory.get("affinity_score"))
            if parsed is not None:
                scores.append(parsed)
        return max(scores) if scores else 0

    def _resolve_target_character_id(self, value, context: dict | None) -> int | None:
        parsed = self._to_int(value)
        allowed_ids = self._allowed_character_ids(context)
        if parsed and parsed in allowed_ids:
            return parsed
        if len(allowed_ids) == 1:
            return next(iter(allowed_ids))
        return None

    def _allowed_character_ids(self, context: dict | None) -> set[int]:
        if not isinstance(context, dict):
            return set()
        ids: set[int] = set()
        for key in ("characters", "project_characters"):
            for character in context.get(key) or []:
                character_id = self._to_int((character or {}).get("id"))
                if character_id:
                    ids.add(character_id)
        return ids

    def _clamp_int(self, value, *, default: int | None = None, minimum: int = 1, maximum: int = 5) -> int | None:
        parsed = self._to_int(value)
        if parsed is None:
            return default
        return max(minimum, min(maximum, parsed))

    def _to_int(self, value) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None
