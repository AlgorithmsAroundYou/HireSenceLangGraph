CREATE TABLE IF NOT EXISTS user_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

INSERT OR IGNORE INTO user_details (id, user_name, password, role, is_active)
VALUES (1, 'saikodati', 'root', 'admin', 1);

CREATE TABLE IF NOT EXISTS job_description_details (
    jd_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_saved_location TEXT NOT NULL,
    created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS resume_details (
    resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
    jd_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_location TEXT NOT NULL,
    created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (jd_id) REFERENCES job_description_details (jd_id)
);
