import React, { useEffect, useState } from 'react';
import { 
  Search, 
  Calendar, 
  Trash2, 
  Clock, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  Plus,
  User,
  Phone
} from 'lucide-react';
import { appointmentService } from '../services/appointmentService';
import { getLocalDateString } from '../utils/dateUtils';

export default function Appointments() {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Search and filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Modals state
  const [bookingModalOpen, setBookingModalOpen] = useState(false);
  const [rescheduleModalOpen, setRescheduleModalOpen] = useState(false);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);

  // Form states
  const [selectedAppt, setSelectedAppt] = useState(null); // for cancel/reschedule actions
  
  // Booking Form State
  const [bookingForm, setBookingForm] = useState({
    name: '',
    phone: '',
    date: getLocalDateString(),
    time: ''
  });
  const [bookingSlots, setBookingSlots] = useState([]);
  const [loadingBookingSlots, setLoadingBookingSlots] = useState(false);

  // Reschedule Form State
  const [rescheduleForm, setRescheduleForm] = useState({
    new_date: getLocalDateString(),
    new_time: ''
  });
  const [rescheduleSlots, setRescheduleSlots] = useState([]);
  const [loadingRescheduleSlots, setLoadingRescheduleSlots] = useState(false);

  // Fetch appointments list
  const fetchAppointments = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await appointmentService.getAll();
      setAppointments(data.appointments || []);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch appointments from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  // Fetch available slots for Booking Modal when date changes
  useEffect(() => {
    if (bookingModalOpen && bookingForm.date) {
      const getSlots = async () => {
        setLoadingBookingSlots(true);
        try {
          const res = await appointmentService.getAvailableSlots(bookingForm.date);
          setBookingSlots(res.available_slots || []);
          if (res.available_slots && res.available_slots.length > 0) {
            setBookingForm(prev => ({ ...prev, time: res.available_slots[0] }));
          } else {
            setBookingForm(prev => ({ ...prev, time: '' }));
          }
        } catch (e) {
          console.error(e);
        } finally {
          setLoadingBookingSlots(false);
        }
      };
      getSlots();
    }
  }, [bookingForm.date, bookingModalOpen]);

  // Fetch available slots for Reschedule Modal when date changes
  useEffect(() => {
    if (rescheduleModalOpen && rescheduleForm.new_date) {
      const getSlots = async () => {
        setLoadingRescheduleSlots(true);
        try {
          const res = await appointmentService.getAvailableSlots(rescheduleForm.new_date);
          setRescheduleSlots(res.available_slots || []);
          if (res.available_slots && res.available_slots.length > 0) {
            setRescheduleForm(prev => ({ ...prev, new_time: res.available_slots[0] }));
          } else {
            setRescheduleForm(prev => ({ ...prev, new_time: '' }));
          }
        } catch (e) {
          console.error(e);
        } finally {
          setLoadingRescheduleSlots(false);
        }
      };
      getSlots();
    }
  }, [rescheduleForm.new_date, rescheduleModalOpen]);

  // Handle Book appointment form submission
  const handleBookSubmit = async (e) => {
    e.preventDefault();
    if (!bookingForm.name || !bookingForm.phone || !bookingForm.date || !bookingForm.time) {
      alert("All fields are required");
      return;
    }
    try {
      setError(null);
      const res = await appointmentService.book(bookingForm);
      if (res.status === 'booked') {
        alert(res.message);
        setBookingModalOpen(false);
        setBookingForm({
          name: '',
          phone: '',
          date: getLocalDateString(),
          time: ''
        });
        fetchAppointments();
      } else {
        alert(res.message || "Failed to book slot.");
      }
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error connecting to booking system.");
    }
  };

  // Handle Reschedule appointment form submission
  const handleRescheduleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAppt || !rescheduleForm.new_date || !rescheduleForm.new_time) {
      alert("New slot selection is required");
      return;
    }
    try {
      const res = await appointmentService.reschedule({
        short_id: selectedAppt.short_id,
        phone: selectedAppt.phone,
        new_date: rescheduleForm.new_date,
        new_time: rescheduleForm.new_time
      });
      if (res.status === 'rescheduled') {
        alert(res.message);
        setRescheduleModalOpen(false);
        fetchAppointments();
      } else {
        alert(res.message || "Slot was unavailable.");
      }
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error rescheduling booking.");
    }
  };

  // Handle Cancellation submission
  const handleCancelSubmit = async () => {
    if (!selectedAppt) return;
    try {
      const res = await appointmentService.cancel({
        short_id: selectedAppt.short_id,
        phone: selectedAppt.phone
      });
      if (res.status === 'cancelled') {
        alert(res.message);
        setCancelModalOpen(false);
        fetchAppointments();
      } else {
        alert(res.message || "Unable to cancel booking.");
      }
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Error cancelling appointment.");
    }
  };

  // Filter list
  const filteredAppointments = appointments.filter(appt => {
    // Search filter
    const query = searchQuery.toLowerCase();
    const matchesSearch = 
      appt.name.toLowerCase().includes(query) ||
      appt.phone.includes(query) ||
      (appt.short_id && appt.short_id.toLowerCase().includes(query));
    
    // Status filter
    const matchesStatus = 
      statusFilter === 'all' || 
      appt.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header and create button */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="font-outfit text-3xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Manage Appointments
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Browse bookings, schedule new slots, reschedule, or process cancellations.
          </p>
        </div>
        <button
          onClick={() => setBookingModalOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-sm font-semibold text-white shadow-glow transition-all hover:bg-brand-600"
        >
          <Plus size={18} />
          Book Appointment
        </button>
      </div>

      {/* Filter and search layout */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
        {/* Search bar */}
        <div className="relative w-full md:w-96">
          <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search patient, phone number, ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-3 rounded-xl glass-input text-slate-200 text-sm"
          />
        </div>

        {/* Status filters */}
        <div className="flex gap-2 w-full md:w-auto overflow-x-auto self-start md:self-center">
          {['all', 'confirmed', 'cancelled'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-all border ${
                statusFilter === status
                  ? 'bg-brand-500/10 border-brand-500 text-brand-400'
                  : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:bg-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Main listing panel */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <RefreshCw size={24} className="animate-spin text-brand-500" />
            <span className="text-slate-400 text-sm">Syncing booking ledger...</span>
          </div>
        </div>
      ) : error ? (
        <div className="glass-card rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-center">
          <AlertCircle size={32} className="mx-auto text-rose-400 mb-3" />
          <h4 className="font-semibold text-rose-300">Synchronization Error</h4>
          <p className="text-slate-400 text-sm mt-1 mb-4">{error}</p>
          <button 
            onClick={fetchAppointments} 
            className="rounded-xl border border-slate-700 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800"
          >
            Retry Connection
          </button>
        </div>
      ) : filteredAppointments.length === 0 ? (
        <div className="glass-card rounded-2xl border border-slate-800 p-8 text-center text-slate-500 text-sm">
          No appointments found matching filters.
        </div>
      ) : (
        <div className="glass-card rounded-2xl border border-slate-800/80 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/40 text-slate-400 text-xs font-semibold uppercase tracking-wider">
                  <th className="px-6 py-4">Booking ID</th>
                  <th className="px-6 py-4">Client / Patient</th>
                  <th className="px-6 py-4">Date / Time</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm">
                {filteredAppointments.map((appt) => (
                  <tr key={appt.id} className="hover:bg-slate-900/20 transition-colors">
                    <td className="px-6 py-4 font-mono font-bold text-brand-400">
                      {appt.short_id || 'APT-N/A'}
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-200">{appt.name}</div>
                      <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                        <Phone size={11} /> {appt.phone}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-slate-300 font-medium">{appt.date}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{appt.time}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        appt.status === 'confirmed' 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}>
                        {appt.status === 'confirmed' ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                        {appt.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {appt.status === 'confirmed' ? (
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => {
                              setSelectedAppt(appt);
                              setRescheduleForm({
                                new_date: appt.date,
                                new_time: appt.time
                              });
                              setRescheduleModalOpen(true);
                            }}
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/40 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                          >
                            <Calendar size={13} />
                            Reschedule
                          </button>
                          <button
                            onClick={() => {
                              setSelectedAppt(appt);
                              setCancelModalOpen(true);
                            }}
                            className="inline-flex items-center gap-1 rounded-lg border border-rose-900/30 bg-rose-950/20 px-3 py-1.5 text-xs font-medium text-rose-400 hover:bg-rose-900/30 transition-colors"
                          >
                            <Trash2 size={13} />
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-600 italic">No Actions</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: BOOK APPOINTMENT */}
      {bookingModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-glow-lg animate-fadeIn">
            <h3 className="font-outfit text-xl font-bold text-slate-100 flex items-center gap-2 mb-4">
              <Plus className="text-brand-500" /> Book New Appointment
            </h3>
            
            <form onSubmit={handleBookSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Client Name</label>
                <div className="relative">
                  <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. John Doe"
                    value={bookingForm.name}
                    onChange={(e) => setBookingForm(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl glass-input text-slate-200 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Phone Number</label>
                <div className="relative">
                  <Phone size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="tel"
                    required
                    placeholder="e.g. +919876543210"
                    value={bookingForm.phone}
                    onChange={(e) => setBookingForm(prev => ({ ...prev, phone: e.target.value }))}
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl glass-input text-slate-200 text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Date</label>
                  <input
                    type="date"
                    required
                    min={getLocalDateString()}
                    value={bookingForm.date}
                    onChange={(e) => setBookingForm(prev => ({ ...prev, date: e.target.value }))}
                    className="w-full px-3 py-2.5 rounded-xl glass-input text-slate-200 text-sm"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Time Slot</label>
                  {loadingBookingSlots ? (
                    <div className="h-10 flex items-center justify-center text-xs text-slate-500">Checking...</div>
                  ) : bookingSlots.length === 0 ? (
                    <div className="h-10 flex items-center text-xs text-rose-400 font-medium">No slots free</div>
                  ) : (
                    <select
                      value={bookingForm.time}
                      onChange={(e) => setBookingForm(prev => ({ ...prev, time: e.target.value }))}
                      className="w-full px-3 py-2.5 rounded-xl glass-input text-slate-200 text-sm"
                    >
                      {bookingSlots.map(slot => (
                        <option key={slot} value={slot} className="bg-slate-900 text-slate-200">{slot}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              <div className="flex gap-3 pt-4 border-t border-slate-800 mt-6">
                <button
                  type="button"
                  onClick={() => setBookingModalOpen(false)}
                  className="flex-1 rounded-xl border border-slate-800 bg-slate-950/40 py-2.5 text-xs font-semibold text-slate-400 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={bookingSlots.length === 0}
                  className="flex-1 rounded-xl bg-brand-500 py-2.5 text-xs font-semibold text-white shadow-glow hover:bg-brand-600 disabled:opacity-50"
                >
                  Confirm Booking
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: RESCHEDULE */}
      {rescheduleModalOpen && selectedAppt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-glow-lg animate-fadeIn">
            <h3 className="font-outfit text-xl font-bold text-slate-100 flex items-center gap-2 mb-2">
              <Calendar className="text-brand-500" /> Reschedule Appointment
            </h3>
            <p className="text-xs text-slate-400 mb-6">
              Rescheduling booking <strong className="text-brand-400 font-mono">{selectedAppt.short_id}</strong> ({selectedAppt.name})
            </p>

            <form onSubmit={handleRescheduleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">New Date</label>
                  <input
                    type="date"
                    required
                    min={getLocalDateString()}
                    value={rescheduleForm.new_date}
                    onChange={(e) => setRescheduleForm(prev => ({ ...prev, new_date: e.target.value }))}
                    className="w-full px-3 py-2.5 rounded-xl glass-input text-slate-200 text-sm"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">New Time Slot</label>
                  {loadingRescheduleSlots ? (
                    <div className="h-10 flex items-center justify-center text-xs text-slate-500">Checking...</div>
                  ) : rescheduleSlots.length === 0 ? (
                    <div className="h-10 flex items-center text-xs text-rose-400 font-medium">No slots free</div>
                  ) : (
                    <select
                      value={rescheduleForm.new_time}
                      onChange={(e) => setRescheduleForm(prev => ({ ...prev, new_time: e.target.value }))}
                      className="w-full px-3 py-2.5 rounded-xl glass-input text-slate-200 text-sm"
                    >
                      {rescheduleSlots.map(slot => (
                        <option key={slot} value={slot} className="bg-slate-900 text-slate-200">{slot}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              <div className="flex gap-3 pt-4 border-t border-slate-800 mt-6">
                <button
                  type="button"
                  onClick={() => setRescheduleModalOpen(false)}
                  className="flex-1 rounded-xl border border-slate-800 bg-slate-950/40 py-2.5 text-xs font-semibold text-slate-400 hover:bg-slate-800"
                >
                  Keep Original
                </button>
                <button
                  type="submit"
                  disabled={rescheduleSlots.length === 0}
                  className="flex-1 rounded-xl bg-brand-500 py-2.5 text-xs font-semibold text-white shadow-glow hover:bg-brand-600 disabled:opacity-50"
                >
                  Reschedule Slot
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: CANCEL CONFIRMATION */}
      {cancelModalOpen && selectedAppt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-rose-500/20 bg-slate-900 p-6 shadow-glow-lg animate-fadeIn">
            <h3 className="font-outfit text-lg font-bold text-rose-400 flex items-center gap-2 mb-2">
              <Trash2 size={18} /> Cancel Appointment
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed mb-6">
              Are you sure you want to cancel the appointment for <strong className="text-slate-200">{selectedAppt.name}</strong> on <strong className="text-slate-200">{selectedAppt.date}</strong> at <strong className="text-slate-200">{selectedAppt.time}</strong>? This will send a WhatsApp/SMS notification to the client.
            </p>

            <div className="flex gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setCancelModalOpen(false)}
                className="flex-1 rounded-xl border border-slate-800 bg-slate-950/40 py-2.5 text-xs font-semibold text-slate-400 hover:bg-slate-800"
              >
                No, Keep
              </button>
              <button
                type="button"
                onClick={handleCancelSubmit}
                className="flex-1 rounded-xl bg-rose-500 py-2.5 text-xs font-semibold text-white hover:bg-rose-600"
              >
                Yes, Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
