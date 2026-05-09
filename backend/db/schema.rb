# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_05_09_001400) do
  create_table "copilot_sessions", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.integer "activity_count", default: 0, null: false
    t.string "branch"
    t.text "conversation_preview"
    t.datetime "created_at", null: false
    t.datetime "created_at_source"
    t.text "cwd"
    t.boolean "degraded", default: false, null: false
    t.json "detail_payload", null: false
    t.integer "event_count", default: 0, null: false
    t.text "git_root"
    t.datetime "indexed_at", null: false
    t.integer "issue_count", default: 0, null: false
    t.integer "message_count", default: 0, null: false
    t.integer "message_snapshot_count", default: 0, null: false
    t.string "repository"
    t.text "search_text", size: :medium, null: false
    t.string "selected_model"
    t.string "session_id", null: false
    t.json "source_fingerprint", null: false
    t.string "source_format", null: false
    t.json "source_paths", null: false
    t.string "source_state", null: false
    t.json "summary_payload", null: false
    t.datetime "updated_at", null: false
    t.datetime "updated_at_source"
    t.index ["branch"], name: "index_copilot_sessions_on_branch"
    t.index ["created_at_source"], name: "index_copilot_sessions_on_created_at_source"
    t.index ["repository"], name: "index_copilot_sessions_on_repository"
    t.index ["session_id"], name: "index_copilot_sessions_on_session_id", unique: true
    t.index ["source_format"], name: "index_copilot_sessions_on_source_format"
    t.index ["source_state"], name: "index_copilot_sessions_on_source_state"
    t.index ["updated_at_source"], name: "index_copilot_sessions_on_updated_at_source"
  end

  create_table "history_sync_runs", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.text "degradation_summary"
    t.integer "degraded_count", default: 0, null: false
    t.integer "failed_count", default: 0, null: false
    t.text "failure_summary"
    t.datetime "finished_at"
    t.integer "inserted_count", default: 0, null: false
    t.integer "processed_count", default: 0, null: false
    t.string "running_lock_key"
    t.integer "saved_count", default: 0, null: false
    t.integer "skipped_count", default: 0, null: false
    t.datetime "started_at", null: false
    t.string "status", null: false
    t.datetime "updated_at", null: false
    t.integer "updated_count", default: 0, null: false
    t.index ["running_lock_key"], name: "index_history_sync_runs_on_running_lock_key", unique: true
    t.index ["started_at"], name: "index_history_sync_runs_on_started_at"
    t.index ["status"], name: "index_history_sync_runs_on_status"
  end
end
