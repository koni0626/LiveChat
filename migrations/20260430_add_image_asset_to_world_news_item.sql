ALTER TABLE world_news_item ADD COLUMN image_asset_id INTEGER REFERENCES asset(id);
CREATE INDEX IF NOT EXISTS ix_world_news_item_image_asset_id ON world_news_item(image_asset_id);
