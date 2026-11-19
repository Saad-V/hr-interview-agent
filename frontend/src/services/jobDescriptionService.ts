import api from './api';
import type { JobDescriptionResponse } from '../types/interview';

export interface HRPolicySubmission {
  role_title: string;
  min_salary_lpa: number;
  max_salary_lpa: number;
  max_notice_period_days: number;
  work_location: string;
  role_requirements: string;
}

export const jobDescriptionService = {
  uploadJobDescription: async (sessionId: string, file: File): Promise<JobDescriptionResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<JobDescriptionResponse>(
      `/interview-sessions/${sessionId}/job-description`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  submitHrPolicy: async (
    sessionId: string,
    policy: HRPolicySubmission
  ): Promise<JobDescriptionResponse> => {
    const response = await api.post<JobDescriptionResponse>(
      `/interview-sessions/${sessionId}/hr-policy`,
      policy
    );
    return response.data;
  },
};
