-- ResumeIQ MySQL schema bootstrap
-- Market-ready baseline for auth, resume parsing, template selection, job search,
-- tailoring, application tracking, and activity history.

CREATE DATABASE IF NOT EXISTS `resumeiq`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `resumeiq`;

CREATE TABLE IF NOT EXISTS `user` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `hashed_password` VARCHAR(255) NOT NULL,
  `name` VARCHAR(255) NOT NULL DEFAULT '',
  `plan` VARCHAR(64) NOT NULL DEFAULT 'free',
  `email_verified` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_email` (`email`)
);

CREATE TABLE IF NOT EXISTS `emailotpcode` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `user_id` INT NOT NULL,
  `code_hash` VARCHAR(255) NOT NULL,
  `expires_at` DATETIME NOT NULL,
  `consumed` TINYINT(1) NOT NULL DEFAULT 0,
  `purpose` VARCHAR(64) NOT NULL DEFAULT 'register',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_emailotpcode_email` (`email`),
  KEY `ix_emailotpcode_user_id` (`user_id`),
  CONSTRAINT `fk_emailotpcode_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
);

CREATE TABLE IF NOT EXISTS `templatecatalog` (
  `id` VARCHAR(128) NOT NULL,
  `name` VARCHAR(255) NOT NULL,
  `style` VARCHAR(128) NOT NULL DEFAULT 'LaTeX',
  `best_for` VARCHAR(255) NOT NULL DEFAULT '',
  `ats_score` INT NOT NULL DEFAULT 90,
  `kind` VARCHAR(64) NOT NULL DEFAULT 'latex',
  `source` VARCHAR(64) NOT NULL DEFAULT 'builtin',
  `description` VARCHAR(500) NOT NULL DEFAULT '',
  `preview_variant` VARCHAR(64) NOT NULL DEFAULT 'clean',
  `preview_asset` VARCHAR(1000) NULL,
  `entry_path` VARCHAR(1000) NULL,
  `folder_path` VARCHAR(1000) NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_templatecatalog_active_sort` (`is_active`, `sort_order`)
);

CREATE TABLE IF NOT EXISTS `resume` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `file_url` VARCHAR(500) NULL,
  `parsed_json` JSON NULL,
  `ats_baseline` FLOAT NULL,
  `active_template_id` VARCHAR(128) NOT NULL DEFAULT '',
  `version` INT NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `ix_resume_user_id` (`user_id`),
  KEY `ix_resume_template` (`active_template_id`),
  CONSTRAINT `fk_resume_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
);

CREATE TABLE IF NOT EXISTS `resumetemplateselection` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `resume_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `template_id` VARCHAR(128) NOT NULL,
  `template_name` VARCHAR(255) NOT NULL DEFAULT '',
  `source` VARCHAR(64) NOT NULL DEFAULT 'unknown',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_resumetemplateselection_resume_id` (`resume_id`),
  KEY `ix_resumetemplateselection_user_id` (`user_id`),
  KEY `ix_resumetemplateselection_template_id` (`template_id`),
  CONSTRAINT `fk_resumetemplateselection_resume` FOREIGN KEY (`resume_id`) REFERENCES `resume` (`id`),
  CONSTRAINT `fk_resumetemplateselection_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
);

CREATE TABLE IF NOT EXISTS `jdanalysis` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `raw_jd` MEDIUMTEXT NOT NULL,
  `parsed_json` JSON NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_jdanalysis_user_id` (`user_id`),
  CONSTRAINT `fk_jdanalysis_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
);

CREATE TABLE IF NOT EXISTS `tailoringsession` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `resume_id` INT NOT NULL,
  `jd_id` INT NULL,
  `output_resume_json` JSON NULL,
  `pdf_path` VARCHAR(1000) NULL,
  `ats_score` FLOAT NULL,
  `template_id` VARCHAR(128) NOT NULL DEFAULT '',
  `status` VARCHAR(64) NOT NULL DEFAULT 'draft',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_tailoringsession_resume_id` (`resume_id`),
  KEY `ix_tailoringsession_jd_id` (`jd_id`),
  KEY `ix_tailoringsession_template_id` (`template_id`),
  CONSTRAINT `fk_tailoringsession_resume` FOREIGN KEY (`resume_id`) REFERENCES `resume` (`id`),
  CONSTRAINT `fk_tailoringsession_jd` FOREIGN KEY (`jd_id`) REFERENCES `jdanalysis` (`id`)
);

CREATE TABLE IF NOT EXISTS `joblisting` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `source` VARCHAR(128) NOT NULL,
  `external_id` VARCHAR(255) NOT NULL,
  `title` VARCHAR(500) NOT NULL,
  `company` VARCHAR(300) NOT NULL,
  `location` VARCHAR(500) NOT NULL DEFAULT '',
  `description` MEDIUMTEXT NULL,
  `salary_range` VARCHAR(128) NULL,
  `job_type` VARCHAR(64) NOT NULL DEFAULT 'full-time',
  `remote` VARCHAR(64) NOT NULL DEFAULT 'hybrid',
  `skills` JSON NULL,
  `posted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `apply_url` VARCHAR(2000) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_joblisting_source_external` (`source`, `external_id`),
  KEY `ix_joblisting_company` (`company`),
  KEY `ix_joblisting_posted_at` (`posted_at`)
);

CREATE TABLE IF NOT EXISTS `application` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `job_id` INT NOT NULL,
  `resume_id` INT NULL,
  `status` VARCHAR(64) NOT NULL DEFAULT 'saved',
  `notes` TEXT NOT NULL,
  `applied_at` DATETIME NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_application_user_job` (`user_id`, `job_id`),
  KEY `ix_application_resume_id` (`resume_id`),
  KEY `ix_application_status` (`status`),
  CONSTRAINT `fk_application_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_application_job` FOREIGN KEY (`job_id`) REFERENCES `joblisting` (`id`),
  CONSTRAINT `fk_application_resume` FOREIGN KEY (`resume_id`) REFERENCES `resume` (`id`)
);

CREATE TABLE IF NOT EXISTS `applicationevent` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `application_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `from_status` VARCHAR(64) NOT NULL DEFAULT '',
  `to_status` VARCHAR(64) NOT NULL DEFAULT '',
  `note` VARCHAR(500) NOT NULL DEFAULT '',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_applicationevent_application_id` (`application_id`),
  KEY `ix_applicationevent_user_id` (`user_id`),
  CONSTRAINT `fk_applicationevent_application` FOREIGN KEY (`application_id`) REFERENCES `application` (`id`),
  CONSTRAINT `fk_applicationevent_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
);

-- Optional starter user (replace hashed password from app if needed)
-- INSERT INTO `user` (`email`, `hashed_password`, `name`, `plan`, `email_verified`)
-- VALUES ('admin@resumeiq.local', '$2b$12$replace_with_bcrypt_hash', 'Admin', 'free', 1);
