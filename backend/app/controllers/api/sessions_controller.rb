module Api
  class SessionsController < ApplicationController
    def index
      criteria = session_list_params.call(params:)
      if criteria.is_a?(CopilotHistory::Api::Types::SessionIndexResult::Invalid)
        return render_error(*error_presenter.from_invalid_session_list_query(invalid_result: criteria))
      end

      result = session_index_query.call(
        from_time: criteria.from_time,
        to_time: criteria.to_time,
        limit: criteria.limit,
        search_term: criteria.search_term
      )

      case result
      when CopilotHistory::Api::Types::SessionIndexResult::Success
        render json: { data: result.data, meta: result.meta }, status: :ok
      else
        raise ArgumentError, "unexpected session index result: #{result.class}"
      end
    end

    def show
      result = session_detail_query.call(session_id: params[:id])

      case result
      when CopilotHistory::Api::Types::SessionLookupResult::Found
        render json: { data: result.detail_payload }, status: :ok
      when CopilotHistory::Api::Types::SessionLookupResult::NotFound
        render_error(*error_presenter.from_not_found(session_id: result.session_id))
      else
        raise ArgumentError, "unexpected session detail result: #{result.class}"
      end
    end

    private

    def render_error(status, payload)
      render json: payload, status: status
    end

    def session_index_query
      @session_index_query ||= CopilotHistory::Api::SessionIndexQuery.new
    end

    def session_detail_query
      @session_detail_query ||= CopilotHistory::Api::SessionDetailQuery.new
    end

    def session_list_params
      @session_list_params ||= CopilotHistory::Api::SessionListParams.new
    end

    def error_presenter
      @error_presenter ||= CopilotHistory::Api::Presenters::ErrorPresenter.new
    end
  end
end
