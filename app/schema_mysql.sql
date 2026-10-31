-- 66th 商家参展申请 —— MySQL 8 / 5.7 通用 DDL
-- 建库：CREATE DATABASE IF NOT EXISTS verifly_signup
--         DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS application (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

  -- 品牌与联络
  brand_name        VARCHAR(120) NOT NULL COMMENT '品牌／店铺名称',
  contact_name      VARCHAR(60)  NOT NULL COMMENT '联系人',
  phone             VARCHAR(20)  NOT NULL COMMENT '手机号',
  wechat            VARCHAR(60)  NULL COMMENT '微信',
  email             VARCHAR(120) NULL COMMENT '邮箱',
  city              VARCHAR(60)  NULL COMMENT '所在城市',
  entity_type       VARCHAR(20)  NULL COMMENT 'company/individual/personal',
  is_first_time     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否首次参展',

  -- 经营与参展内容
  categories        VARCHAR(200) NOT NULL COMMENT 'JSON: ["bag","watch"]',
  zones             VARCHAR(50)  NOT NULL COMMENT 'JSON: ["A","C"]',
  expected_qty      INT          NULL COMMENT '预计带货件数',
  price_min         INT          NULL COMMENT '价格区间下限',
  price_max         INT          NULL COMMENT '价格区间上限',
  pct_secondhand    TINYINT      NULL COMMENT '二手 %',
  pct_new_stock     TINYINT      NULL COMMENT '未使用库存 %',
  pct_sample        TINYINT      NULL COMMENT '样衣 %',
  pct_replica       TINYINT      NULL COMMENT '复刻／原创 %',
  items_json        TEXT         NULL COMMENT '代表商品清单 JSON',

  -- 品牌背景与经营情况（v2 调研新增，历史数据为 NULL）
  founded_year          INT          NULL COMMENT '品牌成立年份',
  social_links          VARCHAR(2000) NULL COMMENT 'JSON: 社交平台链接',
  brand_intro           TEXT         NULL COMMENT '品牌简介 100-300 字',
  channels              VARCHAR(200) NULL COMMENT 'JSON: 主要经营渠道',
  has_physical_store    TINYINT(1)   NULL COMMENT '是否有实体店',
  attended_other_events TINYINT(1)   NULL COMMENT '是否参加过其他市集或展会',
  past_experience       TEXT         NULL COMMENT '过往参展经历',
  brand_specialty       TEXT         NULL COMMENT '品牌最有特色的地方',
  target_consumers      VARCHAR(30)  NULL COMMENT '主要面向消费者',
  planned_activities    VARCHAR(300) NULL COMMENT 'JSON: 特别商品或活动',
  willing_to_promote    VARCHAR(30)  NULL COMMENT '配合品牌宣传意愿',
  authorize_media       VARCHAR(30)  NULL COMMENT '素材授权范围',

  -- 合规
  consent_at        VARCHAR(32)  NULL COMMENT '同意时间 UTC',
  privacy_version   VARCHAR(20)  NULL COMMENT '政策版本',

  -- 系统
  source            VARCHAR(30)  NULL COMMENT 'h5/qrcode/word',
  created_at        VARCHAR(32)  NOT NULL COMMENT '提交时间 UTC',

  PRIMARY KEY (id),
  KEY idx_app_phone (phone),
  KEY idx_app_city (city),
  KEY idx_app_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='商家参展申请';

CREATE TABLE IF NOT EXISTS file (
  id             VARCHAR(32) NOT NULL COMMENT 'uuid，同时是磁盘文件名',
  application_id BIGINT UNSIGNED NULL COMMENT '关联报名，提交前为 NULL',
  kind           VARCHAR(20) NULL COMMENT 'photos/list/other',
  original_name  VARCHAR(255) NOT NULL COMMENT '原始文件名',
  stored_path    VARCHAR(255) NOT NULL COMMENT '相对 UPLOAD_DIR',
  mime           VARCHAR(120) NULL,
  size           BIGINT NOT NULL DEFAULT 0,
  sha256         VARCHAR(64) NULL,
  created_at     VARCHAR(32) NOT NULL,

  PRIMARY KEY (id),
  KEY idx_file_app (application_id),
  KEY idx_file_created (created_at),
  CONSTRAINT fk_file_application FOREIGN KEY (application_id)
    REFERENCES application (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='报名附件';
