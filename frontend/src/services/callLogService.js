// Mock call logs since there is no backend DB for call logging yet.
// In the future, these can easily fetch from 'GET /voice/logs' or similar endpoints.
const MOCK_CALL_LOGS = [
  {
    id: "call-1",
    caller: "+91 98765 43210",
    timestamp: "2026-05-22T14:30:15Z",
    duration: 112, // in seconds
    status: "completed", // completed, failed, busy, no-answer
    type: "inbound",
    summary: "Patient Amit Kumar booked an appointment for May 24 at 10:00 AM. System sent WhatsApp confirmation.",
    transcript: [
      { role: "assistant", text: "Hello! Thank you for calling. This is Aria, your virtual receptionist. How may I assist you today?" },
      { role: "user", text: "Hi, I'd like to book an appointment with Dr. Sharma for this Sunday, May 24th, in the morning." },
      { role: "assistant", text: "I can help with that. Let me check the available slots for Sunday, May 24th. We have slots available at 9:00 AM, 9:30 AM, and 10:00 AM. Which one would you prefer?" },
      { role: "user", text: "Let's go with 10:00 AM. That works best." },
      { role: "assistant", text: "Great. May I have your name and registered phone number to confirm the booking?" },
      { role: "user", text: "My name is Amit Kumar and my phone number is +91 98765 43210." },
      { role: "assistant", text: "Perfect. Appointment confirmed for Amit Kumar on 2026-05-24 at 10:00 AM. Your booking ID is APT-1049. I've also sent you a WhatsApp confirmation with your booking details. Is there anything else I can help you with?" },
      { role: "user", text: "No, that's all. Thank you!" },
      { role: "assistant", text: "Thank you for calling. Have a wonderful day — goodbye!" }
    ]
  },
  {
    id: "call-2",
    caller: "+91 87654 32109",
    timestamp: "2026-05-22T12:15:00Z",
    duration: 85,
    status: "completed",
    type: "inbound",
    summary: "Patient Priya Roy called to cancel appointment APT-3829. Cancellation succeeded, system sent WhatsApp notification.",
    transcript: [
      { role: "assistant", text: "Hello! Thank you for calling. This is Aria, your virtual receptionist. How may I assist you today?" },
      { role: "user", text: "Hello, I need to cancel my appointment. My booking ID is APT-3829." },
      { role: "assistant", text: "Let me check that booking for you. Yes, I see a confirmed appointment for Priya Roy on May 23rd at 11:30 AM. Would you like me to cancel this booking?" },
      { role: "user", text: "Yes, please cancel it. I have some other commitments." },
      { role: "assistant", text: "Your appointment on 2026-05-23 at 11:30 AM has been successfully cancelled. A WhatsApp confirmation has been sent to you. We hope to see you again soon." },
      { role: "user", text: "Thank you, bye." },
      { role: "assistant", text: "You're welcome. Have a wonderful day — goodbye!" }
    ]
  },
  {
    id: "call-3",
    caller: "+91 76543 21098",
    timestamp: "2026-05-22T10:05:42Z",
    duration: 145,
    status: "completed",
    type: "inbound",
    summary: "Caller attempted to book a slot at 11:00 AM on May 22 (today), which was taken. Assistant suggested alternatives and rescheduled them to 2:00 PM.",
    transcript: [
      { role: "assistant", text: "Hello! Thank you for calling. This is Aria, your virtual receptionist. How may I assist you today?" },
      { role: "user", text: "Hi, can I get a doctor's checkup today around 11:00 AM?" },
      { role: "assistant", text: "Sorry, 11:00 AM on May 22nd is already booked. Nearest available slots are today at 2:00 PM, 2:30 PM, or 3:00 PM. Do any of these work for you?" },
      { role: "user", text: "Yes, 2:00 PM works." },
      { role: "assistant", text: "Understood. Please provide your name and phone number to finalize your scheduling." },
      { role: "user", text: "Rohan Sen, phone is +91 76543 21098." },
      { role: "assistant", text: "Appointment confirmed for Rohan Sen on 2026-05-22 at 2:00 PM. Your booking ID is APT-8821. An SMS confirmation has been sent to you. Thank you!" }
    ]
  },
  {
    id: "call-4",
    caller: "+91 99887 76655",
    timestamp: "2026-05-21T16:45:10Z",
    duration: 35,
    status: "no-answer",
    type: "outbound",
    summary: "System outbound reminder failed. Caller did not pick up after several rings.",
    transcript: []
  },
  {
    id: "call-5",
    caller: "+91 88776 65544",
    timestamp: "2026-05-21T15:20:00Z",
    duration: 62,
    status: "completed",
    type: "inbound",
    summary: "General enquiry about opening hours and location. Assistant informed standard hours are 9 AM - 6 PM, Mon-Sat.",
    transcript: [
      { role: "assistant", text: "Hello! Thank you for calling. This is Aria, your virtual receptionist. How may I assist you today?" },
      { role: "user", text: "What are your opening hours and are you open on Sundays?" },
      { role: "assistant", text: "We are open Monday through Saturday from 9:00 AM to 6:00 PM. We are closed on Sundays. Is there anything else I can help you find?" },
      { role: "user", text: "No, that's what I wanted. Thank you." },
      { role: "assistant", text: "Thank you for calling. Have a great day!" }
    ]
  }
];

export const callLogService = {
  /**
   * Get list of all call logs
   * When the backend is ready, this will perform an api.get('/voice/logs')
   */
  getAll: async () => {
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 600));
    return {
      total: MOCK_CALL_LOGS.length,
      logs: [...MOCK_CALL_LOGS],
    };
  },

  /**
   * Get single call log by ID
   */
  getById: async (id) => {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const log = MOCK_CALL_LOGS.find(l => l.id === id);
    if (!log) throw new Error("Call log not found");
    return log;
  }
};
