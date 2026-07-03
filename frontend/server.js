const express = require('express');
const path = require('path');
const cookieParser = require('cookie-parser');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const app = express();
const PORT = process.env.PORT || process.env.FRONTEND_PORT || 3000;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

const API_BASE = process.env.API_BASE || 'http://localhost:8000/api';
app.locals.apiBase = API_BASE;

function parseUserCookie(cookieValue) {
  if (!cookieValue) return null;
  try {
    return JSON.parse(cookieValue);
  } catch (_) {
    return null;
  }
}

app.use((req, res, next) => {
  res.locals.apiBase = API_BASE;
  res.locals.currentPath = req.path;
  req.currentUser = parseUserCookie(req.cookies.user);
  res.locals.user = req.currentUser;
  res.locals.token = req.cookies.token || null;
  next();
});

const authRoutes = require('./routes/auth');
const patientRoutes = require('./routes/patient');
const doctorRoutes = require('./routes/doctor');
const adminRoutes = require('./routes/admin');

app.use('/', authRoutes);
app.use('/patient', patientRoutes);
app.use('/doctor', doctorRoutes);
app.use('/admin', adminRoutes);

app.get('/', (req, res) => {
  if (!req.cookies.token) return res.redirect('/login');
  const user = req.currentUser;
  if (user?.role === 'PATIENT') return res.redirect('/patient/dashboard');
  if (user?.role === 'DOCTOR') return res.redirect('/doctor/dashboard');
  if (user?.role === 'ADMIN') return res.redirect('/admin/dashboard');
  res.redirect('/login');
});

app.get('/logout', (req, res) => {
  res.clearCookie('token');
  res.clearCookie('user');
  res.redirect('/login');
});

app.get('/privacy', (req, res) => {
  res.render('privacy');
});

app.listen(PORT, () => {
  console.log(`Frontend server running on http://localhost:${PORT}`);
});

