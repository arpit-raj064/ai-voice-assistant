import React, { useEffect, useState } from 'react';
import { 
  Calendar as CalendarIcon, 
  Check, 
  X, 
  Clock, 
  RefreshCw, 
  AlertCircle,
  TrendingUp,
  Sliders
} from 'lucide-react';
import { appointmentService } from '../services/appointmentService';
import { getLocalDateString, getOffsetLocalDateString, formatDateLabel } from '../utils/dateUtils';

// Standard business hours slots matching rules.py
// 9:00 AM to 6:00 PM, 30-min intervals
const ALL_BUSINESS_SLOTS = [
  "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
  "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
  "15:00", "15:30", "16:00", "16:30", "17:00", "17:30"
];

// Helper to format 24h to 12h
function format12h(timeStr) {
  if (!timeStr) return '';
  const [hours, minutes] = timeStr.split(':');
  const h = parseInt(hours, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const displayH = h % 12 || 12;
  return `${displayH}:${minutes} ${ampm}`;
}

export default function AvailableSlots() {
  const [selectedDate, setSelectedDate] = useState(getLocalDateString());
  const [availableSlots, setAvailableSlots] = useState([]);
  const [allAppointments, setAllAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadSlotsData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch available slots for the selected date
      const slotsRes = await appointmentService.getAvailableSlots(selectedDate);
      setAvailableSlots(slotsRes.available_slots || []);

      // 2. Fetch all appointments to map who booked the taken slots
      const apptsRes = await appointmentService.getAll(200);
      setAllAppointments(apptsRes.appointments || []);
    } catch (err) {
      console.error(err);
      setError("Unable to sync timetable schedules from backend router.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSlotsData();
  }, [selectedDate]);

  // Quick tabs for Today & Tomorrow
  const handleDateTabClick = (offset) => {
    setSelectedDate(getOffsetLocalDateString(offset));
  };

  const todayStr = getLocalDateString();
  const tomorrowStr = getOffsetLocalDateString(1);

  // Map each business hour slot to its status (available vs booked)
  const mappedSlots = ALL_BUSINESS_SLOTS.map(timeSlot => {
    const isFree = availableSlots.some(s => s.startsWith(timeSlot));
    // Find if there is an appointment booking on this date/time slot
    const booking = allAppointments.find(
      appt => appt.date === selectedDate && 
      appt.time.startsWith(timeSlot) && 
      appt.status === 'confirmed'
    );

    return {
      time: timeSlot,
      isFree,
      bookingName: booking ? booking.name : null,
      bookingId: booking ? booking.short_id : null
    };
  });

  const totalSlotsCount = mappedSlots.length;
  const freeSlotsCount = mappedSlots.filter(s => s.isFree).length;
  const bookedSlotsCount = totalSlotsCount - freeSlotsCount;

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header and sync status */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="font-outfit text-3xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Schedule & Available Slots
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Real-time visual map of receptionist booking timelines and slot status.
          </p>
        </div>

        <button 
          onClick={loadSlotsData}
          className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-2.5 text-xs font-semibold text-slate-300 transition-all hover:bg-slate-800"
        >
          <RefreshCw size={14} />
          Sync Timetable
        </button>
      </div>

      {/* Date controls and visual overview card */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Date Selector sidebar card */}
        <div className="glass-card rounded-2xl border border-slate-800 p-6 space-y-6">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Quick Navigation</h4>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => handleDateTabClick(0)}
                className={`w-full text-left rounded-xl px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all border ${
                  selectedDate === todayStr
                    ? 'bg-brand-500/15 border-brand-500 text-brand-400'
                    : 'bg-slate-950/40 border-slate-800/80 text-slate-400 hover:bg-slate-800'
                }`}
              >
                📅 Today ({formatDateLabel(todayStr)})
              </button>
              <button
                onClick={() => handleDateTabClick(1)}
                className={`w-full text-left rounded-xl px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all border ${
                  selectedDate === tomorrowStr
                    ? 'bg-brand-500/15 border-brand-500 text-brand-400'
                    : 'bg-slate-950/40 border-slate-800/80 text-slate-400 hover:bg-slate-800'
                }`}
              >
                📅 Tomorrow ({formatDateLabel(tomorrowStr)})
              </button>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Custom Calendar Date</h4>
            <div className="relative">
              <CalendarIcon size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-full pl-10 pr-3 py-2.5 rounded-xl glass-input text-slate-200 text-xs font-semibold"
              />
            </div>
          </div>

          {/* Business rules notes */}
          <div className="rounded-xl bg-slate-950/60 p-4 border border-slate-850 text-[11px] text-slate-400 leading-relaxed space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-slate-300 uppercase tracking-wider">
              <Sliders size={12} className="text-brand-400" /> Business Rules
            </div>
            <p>• Weekdays: 9:00 AM - 6:00 PM</p>
            <p>• Booking interval: 30 minutes</p>
            <p>• Closed: Sundays</p>
          </div>
        </div>

        {/* Timeline visualization (3 cols) */}
        <div className="lg:col-span-3 space-y-6">
          {/* Timeline header counters */}
          <div className="grid grid-cols-3 gap-4">
            <div className="glass-card p-4 rounded-xl border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Total Slots</span>
              <span className="text-xl font-bold font-outfit text-slate-200 mt-1 block">{totalSlotsCount}</span>
            </div>
            <div className="glass-card p-4 rounded-xl border border-emerald-500/10 text-center">
              <span className="text-[10px] text-emerald-500/80 font-bold uppercase tracking-wider block">Free Slots</span>
              <span className="text-xl font-bold font-outfit text-emerald-400 mt-1 block">{freeSlotsCount}</span>
            </div>
            <div className="glass-card p-4 rounded-xl border border-slate-850 text-center">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Booked Slots</span>
              <span className="text-xl font-bold font-outfit text-slate-400 mt-1 block">{bookedSlotsCount}</span>
            </div>
          </div>

          {/* Grid display of slots */}
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <RefreshCw size={24} className="animate-spin text-brand-500" />
                <span className="text-slate-400 text-sm">Compiling daily schedule...</span>
              </div>
            </div>
          ) : error ? (
            <div className="glass-card rounded-2xl border border-rose-500/20 bg-rose-500/5 p-8 text-center text-rose-400">
              <AlertCircle size={28} className="mx-auto mb-2" />
              <p className="text-sm font-semibold">{error}</p>
            </div>
          ) : mappedSlots.length === 0 ? (
            <div className="glass-card rounded-2xl border border-slate-850 p-12 text-center text-slate-500 text-sm">
              The clinic is closed on this date (Sunday or Holiday). No booking slots are active.
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {mappedSlots.map((slot) => (
                <div 
                  key={slot.time}
                  className={`rounded-2xl border p-4 transition-all duration-300 flex flex-col justify-between h-28 relative overflow-hidden ${
                    slot.isFree
                      ? 'border-emerald-500/10 bg-emerald-500/5 hover:border-emerald-500/30 hover:shadow-glow'
                      : 'border-slate-850 bg-slate-900/20 opacity-70'
                  }`}
                >
                  {/* Glowing background blob for active */}
                  {slot.isFree && <div className="absolute top-0 right-0 -mt-2 -mr-2 h-12 w-12 rounded-full bg-emerald-500/5 blur-lg"></div>}
                  
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-400 flex items-center gap-1.5">
                      <Clock size={12} className="text-brand-400" /> {format12h(slot.time)}
                    </span>
                    {slot.isFree ? (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/20" title="Available">
                        <Check size={10} strokeWidth={3} />
                      </span>
                    ) : (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-slate-500 border border-slate-700/50" title="Booked">
                        <X size={10} strokeWidth={3} />
                      </span>
                    )}
                  </div>

                  <div className="mt-4">
                    {slot.isFree ? (
                      <div>
                        <span className="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">Available</span>
                        <p className="text-[9px] text-slate-500 leading-tight">Ready for bookings</p>
                      </div>
                    ) : (
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">Occupied</span>
                        <p className="text-xs font-bold text-slate-300 truncate mt-0.5" title={slot.bookingName || 'Reserved'}>
                          {slot.bookingName || 'Anonymous Booking'}
                        </p>
                        {slot.bookingId && <p className="text-[9px] text-brand-400 font-mono font-medium">{slot.bookingId}</p>}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
