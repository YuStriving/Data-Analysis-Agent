-- Dataset module MVP schema
-- Date: 2026-08-31
-- Scope:
-- 1. dataset
-- 2. dataset_mysql_conn

CREATE TABLE IF NOT EXISTS dataset (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    dataset_id VARCHAR(64) NOT NULL COMMENT 'Business dataset ID, e.g. dataset-xxxxxxxx',
    name VARCHAR(128) NOT NULL COMMENT 'Dataset name',
    source_type VARCHAR(32) NOT NULL COMMENT 'CSV, XLSX, XLS, MYSQL',
    status VARCHAR(32) NOT NULL DEFAULT 'REGISTERING' COMMENT 'REGISTERING, REGISTERED, FAILED',
    owner_user_id VARCHAR(64) NULL COMMENT 'Owner user ID from auth_user',
    description VARCHAR(512) NULL COMMENT 'Optional description',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    PRIMARY KEY (id),
    UNIQUE KEY uk_dataset_dataset_id (dataset_id),
    KEY idx_dataset_owner (owner_user_id),
    KEY idx_dataset_status (status)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Datasets';

CREATE TABLE IF NOT EXISTS dataset_mysql_conn (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
    dataset_id VARCHAR(64) NOT NULL COMMENT 'Business dataset ID referencing dataset.dataset_id',
    host VARCHAR(255) NOT NULL COMMENT 'MySQL host',
    port INT NOT NULL COMMENT 'MySQL port',
    database_name VARCHAR(64) NOT NULL COMMENT 'MySQL database name',
    username VARCHAR(64) NOT NULL COMMENT 'MySQL username (read-only recommended)',
    password_cipher VARCHAR(512) NOT NULL COMMENT 'AES-GCM encrypted password, Base64(iv + ciphertext)',
    schema_json MEDIUMTEXT NULL COMMENT 'Table and column metadata JSON read from information_schema',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    PRIMARY KEY (id),
    UNIQUE KEY uk_dataset_mysql_conn_dataset_id (dataset_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='MySQL connection info for datasets';
