import React, { useEffect, useState } from 'react';
import { Menu, Clock, Radio, ShieldCheck } from 'lucide-react';
import api from '../services/api';

export default function Header({ toggleSidebar }) {
  const [time, setTime] = useState(new Date());
  const [activeCalls, setActiveCalls] = useState(0);

  useEffect(() => {
    // Clock tick
    const timer = setInterval(() => setTime(new Date()), 1000);
    
    // Fetch active calls count from backend `/voice/status` endpoint
    const fetchStatus = async () => {
      try {
        const response = await api.get('/voice/status');
        if (response.data && typeof response.data.active_calls !== 'undefined') {
          setActiveCalls(response.data.active_calls);
        }
      } catch (err) {
        // Fallback silently if offline or endpoint error
      }
    };

    fetchStatus();
    const statusInterval = setInterval(fetchStatus, 15000); // refresh every 15s

    return () => {
      clearInterval(timer);
      clearInterval(statusInterval);
    };
  }, []);

  const formattedDate = time.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  const formattedTime = time.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <header className="flex h-20 items-center justify-between border-b border-slate-800 bg-slate-900/60 px-6 backdrop-blur-md">
      {/* Left: Mobile Toggle & Title */}
      <div className="flex items-center gap-4">
        <button 
          onClick={toggleSidebar} 
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
        >
          <Menu size={20} />
        </button>
        <div className="hidden sm:block">
          <h2 className="font-outfit text-sm font-semibold text-slate-300">Operational Console</h2>
          <p className="text-xs text-slate-500">Domain Adaptive Assistant Dashboard</p>
        </div>
      </div>

      {/* Right: Info widgets */}
      <div className="flex items-center gap-4 md:gap-6">
        {/* Active Calls Indicator */}
        <div className="flex items-center gap-2 rounded-xl bg-slate-800/40 px-3 py-1.5 border border-slate-800">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${activeCalls > 0 ? 'bg-amber-400' : 'bg-emerald-400'}`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${activeCalls > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
          </span>
          <span className="text-xs font-medium text-slate-300">
            {activeCalls > 0 ? `${activeCalls} Active Call(s)` : 'Line Idle'}
          </span>
        </div>

        {/* Date & Time display */}
        <div className="hidden md:flex items-center gap-2.5 text-xs text-slate-400 bg-slate-900/80 px-3.5 py-1.5 rounded-xl border border-slate-800">
          <Clock size={14} className="text-brand-400" />
          <span className="font-medium text-slate-300">{formattedDate}</span>
          <span className="text-slate-600">|</span>
          <span className="font-mono text-brand-300">{formattedTime}</span>
        </div>

        {/* User profile capsule */}
        <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-1.5 pr-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/20 text-brand-300 font-semibold text-xs border border-brand-500/30">
            AD
          </div>
          <div className="text-left">
            <p className="text-[11px] font-semibold leading-tight text-slate-200">Admin Staff</p>
            <p className="text-[9px] leading-tight text-slate-500">Scheduling Agent</p>
          </div>
        </div>
      </div>
    </header>
  );
}
