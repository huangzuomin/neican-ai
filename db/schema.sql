CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1,
  trust_level INTEGER NOT NULL DEFAULT 3,
  language TEXT DEFAULT 'en',
  fetch_interval_minutes INTEGER DEFAULT 120,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER,
  source_url TEXT NOT NULL,
  title TEXT,
  author TEXT,
  published_at TEXT,
  fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  raw_text TEXT,
  clean_text TEXT,
  content_hash TEXT NOT NULL UNIQUE,
  extraction_confidence REAL DEFAULT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  duplicate_of INTEGER,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_item_id INTEGER NOT NULL,
  event_title TEXT NOT NULL,
  event_summary TEXT,
  event_type TEXT,
  event_date TEXT,
  entities_json TEXT,
  topics_json TEXT,
  claims_json TEXT,
  importance_score REAL DEFAULT 0,
  seo_value_score REAL DEFAULT 0,
  knowledge_value_score REAL DEFAULT 0,
  risk_score REAL DEFAULT 0,
  confidence REAL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'modeled',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (raw_item_id) REFERENCES raw_items(id)
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  decision_grade TEXT NOT NULL,
  reason TEXT,
  need_review INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS review_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_type TEXT NOT NULL,
  target_id INTEGER NOT NULL,
  review_type TEXT NOT NULL,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  context_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content_type TEXT NOT NULL,
  slug TEXT,
  file_path TEXT,
  git_commit TEXT,
  published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL,
  message TEXT
);

CREATE TABLE IF NOT EXISTS timeline_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL UNIQUE,
  date TEXT NOT NULL,
  year TEXT NOT NULL,
  month TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  summary TEXT,
  why_it_matters TEXT,
  event_type TEXT,
  grade TEXT NOT NULL,
  importance_score REAL DEFAULT 0,
  confidence REAL DEFAULT 0,
  risk_score REAL DEFAULT 0,
  entities_json TEXT,
  topics_json TEXT,
  claims_json TEXT,
  sources_json TEXT,
  status TEXT NOT NULL DEFAULT 'public',
  review_status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_nodes_date ON timeline_nodes(date);
CREATE INDEX IF NOT EXISTS idx_timeline_nodes_year ON timeline_nodes(year);
CREATE INDEX IF NOT EXISTS idx_timeline_nodes_grade ON timeline_nodes(grade);

CREATE TABLE IF NOT EXISTS entity_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  entity_type TEXT NOT NULL DEFAULT 'organization',
  summary TEXT,
  signal TEXT,
  related_events INTEGER DEFAULT 0,
  related_topics_json TEXT,
  timeline_nodes_json TEXT,
  claims_json TEXT,
  sources_json TEXT,
  status TEXT NOT NULL DEFAULT 'public',
  review_status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_profiles_type ON entity_profiles(entity_type);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT,
  output_json TEXT,
  error_message TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);
