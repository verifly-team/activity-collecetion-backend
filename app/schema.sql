-- 66th 商家参展申请 —— 两张表，够用就好
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS application (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at        TEXT    NOT NULL,

  -- 品牌与联络
  brand_name        TEXT    NOT NULL,   -- 品牌／店铺名称
  contact_name      TEXT    NOT NULL,   -- 联系人
  phone             TEXT    NOT NULL,   -- 手机
  wechat            TEXT,               -- 微信
  email             TEXT,               -- 邮箱（与微信至少一项）
  city              TEXT,               -- 所在城市
  entity_type       TEXT,               -- company / individual / personal
  is_first_time     INTEGER NOT NULL DEFAULT 0,

  -- 经营与参展内容
  categories        TEXT    NOT NULL,   -- JSON: ["bag","watch"]
  zones             TEXT    NOT NULL,   -- JSON: ["A","C"]
  expected_qty      INTEGER,            -- 预计带货件数
  price_min         INTEGER,            -- 价格区间下限
  price_max         INTEGER,            -- 价格区间上限
  pct_secondhand    INTEGER,            -- 商品结构：二手 %
  pct_new_stock     INTEGER,            -- 未使用库存 %
  pct_sample        INTEGER,            -- 样衣 %
  pct_replica       INTEGER,            -- 复刻／原创 %
  items_json        TEXT    NOT NULL DEFAULT '[]',  -- 代表商品 3~5 件

  -- 合规
  consent_at        TEXT,
  privacy_version   TEXT,

  -- 溯源
  source            TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_phone ON application(phone);
CREATE INDEX IF NOT EXISTS idx_app_city  ON application(city);

CREATE TABLE IF NOT EXISTS file (
  id             TEXT    PRIMARY KEY,     -- uuid，磁盘文件名
  application_id INTEGER REFERENCES application(id) ON DELETE CASCADE,
  kind           TEXT,                    -- photos / list / other
  original_name  TEXT    NOT NULL,
  stored_path    TEXT    NOT NULL,        -- 相对 UPLOAD_DIR，如 1/ab12.jpg
  mime           TEXT,
  size           INTEGER NOT NULL,
  sha256         TEXT,
  created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_file_app ON file(application_id);
