from __future__ import annotations

from app import create_app
from app.extensions import db
from app.models import Character, WorldLocation
from app.utils import json_util


PROJECT_ID = 1


def loc(name, region, location_type, tags, description, image_prompt, owner_name=None):
    return {
        "name": name,
        "region": region,
        "location_type": location_type,
        "tags": tags,
        "description": description,
        "image_prompt": image_prompt,
        "owner_name": owner_name,
    }


LOCATIONS = [
    loc("ネオン展望レストラン", "デート街区", "飲食施設", ["デート", "夜景", "食事"], "ラプラスシティの高層階にある展望レストラン。窓際席から都市のネオンと空中交通の光跡が見える。料理を選ぶ、夜景を眺める、少し背伸びした会話をするなど、距離を縮めやすい。", "未来都市の高層展望レストラン、青と金のネオン夜景、窓際の二人席、上品なテーブル、visual novel background"),
    loc("深夜営業のサイバー屋台街", "デート街区", "飲食施設", ["デート", "屋台", "笑い"], "深夜でも明るいサイバー屋台街。怪しい串焼き、光るスープ、失敗寸前の実験料理が並び、注文するだけで会話のきっかけになる。気取らないデートやツッコミの多い場面向き。", "cyberpunk night food stall street, glowing signs, steam, crowded futuristic alley, visual novel background"),
    loc("旧人類風レトロ喫茶", "旧人類文化区", "飲食施設", ["デート", "喫茶", "旧人類"], "旧人類の喫茶店を再現した静かな店。紙のメニュー、少し硬いソファ、古い音楽、手書き風の伝票がある。昔の恋愛や価値観の話に自然につなげられる。", "retro Japanese cafe recreated in futuristic city, warm lamps, paper menus, quiet booths, visual novel background"),
    loc("高級スイーツラウンジ", "デート街区", "飲食施設", ["デート", "スイーツ", "贅沢"], "宝石のような限定スイーツを出すラウンジ。甘いものの好み、食べさせ合い、限定メニューの取り合いなど、軽い恋愛会話に向いている。", "luxury dessert lounge, jewel-like cakes, neon city view, elegant table, visual novel background"),
    loc("回転惑星料理店", "娯楽飲食区", "飲食施設", ["デート", "食事", "コメディ"], "小さな惑星型の料理皿がレーンを回る奇妙な店。何が来るか分からないので、選択ミスや当たりメニューで笑いを作りやすい。", "futuristic conveyor restaurant with tiny planet-shaped dishes, playful neon interior, visual novel background"),
    loc("推しメニューフードコート", "娯楽飲食区", "飲食施設", ["デート", "キャラ", "食事"], "各キャラクターの好みを反映した推しメニューが並ぶフードコート。誰のメニューを選ぶかで軽い嫉妬、照れ、ツッコミが生まれる。", "futuristic food court with character themed menu boards, colorful stalls, visual novel background"),
    loc("AIバーテンダーのカクテルバー", "夜遊び区", "飲食施設", ["デート", "バー", "大人"], "AIバーテンダーが気分や関係性に合わせたカクテルを作るバー。甘い名前のドリンク、意味深な診断、少し大人っぽい会話に使える。", "futuristic cocktail bar, AI bartender, glowing bottles, intimate counter seats, visual novel background"),
    loc("激辛チャレンジ専門店", "娯楽飲食区", "飲食施設", ["デート", "食事", "コメディ"], "辛さレベルを選んで挑戦する専門店。強がり、涙目、汗、意地の張り合いなど、笑いと距離感の近い会話が起こりやすい。", "spicy food challenge restaurant, red neon, dramatic plates, playful atmosphere, visual novel background"),
    loc("金箔だらけの成金レストラン", "金融区", "飲食施設", ["デート", "贅沢", "ドル"], "金箔、シャンデリア、過剰なVIP演出が売りのレストラン。価値観の違いや見栄、贅沢へのツッコミを会話にできる。", "overly luxurious gold leaf restaurant, chandeliers, VIP booth, futuristic city, visual novel background", "ドル"),
    loc("失敗料理の実験キッチン", "研究飲食区", "飲食施設", ["デート", "実験", "コメディ"], "新作料理の試作だけを出す実験キッチン。成功か失敗か分からない皿が出てくるので、リアクションと相談が自然に生まれる。", "experimental kitchen restaurant, strange glowing dishes, clean lab-like interior, visual novel background"),
    loc("空中庭園", "上層庭園区", "ロマンチック施設", ["デート", "夜景", "自然"], "都市上空に浮かぶ庭園。風、花、遠いネオン、静かなベンチがあり、恋愛や本音の会話をゆっくり進められる。", "floating sky garden above neon city, flowers, glass paths, romantic bench, visual novel background"),
    loc("夜景展望デッキ", "上層展望区", "ロマンチック施設", ["デート", "夜景", "告白"], "ラプラスシティ全体を見下ろせる展望デッキ。沈黙しても気まずくなりにくく、告白、相談、将来の話に使いやすい。", "night observation deck overlooking futuristic city, glass railing, blue neon skyline, visual novel background"),
    loc("人工流星観測テラス", "上層展望区", "ロマンチック施設", ["デート", "星", "願い"], "定時になると人工流星が空を流れるテラス。願いごと、予測できない光、隣にいる理由を話すきっかけになる。", "terrace under artificial meteor shower, futuristic skyline, romantic lighting, visual novel background"),
    loc("ガラス張りの水中回廊", "水景区", "ロマンチック施設", ["デート", "水族館", "静か"], "透明な回廊の周囲を光る魚や水中ドローンが泳ぐ。ゆっくり歩きながら、静かで少し幻想的な会話ができる。", "glass underwater corridor, glowing fish, futuristic aquarium tunnel, blue light, visual novel background"),
    loc("光る花の植物園", "自然再現区", "ロマンチック施設", ["デート", "花", "癒し"], "夜になると花弁が発光する植物園。好きな色や香りを選ぶ場面、写真、プレゼントの話に向いている。", "bioluminescent flower botanical garden, glowing petals, soft romantic paths, visual novel background"),
    loc("無重力イルミネーションホール", "娯楽区", "ロマンチック施設", ["デート", "イルミネーション", "非日常"], "短時間だけ無重力になり、光の粒が浮かぶホール。手を取る理由が自然にでき、少しドキドキした会話に使える。", "zero gravity illumination hall, floating lights, futuristic romantic interior, visual novel background"),
    loc("記憶を映す噴水広場", "中央広場", "ロマンチック施設", ["デート", "記憶", "本音"], "水面に訪れた人の印象や記憶の断片が映る噴水広場。過去の話、隠している気持ち、冗談交じりの診断に使える。", "futuristic fountain plaza showing memory-like holograms, night city lights, visual novel background"),
    loc("願い登録端末の祈願スポット", "中央広場", "ロマンチック施設", ["デート", "願い", "イベント"], "二人で願いを登録すると、都市広告の片隅に一瞬だけ願いが流れるスポット。照れやツッコミ、約束の会話に向く。", "small futuristic wish terminal, glowing public display, couple date spot, visual novel background"),
    loc("月光シミュレーション室", "自然再現区", "ロマンチック施設", ["デート", "月光", "静か"], "本物そっくりの月光、風、影を再現する個室型施設。静かな恋愛会話、弱音、本音の吐露に向いている。", "moonlight simulation room, artificial moon, soft shadows, intimate futuristic chamber, visual novel background"),
    loc("雨音を選べる静音ラウンジ", "休息区", "ロマンチック施設", ["デート", "雨音", "相談"], "雨音の種類を選んで過ごす静かなラウンジ。雑談、悩み相談、疲れたキャラの本音を引き出すのに向いている。", "quiet lounge with selectable rain sound panels, dim blue lights, comfortable seats, visual novel background"),
    loc("VR遊園地", "娯楽区", "遊戯施設", ["デート", "遊園地", "VR"], "物理空間とVR演出が混ざった遊園地。絶叫、迷子、ペアアトラクションなど、テンポのよいデートに使える。", "futuristic VR amusement park, hologram rides, neon attractions, visual novel background"),
    loc("ホログラム映画館", "娯楽区", "遊戯施設", ["デート", "映画", "会話"], "映画の登場人物や背景が客席近くまで出てくるホログラム映画館。作品の感想や怖い場面での距離感に使える。", "hologram cinema, futuristic theater seats, immersive projected characters, visual novel background"),
    loc("占いAIブース", "娯楽区", "遊戯施設", ["デート", "占い", "恋"], "AIが恋愛運や相性をそれっぽく診断する小さなブース。結果を信じるか疑うかで軽い掛け合いができる。", "small AI fortune telling booth, holographic tarot, neon curtains, visual novel background"),
    loc("感情同期ルーム", "娯楽区", "遊戯施設", ["デート", "感情", "音楽"], "二人の声や心拍に合わせて照明と音楽が変わる部屋。照れ、笑い、緊張をそのまま演出にできる。", "emotion sync karaoke-like room, reactive lights, futuristic music booth, visual novel background"),
    loc("謎解きミュージアム", "文化娯楽区", "遊戯施設", ["デート", "謎解き", "協力"], "展示品に隠された謎を二人で解くミュージアム。知識、勘違い、協力プレイ、意外な得意不得意が出しやすい。", "mystery solving museum, interactive exhibits, glowing clues, futuristic interior, visual novel background"),
    loc("射的・屋台ゲーム街", "娯楽区", "遊戯施設", ["デート", "屋台", "ゲーム"], "旧人類風の射的や輪投げをサイバー化したゲーム街。景品を取る、外す、譲るなど分かりやすい会話が作れる。", "cyber festival game street, shooting gallery, ring toss stalls, neon prizes, visual novel background"),
    loc("コスプレ試着スタジオ", "ファッション区", "遊戯施設", ["デート", "衣装", "写真"], "衣装を選んで試着し、撮影までできるスタジオ。照れ、褒め合い、衣装選び、写真イベントへつなげやすい。", "cosplay fitting studio, futuristic mirrors, costume racks, photo booth, visual novel background"),
    loc("ダンスゲームアリーナ", "娯楽区", "遊戯施設", ["デート", "ゲーム", "運動"], "床と壁が光る大型ダンスゲーム施設。勝負、ミス、息切れ、褒め合いが自然に起こる。", "futuristic dance game arena, glowing floor panels, rhythm lights, visual novel background"),
    loc("ペア診断アトラクション", "娯楽区", "遊戯施設", ["デート", "診断", "恋"], "質問とミニゲームで二人の相性を診断するアトラクション。結果に照れる、反論する、乗っかるなどの会話に向く。", "pair compatibility diagnosis attraction, neon pods, hologram result screen, visual novel background"),
    loc("旧人類ゲームセンター", "旧人類文化区", "遊戯施設", ["デート", "ゲーム", "旧人類"], "古いアーケード筐体やクレーンゲームを再現したゲームセンター。懐かしさ、下手さ、ムキになる姿で笑いを作れる。", "retro arcade in futuristic city, old game cabinets, crane machines, neon glow, visual novel background"),
    loc("旧人類資料館", "旧人類文化区", "会話施設", ["デート", "旧人類", "学び"], "旧人類の生活、恋愛、仕事、失敗文化を展示する資料館。世界観説明とツッコミを両立できる。", "museum of old humanity, artifacts, documents, futuristic archive displays, visual novel background"),
    loc("記憶アーカイブ図書館", "知識区", "会話施設", ["デート", "図書館", "記憶"], "個人の記憶記録や都市の会話ログを閲覧できる静かな図書館。過去、秘密、好きな物語の話に向いている。", "memory archive library, glowing shelves, quiet reading pods, futuristic visual novel background"),
    loc("失恋相談カフェ", "相談区", "会話施設", ["デート", "相談", "恋"], "恋愛の失敗談を聞いてくれるカフェ。軽い笑いから本気の相談まで扱え、キャラ自身の弱音も出しやすい。", "heartbreak counseling cafe, warm lights, private booths, soft neon, visual novel background"),
    loc("夢記録睡眠ポッド", "休息区", "会話施設", ["デート", "夢", "心理"], "眠った人の夢を短い映像ログにする施設。変な夢、願望、怖いもの、隠れた本音を会話にできる。", "dream recording sleep pod facility, soft blue capsules, hologram dream screens, visual novel background"),
    loc("心理テスト研究所", "研究区", "会話施設", ["デート", "心理", "診断"], "軽い心理テストを受けられる研究所。結果に対する反応でキャラの性格やプレイヤーの好みを引き出せる。", "psychological test laboratory, clean futuristic booths, result monitors, visual novel background"),
    loc("秘密を預ける貸金庫", "金融区", "会話施設", ["デート", "秘密", "本音"], "一つだけ秘密を暗号化して預けられる貸金庫。言うか言わないか、何を隠すかで緊張感のある会話になる。", "futuristic private vault for secrets, secure boxes, dim gold lights, visual novel background", "ドル"),
    loc("未来郵便局", "中央生活区", "会話施設", ["デート", "手紙", "約束"], "手紙を書いて未来の自分や相手に送れる郵便局。約束、照れ、後悔、未来の話を自然に扱える。", "future post office, glowing mail terminals, letter writing desks, visual novel background"),
    loc("価値観可視化診断室", "研究区", "会話施設", ["デート", "価値観", "診断"], "二人の価値観を図や色で可視化する診断室。違いを笑ったり、意外な一致にドキッとしたりできる。", "values visualization diagnosis room, holographic charts, paired seats, visual novel background"),
    loc("好きなものだけ美術館", "文化娯楽区", "会話施設", ["デート", "美術館", "好き"], "来場者の好きなものだけが展示される小さな美術館。好み、思い出、変な趣味を拾える。", "small museum displaying visitors favorite things, intimate gallery, holographic exhibits, visual novel background"),
    loc("反省文懺悔ブース", "相談区", "会話施設", ["デート", "懺悔", "笑い"], "反省文を書くとAIが大げさに読み上げる懺悔ブース。失敗談や軽い謝罪を笑いに変えられる。", "confession booth with futuristic terminal, humorous apology display, dim cozy room, visual novel background"),
    loc("高級オークション会場", "金融区", "キャラ向け施設", ["デート", "ドル", "勝負"], "希少品や情報権利が競りにかけられるVIPオークション会場。ドルの勝負勘、見栄、駆け引きを引き出しやすい。", "luxury futuristic auction hall, gold neon, VIP bidders, dramatic stage, visual novel background", "ドル"),
    loc("投資ゲームラウンジ", "金融区", "キャラ向け施設", ["デート", "ドル", "ゲーム"], "仮想通貨や資源配分をゲーム化したラウンジ。勝ち負けが分かりやすく、ドルとの賭けやツッコミに向く。", "investment game lounge, holographic market board, luxury seats, cyber finance district, visual novel background", "ドル"),
    loc("ドル専用VIPレストラン", "金融区", "キャラ向け施設", ["デート", "ドル", "食事"], "ドルの好みに合わせた豪奢なVIPレストラン。高級感を笑うことも、乗っかって贅沢することもできる。", "exclusive VIP restaurant for wealthy cyber finance queen, gold decor, city view, visual novel background", "ドル"),
    loc("ラプラス観測塔", "上層展望区", "キャラ向け施設", ["デート", "ラプラス", "観測"], "ラプラスシティ全域を観測できる塔。予測、例外、プレイヤーの行動へのリアクションを会話にしやすい。", "futuristic observation tower above city, glass platform, blue data streams, visual novel background", "ラプラス"),
    loc("予測不能イベント会場", "娯楽区", "キャラ向け施設", ["デート", "ラプラス", "イベント"], "内容が毎回変わるイベント会場。ラプラスが予測を外す、照れる、ツッコむ展開に使える。", "unpredictable event venue, holographic random stage, colorful sci-fi crowd, visual novel background", "ラプラス"),
    loc("ラプラス空中庭園", "上層庭園区", "キャラ向け施設", ["デート", "ラプラス", "庭園"], "観測塔から近い静かな空中庭園。ラプラスの全知っぽさと、普通のデートらしい可愛さを両方出せる。", "sky garden connected to observation tower, blue glowing flowers, city panorama, visual novel background", "ラプラス"),
    loc("ミウのスイーツ街", "デート街区", "キャラ向け施設", ["デート", "ミウ", "スイーツ"], "限定スイーツ店が密集する通り。ミウの好み、はしゃぎ、選べない可愛さを出しやすい。", "cute futuristic sweets street, cake shops, pink neon, dessert displays, visual novel background", "ミウ"),
    loc("ミウのライブハウス", "音楽区", "キャラ向け施設", ["デート", "ミウ", "音楽"], "轟音のリハーサルと小さなステージがあるライブハウス。音楽、緊張、応援、終演後の余韻に使える。", "small futuristic live house, stage lights, band equipment, energetic neon, visual novel background", "ミウ"),
    loc("ミウのアクセサリーショップ", "ファッション区", "キャラ向け施設", ["デート", "ミウ", "買い物"], "髪飾りや小物を選べるアクセサリーショップ。似合うかどうか、プレゼント、照れた反応に向く。", "futuristic accessory shop, hair ornaments, glowing display cases, cute stylish interior, visual novel background", "ミウ"),
    loc("シラス水族館", "水景区", "キャラ向け施設", ["デート", "シラス", "水族館"], "透明な水槽と静かな青い光に包まれた水族館。水辺の会話やゆっくりしたデートに向く。", "large futuristic aquarium, blue tanks, glowing fish, quiet romantic walkway, visual novel background"),
    loc("シラス海辺の屋台", "水景区", "キャラ向け施設", ["デート", "シラス", "屋台"], "人工海岸沿いに並ぶ小さな屋台。潮風、軽食、気取らない会話に使いやすい。", "seaside food stalls on artificial coast, neon reflections on water, relaxed date atmosphere, visual novel background"),
    loc("シラス静かな港", "水景区", "キャラ向け施設", ["デート", "シラス", "港"], "夜の人工港。遠くの船灯と水音があり、沈黙や悩み相談も自然に受け止められる。", "quiet artificial harbor at night, futuristic boats, reflections, calm water, visual novel background"),
    loc("レイジア仮眠カフェ", "休息区", "キャラ向け施設", ["デート", "レイジア", "休息"], "短時間だけ眠れる仮眠カフェ。眠そうな会話、毛布、静かな距離感に向く。", "nap cafe with futuristic sleep pods, soft blankets, dim warm lights, visual novel background", "レイジア"),
    loc("低刺激ラウンジ", "休息区", "キャラ向け施設", ["デート", "レイジア", "静か"], "光も音も弱めに調整されたラウンジ。疲れたキャラの本音や、無理をしないデートに使える。", "low stimulus lounge, dim lights, soft acoustic panels, calm futuristic interior, visual novel background", "レイジア"),
    loc("静音公園", "休息区", "キャラ向け施設", ["デート", "レイジア", "公園"], "都市ノイズを遮断した静かな公園。寝転ぶ、ぼんやりする、ゆっくり話す場面に向く。", "silent park in futuristic city, soft grass, soundproof transparent dome, calm evening, visual novel background", "レイジア"),
    loc("ランキングアリーナ", "評価区", "キャラ向け施設", ["デート", "スコア", "勝負"], "競技や成果がリアルタイムで順位表示されるアリーナ。スコアの評価癖や競争心を出しやすい。", "ranking arena with giant leaderboard, futuristic competition floor, sharp lights, visual novel background", "スコア"),
    loc("採点ゲームセンター", "評価区", "キャラ向け施設", ["デート", "スコア", "ゲーム"], "遊ぶたびに細かく採点されるゲームセンター。点数に一喜一憂するコメディと勝負に使える。", "arcade with score evaluation machines, leaderboards, neon game cabinets, visual novel background", "スコア"),
    loc("スコア競技施設", "評価区", "キャラ向け施設", ["デート", "スコア", "競技"], "短距離、反射神経、判断力などを測る競技施設。順位、努力、褒め方を会話にしやすい。", "futuristic athletic and reflex testing facility, glowing tracks, score monitors, visual novel background", "スコア"),
    loc("報道資料館", "透明化局周辺", "キャラ向け施設", ["デート", "リーク", "報道"], "過去の報道資料や隠された訂正記録を見られる資料館。リークの正義感と疑り深さを活かせる。", "press archive museum, transparent displays, news records, investigative atmosphere, visual novel background", "リーク"),
    loc("裏路地ニューススタンド", "透明化局周辺", "キャラ向け施設", ["デート", "リーク", "ニュース"], "速報、噂、号外が集まる裏路地のニューススタンド。事件の火種や軽い情報戦に向いている。", "back alley news stand, holographic headlines, rainy cyberpunk alley, visual novel background", "リーク"),
    loc("透明化局跡地", "透明化局周辺", "キャラ向け施設", ["デート", "リーク", "謎"], "透明化局の跡地。消された表示、隠された通路、未公開記録があり、緊張感のある会話に使える。", "abandoned transparency bureau site, glass ruins, hidden data panels, mysterious neon shadows, visual novel background", "リーク"),
]


