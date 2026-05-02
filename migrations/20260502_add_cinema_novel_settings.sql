ALTER TABLE user_setting ADD COLUMN cinema_novel_text_model VARCHAR(100) NOT NULL DEFAULT 'gpt-5.5';
ALTER TABLE user_setting ADD COLUMN cinema_novel_image_ai_provider VARCHAR(20) NOT NULL DEFAULT 'openai';
ALTER TABLE user_setting ADD COLUMN cinema_novel_image_ai_model VARCHAR(100) NOT NULL DEFAULT 'gpt-image-2';
ALTER TABLE user_setting ADD COLUMN cinema_novel_default_quality VARCHAR(20) NOT NULL DEFAULT 'high';
ALTER TABLE user_setting ADD COLUMN cinema_novel_default_size VARCHAR(20) NOT NULL DEFAULT '1536x1024';
ALTER TABLE user_setting ADD COLUMN cinema_novel_chapter_target_chars INTEGER NOT NULL DEFAULT 8000;
