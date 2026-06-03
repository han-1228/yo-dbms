CREATE DATABASE IF NOT EXISTS `schoolsystemdb`;
USE `schoolsystemdb`;

-- 1. 建立學生表 (Students)
CREATE TABLE Students (
    STU_ID VARCHAR(50) PRIMARY KEY,
    STU_NAME VARCHAR(200) NOT NULL,
    CLASS_NAME VARCHAR(100) NOT NULL,
    SEAT_NUM INT
) ENGINE=InnoDB;

-- 2. 建立課程表 (Courses)
CREATE TABLE Courses (
    COURSE_ID VARCHAR(50) PRIMARY KEY,
    COURSE_NAME VARCHAR(255) NOT NULL,
    SEMESTER VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

-- 3. 建立修課表 (Enrollments)
CREATE TABLE Enrollments (
    ENROLL_ID VARCHAR(50) PRIMARY KEY,
    STU_ID VARCHAR(50),
    COURSE_ID VARCHAR(50),
    FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
    FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
) ENGINE=InnoDB;

-- 4. 建立評量項目表 (Assessments)
CREATE TABLE Assessments (
    AST_ID VARCHAR(50) PRIMARY KEY,
    COURSE_ID VARCHAR(50),
    AST_NAME VARCHAR(255) NOT NULL,
    CATEGORY VARCHAR(100),
    WEIGHT FLOAT,
    FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
) ENGINE=InnoDB;

-- 5. 建立成績表 (Scores)
CREATE TABLE Scores (
    SCORE_ID VARCHAR(50) PRIMARY KEY,
    STU_ID VARCHAR(50),
    AST_ID VARCHAR(50),
    SCORE INT,
    FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
    FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
) ENGINE=InnoDB;

-- 6. 建立學生作品表 (Portfolios)
CREATE TABLE Portfolios (
    PORTFO_ID VARCHAR(50) PRIMARY KEY,
    STU_ID VARCHAR(50),
    COURSE_ID VARCHAR(50),
    AST_ID VARCHAR(50),
    TITLE VARCHAR(255),
    UPLOAD_DATE VARCHAR(50),
    FILE_URL TEXT,
    FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
    FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID),
    FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
) ENGINE=InnoDB;

-- Triggers: 新增/更新 Assessments 後自動正規化權重
DELIMITER $$
DROP TRIGGER IF EXISTS tr_assess_norm_after_insert $$
CREATE TRIGGER tr_assess_norm_after_insert
AFTER INSERT ON Assessments
FOR EACH ROW
BEGIN
  DECLARE _sum DOUBLE DEFAULT 0;
  DECLARE _cnt INT DEFAULT 0;
  IF @__assess_norm_lock IS NULL OR @__assess_norm_lock = 0 THEN
    SET @__assess_norm_lock = 1;
    SELECT SUM(WEIGHT) INTO _sum FROM Assessments WHERE COURSE_ID = NEW.COURSE_ID;
    IF _sum IS NULL OR _sum = 0 THEN
      SELECT COUNT(*) INTO _cnt FROM Assessments WHERE COURSE_ID = NEW.COURSE_ID;
      IF _cnt > 0 THEN
        UPDATE Assessments SET WEIGHT = 1.0 / _cnt WHERE COURSE_ID = NEW.COURSE_ID;
      END IF;
    ELSE
      UPDATE Assessments SET WEIGHT = WEIGHT / _sum WHERE COURSE_ID = NEW.COURSE_ID;
    END IF;
    SET @__assess_norm_lock = 0;
  END IF;
END $$

DROP TRIGGER IF EXISTS tr_assess_norm_after_update $$
CREATE TRIGGER tr_assess_norm_after_update
AFTER UPDATE ON Assessments
FOR EACH ROW
BEGIN
  DECLARE _sum2 DOUBLE DEFAULT 0;
  DECLARE _cnt2 INT DEFAULT 0;
  IF @__assess_norm_lock IS NULL OR @__assess_norm_lock = 0 THEN
    SET @__assess_norm_lock = 1;
    SELECT SUM(WEIGHT) INTO _sum2 FROM Assessments WHERE COURSE_ID = NEW.COURSE_ID;
    IF _sum2 IS NULL OR _sum2 = 0 THEN
      SELECT COUNT(*) INTO _cnt2 FROM Assessments WHERE COURSE_ID = NEW.COURSE_ID;
      IF _cnt2 > 0 THEN
        UPDATE Assessments SET WEIGHT = 1.0 / _cnt2 WHERE COURSE_ID = NEW.COURSE_ID;
      END IF;
    ELSE
      UPDATE Assessments SET WEIGHT = WEIGHT / _sum2 WHERE COURSE_ID = NEW.COURSE_ID;
    END IF;
    SET @__assess_norm_lock = 0;
  END IF;
END $$
DELIMITER ;
