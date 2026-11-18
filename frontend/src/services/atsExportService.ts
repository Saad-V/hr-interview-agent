import api from './api';

export const atsExportService = {
  downloadScorecard: async (sessionId: string): Promise<void> => {
    const response = await api.get<Blob>(
      `/interview-sessions/${sessionId}/ats-export`,
      { responseType: 'blob' }
    );
    const objectUrl = URL.createObjectURL(response.data);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = `hr-scorecard-${sessionId}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  },
};
