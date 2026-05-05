from app.services.live_chat_conversation_service import is_low_information_player_text


def test_low_information_player_text_detects_repeated_noise():
    assert is_low_information_player_text("あああ")
    assert is_low_information_player_text("いいい")
    assert is_low_information_player_text("aaa")
    assert is_low_information_player_text("ｗｗｗ")
    assert is_low_information_player_text("...")


def test_low_information_player_text_allows_meaningful_short_text():
    assert not is_low_information_player_text("好き")
    assert not is_low_information_player_text("ありがとう")
    assert not is_low_information_player_text("手をつなぐ")
