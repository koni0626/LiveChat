ALTER TABLE character ADD COLUMN introduction_text TEXT;
ALTER TABLE character ADD COLUMN bromide_asset_id INTEGER REFERENCES asset(id);
