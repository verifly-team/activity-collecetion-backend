-- ============================================================================
-- v2 调研字段升级（备用 DDL）
--
-- 正常情况下【不需要手工执行】：
--   采集服务启动时 init_db() 会自动检查缺列并 ALTER TABLE 补齐。
--
-- 只有以下情况才需要手工跑：
--   1. 应用连接 MySQL 的账号没有 ALTER 权限
--   2. 想在大流量时段提前把表结构改好，避免启动时加锁
--   3. 自动化迁移失败，需要人工兜底
--
-- 执行前先备份：
--   mysqldump -u root -p --single-transaction verifly_signup \
--     application file > backup_$(date +%Y%m%d_%H%M).sql
-- ============================================================================

USE `verifly_signup`;

ALTER TABLE `application`
  ADD COLUMN `founded_year`          INT           NULL COMMENT '品牌成立年份',
  ADD COLUMN `social_links`          VARCHAR(2000) NULL COMMENT 'JSON: 社交平台链接',
  ADD COLUMN `brand_intro`           TEXT          NULL COMMENT '品牌简介 100-300 字',
  ADD COLUMN `channels`              VARCHAR(200)  NULL COMMENT 'JSON: 主要经营渠道',
  ADD COLUMN `has_physical_store`    TINYINT(1)    NULL COMMENT '是否有实体店',
  ADD COLUMN `attended_other_events` TINYINT(1)    NULL COMMENT '是否参加过其他市集或展会',
  ADD COLUMN `past_experience`       TEXT          NULL COMMENT '过往参展经历',
  ADD COLUMN `brand_specialty`       TEXT          NULL COMMENT '品牌最有特色的地方',
  ADD COLUMN `target_consumers`      VARCHAR(30)   NULL COMMENT '主要面向消费者',
  ADD COLUMN `planned_activities`    VARCHAR(300)  NULL COMMENT 'JSON: 特别商品或活动',
  ADD COLUMN `willing_to_promote`    VARCHAR(30)   NULL COMMENT '配合品牌宣传意愿',
  ADD COLUMN `authorize_media`       VARCHAR(30)   NULL COMMENT '素材授权范围';

-- ---------------------------------------------------------------------------
-- 验证：应该返回 12 行
-- ---------------------------------------------------------------------------
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'verifly_signup'
  AND TABLE_NAME = 'application'
  AND COLUMN_NAME IN (
    'founded_year', 'social_links', 'brand_intro', 'channels',
    'has_physical_store', 'attended_other_events', 'past_experience',
    'brand_specialty', 'target_consumers', 'planned_activities',
    'willing_to_promote', 'authorize_media'
  )
ORDER BY ORDINAL_POSITION;

-- ---------------------------------------------------------------------------
-- 回滚（真要退回旧版才用；会丢失这 12 列数据）
-- ---------------------------------------------------------------------------
-- ALTER TABLE `application`
--   DROP COLUMN `founded_year`,          DROP COLUMN `social_links`,
--   DROP COLUMN `brand_intro`,           DROP COLUMN `channels`,
--   DROP COLUMN `has_physical_store`,    DROP COLUMN `attended_other_events`,
--   DROP COLUMN `past_experience`,       DROP COLUMN `brand_specialty`,
--   DROP COLUMN `target_consumers`,      DROP COLUMN `planned_activities`,
--   DROP COLUMN `willing_to_promote`,    DROP COLUMN `authorize_media`;