def main():
    app = create_app()
    with app.app_context():
        owners = {
            row.name: row.id
            for row in Character.query.filter(Character.project_id == PROJECT_ID).all()
            if row.name
        }
        existing = {
            row.name: row
            for row in WorldLocation.query.filter(
                WorldLocation.project_id == PROJECT_ID,
                WorldLocation.deleted_at.is_(None),
            ).all()
        }
        max_sort = (
            db.session.query(db.func.max(WorldLocation.sort_order))
            .filter(WorldLocation.project_id == PROJECT_ID)
            .scalar()
            or 0
        )
        created = 0
        skipped = 0
        for index, item in enumerate(LOCATIONS, start=1):
            if item["name"] in existing:
                skipped += 1
                continue
            owner_id = owners.get(item.get("owner_name"))
            row = WorldLocation(
                project_id=PROJECT_ID,
                name=item["name"],
                region=item["region"],
                location_type=item["location_type"],
                tags_json=json_util.dumps(item["tags"]),
                description=item["description"],
                image_prompt=item["image_prompt"],
                owner_character_id=owner_id,
                source_type="script",
                source_note="date course location batch",
                status="published",
                sort_order=max_sort + index,
            )
            db.session.add(row)
            created += 1
        db.session.commit()
        print(f"created={created} skipped={skipped} total_requested={len(LOCATIONS)}")


if __name__ == "__main__":
    main()
