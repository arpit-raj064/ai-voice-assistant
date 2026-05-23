import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  CalendarRange, 
  PhoneCall, 
  Clock, 
  Activity, 
  Cpu 
} from 'lucide-react';

export default function Sidebar({ isOpen, toggleSidebar }) {
  const menuItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Appointments', path: '/appointments', icon: CalendarRange },
    { name: 'Call Logs', path: '/call-logs', icon: PhoneCall },
    { name: 'Available Slots', path: '/available-slots', icon: Clock },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-950/80 backdrop-blur-sm lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar Container */}
      <aside 
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-800 bg-slate-900/90 backdrop-blur-md transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Logo */}
        <div className="flex h-20 items-center justify-between px-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-white shadow-glow">
              <Cpu size={20} className="pulse-slow" />
            </div>
            <div>
              <h1 className="font-outfit text-xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                Aria
              </h1>
              <p className="text-[10px] text-brand-400 uppercase tracking-widest font-semibold">AI Receptionist</p>
            </div>
          </div>
          <button 
            onClick={toggleSidebar} 
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
          >
            &times;
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1.5 px-4 py-6 overflow-y-auto">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3.5 rounded-xl px-4 py-3.5 text-sm font-medium transition-all duration-200 group ${
                    isActive
                      ? 'bg-brand-500 text-white shadow-glow'
                      : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
                  }`
                }
              >
                <Icon size={18} className="transition-transform group-hover:scale-110" />
                {item.name}
              </NavLink>
            );
          })}
        </nav>

        {/* System Status Indicators */}
        <div className="p-6 border-t border-slate-800 bg-slate-950/40">
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/50 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={14} className="text-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-slate-300">Receptionist Status</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>AI Voice Core:</span>
                <span className="text-emerald-400 font-medium">Online</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Twilio Gateway:</span>
                <span className="text-emerald-400 font-medium">Active</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>FastAPI Service:</span>
                <span className="text-emerald-400 font-medium">Running</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
