import React, { useEffect, useState } from 'react';
import { 
  Search, 
  PhoneCall, 
  MessageSquareCode, 
  Clock, 
  User, 
  ChevronRight, 
  RefreshCw, 
  Calendar,
  PhoneOff,
  UserX,
  Volume2
} from 'lucide-react';
import { callLogService } from '../services/callLogService';

export default function CallLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLog, setSelectedLog] = useState(null);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await callLogService.getAll();
      setLogs(data.logs || []);
      // Preselect first log if exists for screen layout
      if (data.logs && data.logs.length > 0) {
        setSelectedLog(data.logs[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter(log => {
    const query = searchQuery.toLowerCase();
    return (
      log.caller.includes(query) ||
      log.summary.toLowerCase().includes(query) ||
      (log.status && log.status.toLowerCase().includes(query))
    );
  });

  return (
    <div className="space-y-6 animate-fadeIn h-full flex flex-col">
      {/* Header section */}
      <div>
        <h2 className="font-outfit text-3xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
          Voice Call Interactions
        </h2>
        <p className="text-slate-400 text-sm mt-1">
          Review conversation transcripts and summaries handled by the Aria AI core.
        </p>
      </div>

      {/* Search and refresh tools */}
      <div className="flex gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by phone or log summary..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-3 rounded-xl glass-input text-slate-200 text-sm"
          />
        </div>

        <button 
          onClick={fetchLogs} 
          className="p-3 rounded-xl border border-slate-800 bg-slate-900/40 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Reload logs"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      {loading ? (
        <div className="flex flex-1 items-center justify-center py-20">
          <div className="flex flex-col items-center gap-2">
            <RefreshCw size={24} className="animate-spin text-brand-500" />
            <span className="text-slate-400 text-sm">Decoding Twilio recordings...</span>
          </div>
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="glass-card rounded-2xl border border-slate-800 p-8 text-center text-slate-500 text-sm">
          No voice call interactions found.
        </div>
      ) : (
        /* Split view: Logs list (Left) and Detailed Transcript Drawer (Right) */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          
          {/* Logs Table / List (2 cols) */}
          <div className="lg:col-span-2 glass-card rounded-2xl border border-slate-800/80 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/40 text-slate-400 text-xs font-semibold uppercase tracking-wider">
                    <th className="px-6 py-4">Caller</th>
                    <th className="px-6 py-4">Date / Time</th>
                    <th className="px-6 py-4">Duration</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Summary</th>
                    <th className="px-6 py-4"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-sm">
                  {filteredLogs.map((log) => {
                    const isSelected = selectedLog && selectedLog.id === log.id;
                    return (
                      <tr 
                        key={log.id} 
                        onClick={() => setSelectedLog(log)}
                        className={`cursor-pointer transition-all ${
                          isSelected 
                            ? 'bg-brand-500/10 border-l-2 border-l-brand-500' 
                            : 'hover:bg-slate-900/30'
                        }`}
                      >
                        <td className="px-6 py-4 font-semibold text-slate-300 whitespace-nowrap">
                          {log.caller}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-slate-300">{new Date(log.timestamp).toLocaleDateString()}</div>
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            {new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          </div>
                        </td>
                        <td className="px-6 py-4 font-mono text-slate-400 whitespace-nowrap">
                          {log.duration}s
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                            log.status === 'completed' 
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                              : log.status === 'no-answer'
                              ? 'bg-slate-800 text-slate-400 border border-slate-700/60'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          }`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-xs text-slate-400 max-w-xs truncate">
                          {log.summary}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <ChevronRight size={16} className={`text-slate-600 transition-transform ${isSelected ? 'text-brand-400 translate-x-1' : ''}`} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Transcript Viewer Panel (1 col) */}
          <div className="glass-card rounded-2xl border border-slate-800 p-6 space-y-6">
            {selectedLog ? (
              <>
                {/* Caller identity header */}
                <div className="border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-slate-300 border border-slate-700">
                      {selectedLog.status === 'completed' ? <Volume2 size={18} className="text-cyan-400" /> : <PhoneOff size={18} className="text-slate-500" />}
                    </div>
                    <div>
                      <h4 className="font-outfit font-bold text-slate-200">{selectedLog.caller}</h4>
                      <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mt-0.5">
                        {selectedLog.id} • {selectedLog.duration}s duration
                      </p>
                    </div>
                  </div>
                </div>

                {/* Summary panel */}
                <div>
                  <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">Interactive Summary</h5>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3.5 text-xs text-slate-300 leading-relaxed font-medium">
                    {selectedLog.summary}
                  </div>
                </div>

                {/* Conversation Transcript */}
                <div>
                  <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                    <MessageSquareCode size={13} className="text-brand-400" /> 
                    Live Transcript
                  </h5>
                  
                  {selectedLog.transcript && selectedLog.transcript.length > 0 ? (
                    <div className="space-y-4 max-h-[300px] overflow-y-auto pr-1">
                      {selectedLog.transcript.map((msg, idx) => {
                        const isAssistant = msg.role === 'assistant';
                        return (
                          <div 
                            key={idx} 
                            className={`flex flex-col gap-1 ${isAssistant ? 'items-start' : 'items-end'}`}
                          >
                            <span className="text-[9px] text-slate-500 uppercase tracking-widest font-semibold">
                              {isAssistant ? 'Aria (AI)' : 'Caller'}
                            </span>
                            <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
                              isAssistant 
                                ? 'bg-slate-800 text-slate-200 border border-slate-700/60 rounded-tl-none' 
                                : 'bg-brand-500 text-white rounded-tr-none shadow-glow'
                            }`}>
                              {msg.text}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 text-xs py-10 flex flex-col items-center gap-1">
                      <UserX size={20} className="text-slate-600 mb-1" />
                      No conversation speech recorded.
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center text-slate-500 text-sm py-20">
                Select a call log to view details.
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
}
