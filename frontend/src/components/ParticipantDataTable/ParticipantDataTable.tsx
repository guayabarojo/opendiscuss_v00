/**
 * ParticipantDataTable Component
 *
 * Displays participant submission data in a tabular format with filtering,
 * search, and pagination capabilities.
 *
 * Features:
 * - Filter by round number
 * - Search across raw input, summary, and cluster labels
 * - Pagination (20 rows per page)
 * - Responsive design
 * - Loading and error states
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  fetchParticipantData,
  type ParticipantDataRow,
  type ParticipantDataFilters,
} from '../../services/participantDataApi';
import './ParticipantDataTable.css';

export interface ParticipantDataTableProps {
  discussionId: string;
}

export const ParticipantDataTable: React.FC<ParticipantDataTableProps> = ({
  discussionId,
}) => {
  const [data, setData] = useState<ParticipantDataRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState<number>(0);
  const [totalRounds, setTotalRounds] = useState<number>(0);

  // Filters
  const [roundFilter, setRoundFilter] = useState<number | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');

  // Pagination
  const [currentPage, setCurrentPage] = useState<number>(1);
  const rowsPerPage = 20;

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setCurrentPage(1); // Reset to first page on search
    }, 500);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch data when filters or pagination change
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const filters: ParticipantDataFilters = {
        round_num: roundFilter,
        search: debouncedSearch || undefined,
        limit: rowsPerPage,
        offset: (currentPage - 1) * rowsPerPage,
      };

      const response = await fetchParticipantData(discussionId, filters);

      setData(response.data);
      setTotal(response.total);
      setTotalRounds(response.rounds);
      setLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load participant data');
      setLoading(false);
    }
  }, [discussionId, roundFilter, debouncedSearch, currentPage, rowsPerPage]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Pagination helpers
  const totalPages = Math.ceil(total / rowsPerPage);
  const startRow = total === 0 ? 0 : (currentPage - 1) * rowsPerPage + 1;
  const endRow = Math.min(currentPage * rowsPerPage, total);

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handleRoundFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setRoundFilter(value === '' ? undefined : parseInt(value));
    setCurrentPage(1); // Reset to first page
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const truncateText = (text: string | null, maxLength: number = 100): string => {
    if (!text) return 'N/A';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <div className="participant-data-table-container">
      <div className="participant-data-header">
        <h2>Participant Data</h2>
        <p className="participant-data-subtitle">
          Raw submissions, summaries, and cluster assignments for all participants
        </p>
      </div>

      {/* Filters */}
      <div className="participant-data-filters">
        <div className="filter-group">
          <label htmlFor="round-filter">Filter by Round:</label>
          <select
            id="round-filter"
            value={roundFilter === undefined ? '' : roundFilter}
            onChange={handleRoundFilterChange}
            className="filter-select"
          >
            <option value="">All Rounds</option>
            {Array.from({ length: totalRounds }, (_, i) => i + 1).map((round) => (
              <option key={round} value={round}>
                Round {round}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group search-group">
          <label htmlFor="search-input">Search:</label>
          <input
            id="search-input"
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Search in raw input, summary, or cluster label..."
            className="search-input"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="clear-search-btn"
              aria-label="Clear search"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="participant-data-loading">
          <div className="loading-spinner"></div>
          <p>Loading participant data...</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="participant-data-error">
          <div className="error-icon">⚠️</div>
          <p className="error-message">{error}</p>
          <button onClick={loadData} className="retry-btn">
            Retry
          </button>
        </div>
      )}

      {/* Table */}
      {!loading && !error && (
        <>
          <div className="table-wrapper">
            <table className="participant-data-table">
              <thead>
                <tr>
                  <th>Round</th>
                  <th>Participant ID</th>
                  <th>Raw Input</th>
                  <th>Summary</th>
                  <th>Cluster</th>
                  <th>Cluster Label</th>
                  <th>Cluster Size</th>
                </tr>
              </thead>
              <tbody>
                {data.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="no-data">
                      No participant data found
                      {(roundFilter !== undefined || debouncedSearch) &&
                        ' for the selected filters'}
                      .
                    </td>
                  </tr>
                ) : (
                  data.map((row, index) => (
                    <tr key={`${row.round_id}-${row.participant_id}-${index}`}>
                      <td className="round-col">{row.round_num}</td>
                      <td className="participant-col" title={row.participant_id}>
                        {row.participant_id.substring(0, 8)}...
                      </td>
                      <td className="raw-input-col" title={row.raw_input || 'N/A'}>
                        {row.raw_input ? (
                          <span className="text-content">
                            {truncateText(row.raw_input, 100)}
                          </span>
                        ) : (
                          <span className="text-deleted">
                            (Deleted - ephemeral data)
                          </span>
                        )}
                      </td>
                      <td className="summary-col" title={row.summary}>
                        <span className="text-content">
                          {truncateText(row.summary, 100)}
                        </span>
                      </td>
                      <td className="cluster-col" title={row.cluster_id}>
                        {row.cluster_id.substring(0, 8)}...
                      </td>
                      <td className="cluster-label-col" title={row.cluster_label}>
                        <span className="text-content">
                          {truncateText(row.cluster_label, 80)}
                        </span>
                      </td>
                      <td className="cluster-size-col">{row.cluster_size}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.length > 0 && (
            <div className="pagination-controls">
              <div className="pagination-info">
                Showing {startRow}-{endRow} of {total} rows
              </div>

              <div className="pagination-buttons">
                <button
                  onClick={handlePreviousPage}
                  disabled={currentPage === 1}
                  className="pagination-btn"
                  aria-label="Previous page"
                >
                  Previous
                </button>

                <span className="page-indicator">
                  Page {currentPage} of {totalPages}
                </span>

                <button
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                  className="pagination-btn"
                  aria-label="Next page"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ParticipantDataTable;
