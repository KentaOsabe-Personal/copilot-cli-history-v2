require "rails_helper"

RSpec.describe HistorySyncRun do
  def valid_attributes
    {
      started_at: Time.zone.parse("2026-04-30 03:00:00"),
      finished_at: Time.zone.parse("2026-04-30 03:01:00"),
      status: "succeeded",
      processed_count: 3,
      inserted_count: 1,
      updated_count: 1,
      saved_count: 2,
      skipped_count: 1,
      failed_count: 0,
      degraded_count: 0
    }
  end

  # 概要・目的: 「accepts canonical terminal statuses with a finished timestamp」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「accepts canonical terminal statuses with a finished timestamp」の条件・入力・操作を実行する。
  # 期待値: canonical terminal statuses with a finished timestamp が受け入れられること。
  it "accepts canonical terminal statuses with a finished timestamp" do
    %w[succeeded failed completed_with_issues].each do |status|
      run = described_class.new(valid_attributes.merge(status: status))

      expect(run).to be_valid
    end
  end

  # 概要・目的: 「accepts a running sync without a finished timestamp」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「accepts a running sync without a finished timestamp」の条件・入力・操作を実行する。
  # 期待値: a running sync without a finished timestamp が受け入れられること。
  it "accepts a running sync without a finished timestamp" do
    run = described_class.new(
      valid_attributes.merge(
        status: "running",
        finished_at: nil,
        running_lock_key: "history-sync"
      )
    )

    expect(run).to be_valid
  end

  # 概要・目的: 「requires a running lock for running status」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「requires a running lock for running status」の条件・入力・操作を実行する。
  # 期待値: a running lock for running status が必須として扱われること。
  it "requires a running lock for running status" do
    run = described_class.new(valid_attributes.merge(status: "running", finished_at: nil, running_lock_key: nil))

    expect(run).not_to be_valid
    expect(run.errors[:running_lock_key]).to be_present
  end

  # 概要・目的: 「rejects a running sync with a finished timestamp」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「rejects a running sync with a finished timestamp」の条件・入力・操作を実行する。
  # 期待値: a running sync with a finished timestamp が拒否されること。
  it "rejects a running sync with a finished timestamp" do
    run = described_class.new(valid_attributes.merge(status: "running", running_lock_key: "history-sync"))

    expect(run).not_to be_valid
    expect(run.errors[:finished_at]).to be_present
  end

  # 概要・目的: 「requires a finished timestamp for terminal statuses」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「requires a finished timestamp for terminal statuses」の条件・入力・操作を実行する。
  # 期待値: a finished timestamp for terminal statuses が必須として扱われること。
  it "requires a finished timestamp for terminal statuses" do
    %w[succeeded failed completed_with_issues].each do |status|
      run = described_class.new(valid_attributes.merge(status: status, finished_at: nil))

      expect(run).not_to be_valid
      expect(run.errors[:finished_at]).to be_present
    end
  end

  # 概要・目的: 「requires terminal statuses to release the running lock」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「requires terminal statuses to release the running lock」の条件・入力・操作を実行する。
  # 期待値: terminal statuses to release the running lock が必須として扱われること。
  it "requires terminal statuses to release the running lock" do
    %w[succeeded failed completed_with_issues].each do |status|
      run = described_class.new(valid_attributes.merge(status: status, running_lock_key: "history-sync"))

      expect(run).not_to be_valid
      expect(run.errors[:running_lock_key]).to be_present
    end
  end

  # 概要・目的: 「rejects unknown statuses」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「rejects unknown statuses」の条件・入力・操作を実行する。
  # 期待値: unknown statuses が拒否されること。
  it "rejects unknown statuses" do
    run = described_class.new(valid_attributes.merge(status: "partial"))

    expect(run).not_to be_valid
    expect(run.errors[:status]).to be_present
  end

  # 概要・目的: 「requires count fields to be non-negative integers」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「requires count fields to be non-negative integers」の条件・入力・操作を実行する。
  # 期待値: count fields to be non-negative integers が必須として扱われること。
  it "requires count fields to be non-negative integers" do
    count_fields = %i[
      processed_count
      inserted_count
      updated_count
      saved_count
      skipped_count
      failed_count
      degraded_count
    ]

    count_fields.each do |field|
      run = described_class.new(valid_attributes.merge(field => -1))

      expect(run).not_to be_valid
      expect(run.errors[field]).to be_present
    end
  end

  # 概要・目的: 「reports invalid count fields without raising from saved count validation」を通じて、DB
  #   保存・validation・一意性制約を検証する。
  # テストケース: 「reports invalid count fields without raising from saved count validation」の条件・入力・操作を実行する。
  # 期待値: 「reports invalid count fields without raising from saved count validation」で示す状態または振る舞いが成立すること。
  it "reports invalid count fields without raising from saved count validation" do
    run = described_class.new(valid_attributes.merge(inserted_count: nil, updated_count: "not-a-number"))

    expect { run.valid? }.not_to raise_error
    expect(run.errors[:inserted_count]).to be_present
    expect(run.errors[:updated_count]).to be_present
  end

  # 概要・目的: 「requires saved count to equal inserted count plus updated count」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「requires saved count to equal inserted count plus updated count」の条件・入力・操作を実行する。
  # 期待値: saved count to equal inserted count plus updated count が必須として扱われること。
  it "requires saved count to equal inserted count plus updated count" do
    run = described_class.new(valid_attributes.merge(inserted_count: 1, updated_count: 2, saved_count: 2))

    expect(run).not_to be_valid
    expect(run.errors[:saved_count]).to be_present
  end

  # 概要・目的: 「stores root failures independently of session rows」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「stores root failures independently of session rows」の条件・入力・操作を実行する。
  # 期待値: root failures independently of session rows が保存されること。
  it "stores root failures independently of session rows" do
    run = described_class.new(
      valid_attributes.merge(
        status: "failed",
        processed_count: 0,
        inserted_count: 0,
        updated_count: 0,
        saved_count: 0,
        failed_count: 1,
        failure_summary: "history root is unreadable"
      )
    )

    expect(run).to be_valid
  end

  # 概要・目的: 「stores partial degradation separately from complete success」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「stores partial degradation separately from complete success」の条件・入力・操作を実行する。
  # 期待値: partial degradation separately from complete success が保存されること。
  it "stores partial degradation separately from complete success" do
    run = described_class.new(
      valid_attributes.merge(
        status: "completed_with_issues",
        degraded_count: 2,
        degradation_summary: "2 sessions degraded"
      )
    )

    expect(run).to be_valid
    expect(run.status).to eq("completed_with_issues")
    expect(run.degraded_count).to eq(2)
  end
end
