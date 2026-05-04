from ..extensions import db

from .asset import Asset
from .chat_session_objective_note import ChatSessionObjectiveNote
from .chat_message import ChatMessage
from .chat_session import ChatSession
from .character import Character
from .character_memory_note import CharacterMemoryNote
from .character_memory_summary import CharacterMemorySummary
from .character_intel_hint import CharacterIntelHint
from .character_affinity_reward import CharacterAffinityReward
from .character_user_memory import CharacterUserMemory
from .character_feed_profile import CharacterFeedProfile
from .character_outfit import CharacterOutfit
from .cinema_novel import CinemaNovel
from .cinema_novel_chapter import CinemaNovelChapter
from .cinema_novel_character_impression import CinemaNovelCharacterImpression
from .cinema_novel_lore_entry import CinemaNovelLoreEntry
from .cinema_novel_progress import CinemaNovelProgress
from .cinema_novel_review import CinemaNovelReview
from .feed_like import FeedLike
from .feed_post import FeedPost
from .inventory_item import InventoryItem
from .live_chat_room import LiveChatRoom
from .letter import Letter
from .project import Project
from .point_transaction import PointTransaction
from .outing_session import OutingSession
from .session_image import SessionImage
from .session_gift_event import SessionGiftEvent
from .session_state import SessionState
from .session_character_affinity import SessionCharacterAffinity
from .story import Story
from .story_image import StoryImage
from .story_message import StoryMessage
from .story_roll_log import StoryRollLog
from .story_session import StorySession
from .story_session_state import StorySessionState
from .usage_log import UsageLog
from .user import User
from .user_setting import UserSetting
from .world import World
from .world_location import WorldLocation
from .world_location_service import WorldLocationServiceItem
from .world_map_image import WorldMapImage
from .world_news_item import WorldNewsItem

__all__ = [
    "db",
    "Asset",
    "ChatSessionObjectiveNote",
    "ChatMessage",
    "ChatSession",
    "Character",
    "CharacterMemoryNote",
    "CharacterMemorySummary",
    "CharacterIntelHint",
    "CharacterAffinityReward",
    "CharacterUserMemory",
    "CharacterFeedProfile",
    "CharacterOutfit",
    "CinemaNovel",
    "CinemaNovelChapter",
    "CinemaNovelCharacterImpression",
    "CinemaNovelLoreEntry",
    "CinemaNovelProgress",
    "CinemaNovelReview",
    "FeedLike",
    "FeedPost",
    "InventoryItem",
    "LiveChatRoom",
    "Letter",
    "OutingSession",
    "Project",
    "PointTransaction",
    "SessionImage",
    "SessionGiftEvent",
    "SessionState",
    "SessionCharacterAffinity",
    "Story",
    "StoryImage",
    "StoryMessage",
    "StoryRollLog",
    "StorySession",
    "StorySessionState",
    "UsageLog",
    "User",
    "UserSetting",
    "World",
    "WorldLocation",
    "WorldLocationServiceItem",
    "WorldMapImage",
    "WorldNewsItem",
]
