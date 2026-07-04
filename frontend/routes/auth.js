const express = require('express');
const router = express.Router();
const axios = require('axios');

const getApiBase = (req) => req.app.locals.apiBase;

router.get('/login', (req, res) => {
  if (req.cookies.token) return res.redirect('/');
  // Fire-and-forget ping to wake up the backend server on Render
  axios.get(`${getApiBase(req)}/doctors/search`, { params: { limit: 1 } }).catch(() => {});
  res.render('auth/login', { error: null });
});

router.post('/login', async (req, res) => {
  try {
    const response = await axios.post(`${getApiBase(req)}/auth/login`, req.body);
    const { access_token, user } = response.data;
    res.cookie('token', access_token, { httpOnly: true, maxAge: 24 * 60 * 60 * 1000 });
    res.cookie('user', JSON.stringify(user), { httpOnly: true, maxAge: 24 * 60 * 60 * 1000 });
    res.redirect('/');
  } catch (err) {
    const error = err.response?.data?.detail || 'Login failed';
    res.render('auth/login', { error });
  }
});

router.get('/register', (req, res) => {
  if (req.cookies.token) return res.redirect('/');
  // Fire-and-forget ping to wake up the backend server on Render
  axios.get(`${getApiBase(req)}/doctors/search`, { params: { limit: 1 } }).catch(() => {});
  res.render('auth/register', { error: null });
});


router.post('/register', async (req, res) => {
  try {
    const response = await axios.post(`${getApiBase(req)}/auth/register`, req.body);
    const { access_token, user } = response.data;
    res.cookie('token', access_token, { httpOnly: true, maxAge: 24 * 60 * 60 * 1000 });
    res.cookie('user', JSON.stringify(user), { httpOnly: true, maxAge: 24 * 60 * 60 * 1000 });
    res.redirect('/');
  } catch (err) {
    const error = err.response?.data?.detail || 'Registration failed';
    res.render('auth/register', { error });
  }
});

module.exports = router;
