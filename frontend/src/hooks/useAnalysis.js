import { useState, useEffect } from 'react';
import { apiService } from '../services/api';

export const useAnalysis = (analysisId) => {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('pending');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!analysisId) return;

    const pollStatus = async () => {
      try {
        const statusData = await apiService.getAnalysisStatus(analysisId);

        setProgress(statusData.progress);
        setStatus(statusData.status);
        setMessage(statusData.message || '');

        // Продолжаем опрос если не завершено
        if (statusData.status !== 'completed' && statusData.status !== 'failed') {
          setTimeout(pollStatus, 2000);
        }
      } catch (error) {
        console.error('Error polling analysis status:', error);
        setTimeout(pollStatus, 5000); // Повтор через 5 сек при ошибке
      }
    };

    pollStatus();
  }, [analysisId]);

  return { progress, status, message };
};