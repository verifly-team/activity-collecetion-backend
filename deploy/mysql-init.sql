-- 交给 DBA 在 MySQL 上执行一次
-- 库名/账号密码按实际环境改

CREATE DATABASE IF NOT EXISTS `verifly_signup`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'verifly'@'%' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

-- 应用只需要这两张表的增删改查 + 建表权限（首次启动会自动建表）
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES
  ON `verifly_signup`.* TO 'verifly'@'%';

FLUSH PRIVILEGES;

-- 验证
-- SHOW CREATE DATABASE verifly_signup;
