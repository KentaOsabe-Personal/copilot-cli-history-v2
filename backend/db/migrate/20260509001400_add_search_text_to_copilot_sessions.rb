class AddSearchTextToCopilotSessions < ActiveRecord::Migration[8.1]
  def up
    add_column :copilot_sessions, :search_text, :mediumtext
    CopilotSession.reset_column_information
    CopilotSession.where(search_text: nil).update_all(search_text: "")
    change_column_null :copilot_sessions, :search_text, false
  end

  def down
    remove_column :copilot_sessions, :search_text
  end
end
