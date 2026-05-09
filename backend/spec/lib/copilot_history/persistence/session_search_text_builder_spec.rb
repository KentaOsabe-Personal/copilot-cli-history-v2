require "rails_helper"

RSpec.describe CopilotHistory::Persistence::SessionSearchTextBuilder do
  describe "#call" do
    it "collects conversation body, summary, and issue text only" do
      summary_payload = {
        conversation_summary: {
          preview: "Investigate failing history sync"
        }
      }
      detail_payload = {
        selected_model: "gpt-5.4",
        work_context: {
          cwd: "/workspace/app",
          git_root: "/workspace",
          repository: "octo/copilot-history",
          branch: "feature/search"
        },
        issues: [
          { code: "legacy_partial_mapping", message: "legacy activity mapped partially" }
        ],
        conversation: {
          entries: [
            {
              content: "Find the session with a Redis timeout",
              tool_calls: [
                { name: "shell", arguments_preview: "rg session-full-text-search" }
              ],
              issues: [
                { code: "event_partial_mapping", message: "tool arguments truncated" }
              ]
            }
          ],
          summary: {
            preview: "Find the session with a Redis timeout"
          }
        },
        activity: {
          entries: [
            {
              title: "session-full-text-search activity",
              summary: "loaded context from session-full-text-search"
            }
          ]
        },
        timeline: [
          {
            content: "timeline mentioned session-full-text-search",
            tool_calls: [
              { name: "apply_patch", arguments_preview: "add search_text" }
            ],
            issues: [
              { code: "timeline_degraded", message: "timeline event degraded" }
            ],
            raw_payload: { "secret_internal" => "raw payload must stay out" },
            raw_type: "internal.timestamp"
          }
        ],
        created_at: "2026-05-09T00:00:00Z",
        updated_at: "2026-05-09T00:05:00Z"
      }
      metadata = {
        cwd: "/workspace/app",
        git_root: "/workspace",
        repository: "octo/copilot-history",
        branch: "feature/search",
        selected_model: "gpt-5.4"
      }

      search_text = described_class.new.call(summary_payload:, detail_payload:, metadata:)

      expect(search_text).to include(
        "Investigate failing history sync",
        "Find the session with a Redis timeout",
        "legacy_partial_mapping",
        "legacy activity mapped partially",
        "event_partial_mapping",
        "tool arguments truncated"
      )
      expect(search_text).not_to include(
        "shell",
        "rg session-full-text-search",
        "session-full-text-search activity",
        "loaded context from session-full-text-search",
        "timeline mentioned session-full-text-search",
        "apply_patch",
        "add search_text",
        "/workspace/app",
        "/workspace",
        "octo/copilot-history",
        "feature/search",
        "gpt-5.4",
        "secret_internal",
        "raw payload must stay out",
        "internal.timestamp",
        "2026-05-09"
      )
    end

    it "normalizes whitespace and returns an empty string when no searchable text exists" do
      search_text = described_class.new.call(
        summary_payload: { conversation_summary: { preview: "  hello\n\nworld\t" } },
        detail_payload: { conversation: { entries: [ { content: "hello world" } ] } },
        metadata: { selected_model: nil }
      )
      empty_text = described_class.new.call(summary_payload: {}, detail_payload: {}, metadata: {})

      expect(search_text).to eq("hello world")
      expect(empty_text).to eq("")
    end
  end
end
