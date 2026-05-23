import api from './api';

export const appointmentService = {
  /**
   * Fetch all appointments (admin view)
   * @param {number} limit 
   * @returns {Promise<{total: number, appointments: Array}>}
   */
  getAll: async (limit = 100) => {
    const response = await api.get(`/appointments/all?limit=${limit}`);
    return response.data;
  },

  /**
   * Check available slots for a given date
   * @param {string} date "YYYY-MM-DD"
   * @returns {Promise<{date: string, available_slots: Array<string>, total_available: number}>}
   */
  getAvailableSlots: async (date) => {
    const response = await api.get(`/appointments/available-slots?date=${date}`);
    return response.data;
  },

  /**
   * Book a new appointment
   * @param {object} bookingData { name: string, phone: string, date: string, time: string }
   * @returns {Promise<object>}
   */
  book: async (bookingData) => {
    const response = await api.post('/appointments/book', bookingData);
    return response.data;
  },

  /**
   * Cancel a confirmed appointment
   * @param {object} cancelData { short_id: string | null, phone: string | null }
   * @returns {Promise<object>}
   */
  cancel: async (cancelData) => {
    const response = await api.post('/appointments/cancel', cancelData);
    return response.data;
  },

  /**
   * Reschedule an existing appointment
   * @param {object} rescheduleData { short_id: string | null, phone: string | null, new_date: string, new_time: string }
   * @returns {Promise<object>}
   */
  reschedule: async (rescheduleData) => {
    const response = await api.post('/appointments/reschedule', rescheduleData);
    return response.data;
  },
};
