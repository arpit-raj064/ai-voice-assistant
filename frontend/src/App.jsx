import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import Dashboard from './pages/Dashboard';
import Appointments from './pages/Appointments';
import CallLogs from './pages/CallLogs';
import AvailableSlots from './pages/AvailableSlots';

export default function App() {
  return (
    <Router>
      <DashboardLayout>
        <Routes>
          {/* Default redirect to Dashboard */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          
          {/* Main dashboard console routes */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/appointments" element={<Appointments />} />
          <Route path="/call-logs" element={<CallLogs />} />
          <Route path="/available-slots" element={<AvailableSlots />} />
          
          {/* Fallback to Dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </DashboardLayout>
    </Router>
  );
}
