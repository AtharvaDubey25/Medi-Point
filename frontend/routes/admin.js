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
  if (user?.role !== 'ADMIN') return res.redirect('/');
  next();
});

router.get('/dashboard', async (req, res) => {
  try {
    const [doctorsRes, appointmentsRes] = await Promise.all([
      axios.get(`${getApiBase(req)}/admin/doctors`, authHeaders(req)),
      axios.get(`${getApiBase(req)}/admin/appointments`, authHeaders(req)),
    ]);
    res.render('admin/dashboard', {
      doctors: doctorsRes.data,
      appointments: appointmentsRes.data,
    });
  } catch (err) {
    res.render('admin/dashboard', { doctors: [], appointments: [] });
  }
});

router.get('/doctors/create', (req, res) => {
  res.render('admin/doctor-form', { doctor: null, error: null });
});

router.post('/doctors/create', async (req, res) => {
  try {
    await axios.post(`${getApiBase(req)}/admin/doctors`, req.body, authHeaders(req));
    res.redirect('/admin/dashboard');
  } catch (err) {
    const error = err.response?.data?.detail || 'Failed to create doctor';
    res.render('admin/doctor-form', { doctor: null, error });
  }
});

router.get('/doctors/:id/edit', async (req, res) => {
  try {
    const response = await axios.get(`${getApiBase(req)}/doctors/${req.params.id}`, authHeaders(req));
    res.render('admin/doctor-form', { doctor: response.data, error: null });
  } catch (err) {
    res.redirect('/admin/dashboard');
  }
});

router.post('/doctors/:id/edit', async (req, res) => {
  try {
    await axios.put(`${getApiBase(req)}/admin/doctors/${req.params.id}`, req.body, authHeaders(req));
    res.redirect('/admin/dashboard');
  } catch (err) {
    const error = err.response?.data?.detail || 'Failed to update doctor';
    const doctor = {
      user_id: req.params.id,
      full_name: req.body.full_name,
      email: req.body.email,
      specialization: req.body.specialization,
      qualification: req.body.qualification,
      experience_years: req.body.experience_years,
      slot_duration_minutes: req.body.slot_duration_minutes,
      bio: req.body.bio,
    };
    res.render('admin/doctor-form', { doctor, error });
  }
});

router.post('/doctors/:id/delete', async (req, res) => {
  try {
    await axios.delete(`${getApiBase(req)}/admin/doctors/${req.params.id}`, authHeaders(req));
    res.redirect('/admin/dashboard');
  } catch (err) {
    res.redirect('/admin/dashboard');
  }
});

module.exports = router;
