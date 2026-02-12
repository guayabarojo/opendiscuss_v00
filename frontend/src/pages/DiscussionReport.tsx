import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { discussionApi } from '../services/discussionApi';
import { FlowRenderer } from '../components/SankeyDiagram/FlowRenderer';
import { ClusteringInspectorModal } from '../components/ClusteringInspectorModal';
import type { DiscussionReport } from '../types/api';

interface SankeyNode {
  id: string;
  name: string;
  value: number;
  round: number;
  cluster_id: string;
  percentage: number;
  color: string;
}

interface SankeyLink {
  sourceClusterId: string;
  targetClusterId: string;
  value: number;
  flow_id: string;
}

/**
 * DiscussionReport Component
 *
 * Renders a single-column (or multi-column) Sankey diagram showing:
 * - Discussion metadata
 * - All questions
 * - Thought spaces with participant proportions
 * - Flow of participants between rounds (if multi-round)
 *
 * Uses D3.js for visualization with interactive hover effects.
 * Includes download report button for JSON export.
 */
export default function DiscussionReport() {
  const { discussionId } = useParams<{ discussionId: string }>();
  const [report, setReport] = useState<DiscussionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<SankeyNode | null>(null);
  const [hoveredLink, setHoveredLink] = useState<SankeyLink | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 1200, height: 600 });
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Fetch report
  useEffect(() => {
    if (!discussionId) return;

    const fetchReport = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await discussionApi.getReport(discussionId);
        setReport(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load discussion report');
        console.error('Error fetching report:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [discussionId]);

  // Handle responsive sizing
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        // Height scales with number of nodes and rounds
        const height = Math.max(
          600,
          (report?.sankey_diagram.columns.reduce(
            (sum, col) => sum + col.thought_spaces.length,
            0
          ) || 10) * 40
        );
        setDimensions({ width, height });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [report]);

  const handleDownloadReport = () => {
    if (!report) return;

    const dataStr = JSON.stringify(report, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `discussion-${report.discussion_id}-report.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="discussion-report loading">
        <div className="spinner"></div>
        <p>Loading discussion report...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="discussion-report error">
        <h2>Error Loading Report</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="discussion-report empty">
        <p>No report data available</p>
      </div>
    );
  }

  return (
    <div className="discussion-report">
      <header className="report-header">
        <h1>Discussion Report</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={handleDownloadReport} className="download-btn">
            Download Report (JSON)
          </button>
          {import.meta.env.DEV && (
            <button
              onClick={() => setInspectorOpen(true)}
              className="download-btn"
              style={{ backgroundColor: '#f59e0b' }}
            >
              🔍 Inspect Clustering
            </button>
          )}
        </div>
      </header>

      <section className="report-metadata">
        <h2>Discussion Metadata</h2>
        <div className="metadata-grid">
          <div className="metadata-item">
            <label>Total Rounds:</label>
            <span>{report.metadata.total_rounds}</span>
          </div>
          <div className="metadata-item">
            <label>Total Participants:</label>
            <span>{report.metadata.total_participants}</span>
          </div>
          <div className="metadata-item">
            <label>Duration:</label>
            <span>{report.metadata.duration_minutes.toFixed(1)} minutes</span>
          </div>
        </div>
      </section>

      <section className="report-questions">
        <h2>Discussion Questions</h2>
        <ol className="questions-list">
          {report.metadata.questions.map((question, idx) => (
            <li key={idx}>
              <strong>Round {idx + 1}:</strong> {question}
            </li>
          ))}
        </ol>
      </section>

      <section className="report-visualization">
        <h2>Thought Space Flow</h2>
        <p className="visualization-description">
          {report.metadata.total_rounds === 1
            ? 'Single round discussion showing thought space distribution.'
            : `Multi-round discussion showing participant movement across ${report.metadata.total_rounds} rounds. Hover over nodes and flows to see details.`}
        </p>
        <div ref={containerRef} className="sankey-container">
          <FlowRenderer
            columns={report.sankey_diagram.columns}
            flows={report.sankey_diagram.flows}
            width={dimensions.width}
            height={dimensions.height}
            onNodeHover={setHoveredNode}
            onLinkHover={setHoveredLink}
          />
        </div>
        {hoveredNode && (
          <div className="node-tooltip">
            <h4>{hoveredNode.name}</h4>
            <p>
              <strong>Round:</strong> {hoveredNode.round}
            </p>
            <p>
              <strong>Participants:</strong> {hoveredNode.value} (
              {hoveredNode.percentage.toFixed(1)}%)
            </p>
          </div>
        )}
        {hoveredLink && (
          <div className="link-tooltip">
            <h4>Participant Flow</h4>
            <p>
              <strong>Participants:</strong> {hoveredLink.value}
            </p>
            <p className="tooltip-detail">
              Movement between thought spaces across rounds
            </p>
          </div>
        )}
      </section>

      <style>{`
        .discussion-report {
          max-width: 1200px;
          margin: 0 auto;
          padding: 2rem;
          font-family: system-ui, -apple-system, sans-serif;
        }

        .report-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 2rem;
        }

        .report-header h1 {
          font-size: 2rem;
          font-weight: 600;
          margin: 0;
        }

        .download-btn {
          padding: 0.75rem 1.5rem;
          background: #007bff;
          color: white;
          border: none;
          border-radius: 0.375rem;
          font-size: 1rem;
          cursor: pointer;
          transition: background 0.2s;
        }

        .download-btn:hover {
          background: #0056b3;
        }

        .report-metadata,
        .report-questions,
        .report-visualization {
          margin-bottom: 2rem;
          padding: 1.5rem;
          background: #f8f9fa;
          border-radius: 0.5rem;
        }

        .report-metadata h2,
        .report-questions h2,
        .report-visualization h2 {
          font-size: 1.5rem;
          font-weight: 600;
          margin-top: 0;
          margin-bottom: 1rem;
        }

        .metadata-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
        }

        .metadata-item {
          display: flex;
          flex-direction: column;
        }

        .metadata-item label {
          font-weight: 600;
          color: #6c757d;
          font-size: 0.875rem;
          margin-bottom: 0.25rem;
        }

        .metadata-item span {
          font-size: 1.25rem;
          color: #212529;
        }

        .questions-list {
          list-style-position: inside;
          padding-left: 0;
        }

        .questions-list li {
          padding: 0.75rem;
          margin-bottom: 0.5rem;
          background: white;
          border-radius: 0.375rem;
          line-height: 1.5;
        }

        .questions-list strong {
          color: #007bff;
        }

        .visualization-description {
          margin-bottom: 1rem;
          color: #6c757d;
          font-size: 0.9375rem;
          line-height: 1.5;
        }

        .sankey-container {
          min-height: 500px;
          background: white;
          border-radius: 0.375rem;
          padding: 1rem;
          position: relative;
          overflow-x: auto;
        }

        .node-tooltip,
        .link-tooltip {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: rgba(0, 0, 0, 0.9);
          color: white;
          padding: 1rem;
          border-radius: 0.5rem;
          pointer-events: none;
          z-index: 1000;
          max-width: 280px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
          animation: tooltipFadeIn 0.2s ease;
        }

        @keyframes tooltipFadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .node-tooltip h4,
        .link-tooltip h4 {
          margin: 0 0 0.5rem 0;
          font-size: 1rem;
          font-weight: 600;
          border-bottom: 1px solid rgba(255, 255, 255, 0.2);
          padding-bottom: 0.5rem;
        }

        .node-tooltip p,
        .link-tooltip p {
          margin: 0.25rem 0;
          font-size: 0.875rem;
        }

        .tooltip-detail {
          opacity: 0.8;
          font-size: 0.8125rem;
        }

        .loading,
        .error,
        .empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 400px;
          text-align: center;
        }

        .spinner {
          width: 50px;
          height: 50px;
          border: 4px solid #f3f3f3;
          border-top: 4px solid #007bff;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 1rem;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        .error {
          color: #dc3545;
        }

        /* Responsive Design */
        @media (max-width: 768px) {
          .report-header {
            flex-direction: column;
            gap: 1rem;
            align-items: flex-start;
          }

          .metadata-grid {
            grid-template-columns: 1fr;
          }

          .node-tooltip,
          .link-tooltip {
            left: 10px;
            right: 10px;
            bottom: 10px;
            max-width: none;
          }
        }
      `}</style>
      {inspectorOpen && (
        <ClusteringInspectorModal
          discussionId={discussionId!}
          onClose={() => setInspectorOpen(false)}
        />
      )}
    </div>
  );
}
