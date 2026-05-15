from types import SimpleNamespace

from app.services.blog_service import BlogService


class _Repo:
    def __init__(self):
        self.created = []

    def create_post(self, payload):
        post = SimpleNamespace(id=len(self.created) + 1, **payload)
        self.created.append(post)
        return post


class _Characters:
    def __init__(self, character):
        self.character = character

    def get_character(self, character_id):
        return self.character if character_id == self.character.id else None


class _TextAI:
    def __init__(self):
        self.last_prompt = ""
        self.last_kwargs = {}

    def generate_text(self, prompt, **kwargs):
        self.last_prompt = prompt
        self.last_kwargs = dict(kwargs)
        return {
            "model": "test-model",
            "text": "# Today\n**A little** mistake turned into a decent story。The next sentence wraps。\nThe next paragraph is easier to read。",
        }


class _Projects:
    def get_project(self, project_id):
        return SimpleNamespace(id=project_id, title="Laplace", summary="City")


class _Worlds:
    def get_world(self, project_id):
        return SimpleNamespace(project_id=project_id, overview="A strange city", tone="Light")


def test_generate_post_creates_plain_text_article():
    character = SimpleNamespace(
        id=3,
        project_id=1,
        name="Noa",
        nickname=None,
        personality="",
        speech_style="",
        character_summary="",
    )
    repo = _Repo()
    text_ai = _TextAI()
    service = BlogService(
        repository=repo,
        character_service=_Characters(character),
        project_service=_Projects(),
        world_service=_Worlds(),
        text_ai_client=text_ai,
    )

    post = service.generate_post(
        project_id=1,
        user_id=2,
        payload={"character_id": 3, "theme": "update", "instruction": "make it funny"},
    )

    assert post.theme == "update"
    assert post.status == "draft"
    assert "#" not in post.body
    assert "**" not in post.body
    assert "Today" in post.body
    assert "story。\nThe next sentence" in post.body
    assert "\n\n" in post.body
    assert text_ai.last_kwargs["max_tokens"] == 5000
    assert text_ai.last_kwargs["model"] is None
    assert "900" in text_ai.last_prompt
    assert "短くまとめない" in text_ai.last_prompt


def test_generate_post_uses_configured_text_model():
    character = SimpleNamespace(
        id=3,
        project_id=1,
        name="Noa",
        nickname=None,
        personality="",
        speech_style="",
        character_summary="",
    )
    text_ai = _TextAI()
    service = BlogService(
        repository=_Repo(),
        character_service=_Characters(character),
        project_service=_Projects(),
        world_service=_Worlds(),
        text_ai_client=text_ai,
    )

    service.generate_post(
        project_id=1,
        user_id=2,
        payload={"character_id": 3, "theme": "update", "model": "gpt-5.5"},
    )

    assert text_ai.last_kwargs["model"] == "gpt-5.5"
