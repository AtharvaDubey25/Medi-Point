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
  if (user?.role !== 'DOCTOR') return res.redirect('/');
  next();
});

router.get('/dashboard', async (req, res) => {
  try {
    const aptRes = await axios.get(`${getApiBase(req)}/appointments/my`, authHeaders(req));
    res.render('doctor/dashboard', { appointments: aptRes.data.appointments });
  } catch (err) {
    res.render('doctor/dashboard', { appointments: [] });
  }
});

router.get('/appointments/:id', async (req, res) => {
  try {
    const response = await axios.get(
      `${getApiBase(req)}/appointments/${req.params.id}`,
      authHeaders(req),
    );
    res.render('doctor/appointment-detail', { appointment: response.data });
  } catch (err) {
    res.redirect('/doctor/dashboard');
  }
});

router.get('/appointments/:id/pre-visit', async (req, res) => {
  try {
    const response = await axios.get(
      `${getApiBase(req)}/symptoms/appointment/${req.params.id}/pre-visit-summary`,
      authHeaders(req),
    );
    res.render('doctor/pre-visit', { data: response.data, appointmentId: req.params.id });
  } catch (err) {
    res.redirect('/doctor/dashboard');
  }
});

router.get('/appointments/:id/post-visit', async (req, res) => {
  res.render('doctor/post-visit', { appointmentId: req.params.id, error: null });
});

router.post('/appointments/:id/post-visit', async (req, res) => {
  try {
    const medications = [];
    if (req.body.med_name) {
      const names = Array.isArray(req.body.med_name) ? req.body.med_name : [req.body.med_name];
      const dosages = Array.isArray(req.body.med_dosage) ? req.body.med_dosage : [req.body.med_dosage];
      const frequencies = Array.isArray(req.body.med_frequency) ? req.body.med_frequency : [req.body.med_frequency];
      const durations = Array.isArray(req.body.med_duration) ? req.body.med_duration : [req.body.med_duration];
      for (let i = 0; i < names.length; i++) {
        if (names[i]) {
          medications.push({
            name: names[i],
            dosage: dosages[i] || '',
            frequency: frequencies[i] || '',
            duration_days: parseInt(durations[i]) || null,
          });
        }
      }
    }

    await axios.post(
      `${getApiBase(req)}/symptoms/appointment/${req.params.id}/post-visit`,
      {
        notes: req.body.notes,
        prescription: req.body.prescription,
        medications,
      },
      authHeaders(req),
    );
    res.redirect('/doctor/dashboard');
  } catch (err) {
    const error = err.response?.data?.detail || 'Failed to submit post-visit data';
    res.render('doctor/post-visit', { appointmentId: req.params.id, error });
  }
});

router.get('/availability', async (req, res) => {
  try {
    const docRes = await axios.get(`${getApiBase(req)}/doctors/${req.currentUser?.id || 0}`, authHeaders(req));
    res.render('doctor/availability', { doctor: docRes.data, error: null });
  } catch (err) {
    res.render('doctor/availability', { doctor: null, error: null });
  }
});

router.post('/availability', async (req, res) => {
  try {
    await axios.post(`${getApiBase(req)}/doctors/availability`, {
      day_of_week: parseInt(req.body.day_of_week),
      start_time: req.body.start_time,
      end_time: req.body.end_time,
      is_available: true,
    }, authHeaders(req));
    res.redirect('/doctor/availability');
  } catch (err) {
    res.render('doctor/availability', { doctor: null, error: 'Failed to add availability' });
  }
});

router.post('/leave', async (req, res) => {
  try {
    await axios.post(`${getApiBase(req)}/doctors/leave`, {
      leave_date: req.body.leave_date,
      reason: req.body.reason || '',
    }, authHeaders(req));
    res.redirect('/doctor/availability');
  } catch (err) {
    res.redirect('/doctor/availability');
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
    res.redirect('/doctor/dashboard');
  }
});

module.exports = router;
