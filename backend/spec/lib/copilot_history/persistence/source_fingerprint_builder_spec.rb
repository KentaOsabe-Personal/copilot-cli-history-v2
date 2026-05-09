require "rails_helper"

RSpec.describe CopilotHistory::Persistence::SourceFingerprintBuilder do
  around do |example|
    Dir.mktmpdir("source-fingerprint") do |dir|
      @tmpdir = Pathname.new(dir)
      example.run
    end
  end

  # 概要・目的: 「returns a complete deterministic fingerprint for readable artifacts」を通じて、reader と fixture
  #   の読取・劣化時の扱いを検証する。
  # テストケース: 「returns a complete deterministic fingerprint for readable artifacts」の条件・入力・操作を実行する。
  # 期待値: a complete deterministic fingerprint for readable artifacts を返すこと。
  it "returns a complete deterministic fingerprint for readable artifacts" do
    path = @tmpdir.join("events.jsonl")
    path.write("one\n")
    mtime = Time.zone.parse("2026-04-30 03:00:00").to_time
    File.utime(mtime, mtime, path)

    first = described_class.new.call(source_paths: { events: path })
    second = described_class.new.call(source_paths: { events: path })

    expect(first).to eq(second)
    expect(first).to include(
      "complete" => true,
      "artifacts" => {
        "events" => include(
          "path" => path.to_s,
          "mtime" => "2026-04-30T03:00:00Z",
          "size" => 4,
          "status" => "ok"
        )
      }
    )
  end

  # 概要・目的: 「changes when source metadata changes」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
  # テストケース: 「changes when source metadata changes」の条件・入力・操作を実行する。
  # 期待値: 「changes when source metadata changes」で示す状態または振る舞いが成立すること。
  it "changes when source metadata changes" do
    path = @tmpdir.join("workspace.yaml")
    path.write("cwd: /work\n")
    original = described_class.new.call(source_paths: { workspace: path })

    path.write("cwd: /work\nmodel: gpt-5\n")
    mtime = Time.zone.parse("2026-04-30 03:05:00").to_time
    File.utime(mtime, mtime, path)
    changed = described_class.new.call(source_paths: { workspace: path })

    expect(changed).not_to eq(original)
    expect(changed.dig("artifacts", "workspace", "size")).not_to eq(original.dig("artifacts", "workspace", "size"))
  end

  # 概要・目的: 「marks missing artifacts as incomplete without raising」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
  # テストケース: 「marks missing artifacts as incomplete without raising」の条件・入力・操作を実行する。
  # 期待値: 「marks missing artifacts as incomplete without raising」で示す状態または振る舞いが成立すること。
  it "marks missing artifacts as incomplete without raising" do
    missing_path = @tmpdir.join("missing.json")

    fingerprint = described_class.new.call(source_paths: { source: missing_path })

    expect(fingerprint).to include("complete" => false)
    expect(fingerprint.dig("artifacts", "source")).to include(
      "path" => missing_path.to_s,
      "mtime" => nil,
      "size" => nil,
      "status" => "missing"
    )
  end

  # 概要・目的: 「marks artifacts deleted between existence and stat checks as missing」を通じて、reader と fixture
  #   の読取・劣化時の扱いを検証する。
  # テストケース: 「marks artifacts deleted between existence and stat checks as missing」の条件・入力・操作を実行する。
  # 期待値: 「marks artifacts deleted between existence and stat checks as missing」で示す状態または振る舞いが成立すること。
  it "marks artifacts deleted between existence and stat checks as missing" do
    deleted_path = @tmpdir.join("deleted-during-stat.json")
    deleted_path.write("{}")
    allow_any_instance_of(Pathname).to receive(:stat).and_raise(Errno::ENOENT)

    fingerprint = described_class.new.call(source_paths: { source: deleted_path })

    expect(fingerprint).to include("complete" => false)
    expect(fingerprint.dig("artifacts", "source")).to include(
      "path" => deleted_path.to_s,
      "mtime" => nil,
      "size" => nil,
      "status" => "missing"
    )
  end

  # 概要・目的: 「marks unreadable artifacts as incomplete without raising」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
  # テストケース: 「marks unreadable artifacts as incomplete without raising」の条件・入力・操作を実行する。
  # 期待値: 「marks unreadable artifacts as incomplete without raising」で示す状態または振る舞いが成立すること。
  it "marks unreadable artifacts as incomplete without raising" do
    unreadable_path = @tmpdir.join("unreadable.json")
    unreadable_path.write("{}")
    allow_any_instance_of(Pathname).to receive(:stat).and_raise(Errno::EACCES)

    fingerprint = described_class.new.call(source_paths: { source: unreadable_path })

    expect(fingerprint).to include("complete" => false)
    expect(fingerprint.dig("artifacts", "source")).to include(
      "path" => unreadable_path.to_s,
      "mtime" => nil,
      "size" => nil,
      "status" => "unreadable"
    )
  end
end
