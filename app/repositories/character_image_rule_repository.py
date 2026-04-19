from ..extensions import db
from ..models.character_image_rule import CharacterImageRule


class CharacterImageRuleRepository:
    def get_by_character_id(self, character_id: int):
        return CharacterImageRule.query.filter(CharacterImageRule.character_id == character_id).first()

    def upsert(self, character_id: int, payload: dict):
        image_rule = self.get_by_character_id(character_id)
        if image_rule is None:
            image_rule = CharacterImageRule(character_id=character_id)
            db.session.add(image_rule)

        for field in (
            "hair_rule",
            "face_rule",
            "ear_rule",
            "accessory_rule",
            "outfit_rule",
            "style_rule",
            "negative_rule",
            "default_quality",
            "default_size",
            "prompt_prefix",
            "prompt_suffix",
        ):
            if field in payload:
                setattr(image_rule, field, payload[field])

        db.session.commit()
        return image_rule
