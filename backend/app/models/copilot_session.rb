class CopilotSession < ApplicationRecord
  SOURCE_FORMATS = %w[current legacy].freeze
  SOURCE_STATES = %w[complete workspace_only degraded].freeze
  COUNT_FIELDS = %i[
    event_count
    message_snapshot_count
    issue_count
    message_count
    activity_count
  ].freeze
  JSON_OBJECT_FIELDS = %i[
    source_paths
    source_fingerprint
    summary_payload
    detail_payload
  ].freeze

  validates :session_id, presence: true, uniqueness: true
  validates :source_format, presence: true, inclusion: { in: SOURCE_FORMATS }
  validates :source_state, presence: true, inclusion: { in: SOURCE_STATES }
  validates :indexed_at, presence: true
  validates :degraded, inclusion: { in: [ true, false ] }
  validates(*COUNT_FIELDS, numericality: { only_integer: true, greater_than_or_equal_to: 0 })
  validates :search_text_version, numericality: { only_integer: true, greater_than_or_equal_to: 0 }

  validate :json_contract_fields_are_objects
  validate :search_text_is_not_nil

  private

  def search_text_is_not_nil
    errors.add(:search_text, :blank) if search_text.nil?
  end

  def json_contract_fields_are_objects
    JSON_OBJECT_FIELDS.each do |field|
      value = public_send(field)

      if value.nil?
        errors.add(field, :blank)
      elsif !value.is_a?(Hash)
        errors.add(field, "must be a JSON object")
      end
    end
  end
end
