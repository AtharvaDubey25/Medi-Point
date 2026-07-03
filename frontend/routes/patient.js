const express = require('express');
const router = express.Router();
const axios = require('axios');

const authHeaders = (req) => ({
  headers: { Authorization: `Bearer ${req.cookies.token}` },
});

const getApiBase = (req) => req.app.locals.apiBase;

router.use((req, res, next) => {
  if (!req.cookies.token) return res.redirect('/login');
  const user = req.currentUser;
  if (user?.role !== 'PATIENT') return res.redirect('/');
  next();
});

router.get('/dashboard', async (req, res) => {
  try {
    const [aptRes, doctorsRes] = await Promise.all([
      axios.get(`${getApiBase(req)}/appointments/my`, authHeaders(req)),
      axios.get(`${getApiBase(req)}/doctors/search`, authHeaders(req)),
    ]);
    res.render('patient/dashboard', {
      appointments: aptRes.data.appointments,
      doctors: doctorsRes.data,
    });
  } catch (err) {
    res.render('patient/dashboard', { appointments: [], doctors: [] });
  }
});

router.get('/doctors', async (req, res) => {
  try {
    const spec = req.query.specialization || '';
    const response = await axios.get(`${getApiBase(req)}/doctors/search`, {
      ...authHeaders(req),
      params: { specialization: spec },
    });
    res.render('patient/doctors', { doctors: response.data, specialization: spec });
  } catch (err) {
    res.render('patient/doctors', { doctors: [], specialization: '' });
  }
});

router.get('/doctors/:id/slots', async (req, res) => {
  try {
    let { date } = req.query;
    if (!date) {
      date = new Date().toISOString().slice(0, 10);
      return res.redirect(`/patient/doctors/${req.params.id}/slots?date=${date}`);
    }
    const [docRes, slotsRes] = await Promise.all([
      axios.get(`${getApiBase(req)}/doctors/${req.params.id}`, authHeaders(req)),
      axios.get(`${getApiBase(req)}/doctors/${req.params.id}/slots`, {
        ...authHeaders(req),
        params: { date },
      }),
    ]);
    res.render('patient/slots', {
      doctor: docRes.data,
      slots: slotsRes.data,
      date: date || '',
    });
  } catch (err) {
    res.redirect('/patient/doctors');
  }
});

router.get('/book/:doctorId', async (req, res) => {
  try {
    const docRes = await axios.get(`${getApiBase(req)}/doctors/${req.params.doctorId}`, authHeaders(req));
    res.render('patient/book', {
      doctor: docRes.data,
      date: req.query.date || '',
      time: req.query.time || '',
      error: null,
    });
  } catch (err) {
    res.redirect('/patient/doctors');
  }
});

router.post('/book', async (req, res) => {
  try {
    await axios.post(`${getApiBase(req)}/appointments/book`, req.body, authHeaders(req));
    res.redirect('/patient/dashboard');
  } catch (err) {
    const error = err.response?.data?.detail || 'Booking failed';
    try {
      const docRes = await axios.get(`${getApiBase(req)}/doctors/${req.body.doctor_id}`, authHeaders(req));
      return res.render('patient/book', {
        doctor: docRes.data,
        date: req.body.appointment_date,
        time: req.body.start_time,
        error,
      });
    } catch (_) {
      return res.redirect('/patient/doctors');
    }
  }
});

router.post('/appointments/:id/cancel', async (req, res) => {
  try {
    await axios.post(`${getApiBase(req)}/appointments/${req.params.id}/cancel`, null, {
      ...authHeaders(req),
      params: { reason: req.body.reason || '' },
    });
    res.redirect('/patient/dashboard');
  } catch (err) {
    res.redirect('/patient/dashboard');
  }
});

router.get('/appointments/:id/symptoms', async (req, res) => {
  res.render('patient/symptoms', { appointmentId: req.params.id, error: null });
});

router.post('/appointments/:id/symptoms', async (req, res) => {
  try {
    await axios.post(
      `${getApiBase(req)}/symptoms/appointment/${req.params.id}`,
      { symptoms: req.body.symptoms },
      authHeaders(req),
    );
    res.redirect('/patient/dashboard');
  } catch (err) {
    const error = err.response?.data?.detail || 'Failed to submit symptoms';
    res.render('patient/symptoms', { appointmentId: req.params.id, error });
  }
});

router.get('/appointments/:id/summary', async (req, res) => {
  try {
    const response = await axios.get(
      `${getApiBase(req)}/symptoms/appointment/${req.params.id}/post-visit-summary`,
      authHeaders(req),
    );
    res.render('patient/summary', { data: response.data, appointmentId: req.params.id });
  } catch (err) {
    res.redirect('/patient/dashboard');
  }
});

router.get('/appointments/:appointmentId/reschedule/slots', async (req, res) => {
  try {
    let { date } = req.query;
    if (!date) {
      date = new Date().toISOString().slice(0, 10);
      return res.redirect(`/patient/appointments/${req.params.appointmentId}/reschedule/slots?date=${date}`);
    }
    const aptRes = await axios.get(`${getApiBase(req)}/appointments/${req.params.appointmentId}`, authHeaders(req));
    const appointment = aptRes.data;
    const doctorId = appointment.doctor_id;

    const [docRes, slotsRes] = await Promise.all([
      axios.get(`${getApiBase(req)}/doctors/${doctorId}`, authHeaders(req)),
      axios.get(`${getApiBase(req)}/doctors/${doctorId}/slots`, {
        ...authHeaders(req),
        params: { date },
      }),
    ]);

    res.render('patient/reschedule-slots', {
      appointment,
      doctor: docRes.data,
      slots: slotsRes.data,
      date: date || '',
    });
  } catch (err) {
    res.redirect('/patient/dashboard');
  }
});

router.get('/appointments/:appointmentId/reschedule/confirm', async (req, res) => {
  try {
    const { date, time } = req.query;
    const aptRes = await axios.get(`${getApiBase(req)}/appointments/${req.params.appointmentId}`, authHeaders(req));
    const appointment = aptRes.data;
    const docRes = await axios.get(`${getApiBase(req)}/doctors/${appointment.doctor_id}`, authHeaders(req));
    
    res.render('patient/reschedule-confirm', {
      appointment,
      doctor: docRes.data,
      date,
      time,
      error: null,
    });
  } catch (err) {
    res.redirect('/patient/dashboard');
  }
});

router.post('/appointments/:appointmentId/reschedule/confirm', async (req, res) => {
  const { date, time } = req.body;
  try {
    await axios.put(
      `${getApiBase(req)}/appointments/${req.params.appointmentId}/reschedule`,
      {
        appointment_date: date,
        start_time: time,
      },
      authHeaders(req),
    );
    res.redirect('/patient/dashboard');
  } catch (err) {
    const error = err.response?.data?.detail || 'Rescheduling failed';
    try {
      const aptRes = await axios.get(`${getApiBase(req)}/appointments/${req.params.appointmentId}`, authHeaders(req));
      const appointment = aptRes.data;
      const docRes = await axios.get(`${getApiBase(req)}/doctors/${appointment.doctor_id}`, authHeaders(req));
      res.render('patient/reschedule-confirm', {
        appointment,
        doctor: docRes.data,
        date,
        time,
        error,
      });
    } catch (_) {
      res.redirect('/patient/dashboard');
    }
  }
});

module.exports = router;
