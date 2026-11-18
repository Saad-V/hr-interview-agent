import { useState } from 'react';
import { AlertCircle, Download, Loader2 } from 'lucide-react';
import { atsExportService } from '../services/atsExportService';

interface ATSExportButtonProps {
  sessionId: string;
}

export default function ATSExportButton({ sessionId }: ATSExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    try {
      await atsExportService.downloadScorecard(sessionId);
    } catch (exportError) {
      setError(
        exportError instanceof Error
          ? exportError.message
          : 'Could not export this scorecard. Please try again.'
      );
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div>
      <button
        className="primary-action inline-flex items-center gap-2"
        disabled={isExporting}
        onClick={() => void handleExport()}
        type="button"
      >
        {isExporting ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Download className="h-4 w-4" aria-hidden="true" />
        )}
        {isExporting ? 'Preparing export…' : 'Export ATS CSV'}
      </button>
      {error && (
        <p className="mt-2 flex items-center gap-2 text-sm text-danger" role="alert">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
