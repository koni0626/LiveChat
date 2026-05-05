ALTER TABLE user_setting
ADD COLUMN mobile_default_size VARCHAR(20) NOT NULL DEFAULT '1024x1536';

UPDATE user_setting
SET mobile_default_size = '1024x1536'
WHERE mobile_default_size IS NULL OR mobile_default_size = '';

UPDATE user_setting
SET prefer_portrait_on_mobile = 1;
