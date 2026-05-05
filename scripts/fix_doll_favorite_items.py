from app import create_app
from app.extensions import db
from app.models import Character
from app.utils import json_util


ITEMS = [
    "金箔入りの高級チョコ",
    "希少ワイン",
    "相場分析レポート",
    "宝石つきの万年筆",
    "上質な香水",
    "高級レストランの招待券",
]


app = create_app()
with app.app_context():
    row = Character.query.filter_by(name="ドル").first()
    if not row:
        raise SystemExit("ドルが見つかりません")
    row.favorite_items_json = json_util.dumps(ITEMS)
    db.session.add(row)
    db.session.commit()
    print(f"updated character_id={row.id} favorite_items_json={row.favorite_items_json}")
