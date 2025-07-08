# 🎉 Corporate Event Management System

> 👩‍💻 Developed by **Janvi Chauhan**  
> 🏫 Semester 8 Project – MSc Computer Science  
> 🧑‍🏫 Guided by Dr. Maitri Jhaveri, Gujarat University  

A robust, full-stack web application built to manage the complete lifecycle of professional and academic events — from planning and registration to role-based access, QR ticketing, reporting, and feedback collection.

---

## 📚 Table of Contents

- [📝 Overview](#-overview)
- [🚀 Key Features](#-key-features)
- [👥 User Roles](#-user-roles)
- [🛠️ Tech Stack](#-tech-stack)
- [🧱 Modules & Functionalities](#-modules--functionalities)
- [🗂️ Data Architecture](#-data-architecture)
- [📸 Screenshots](#-screenshots)
- [📈 Future Work](#-future-work)
- [🙏 Acknowledgements](#-acknowledgements)
- [👩‍💻 About Me](#-about-me)

---

## 📝 Overview

The **Corporate Event Management System (CorpEventX)** simplifies the planning and execution of:

- 💡 Hackathons
- 📢 Seminars & Webinars
- 🎓 Academic Conferences
- 👥 Workshops & Industry Talks

This role-based platform offers a seamless experience for Students, Faculty, Industry Professionals, and Administrators. Each user gets a tailored dashboard, ensuring clarity, relevance, and efficiency.

---

## 🚀 Key Features

- ✅ Multi-role Login (Attendee, Organizer, Speaker, Sponsor, Admin)
- 🎟️ QR Code Ticketing & Check-in
- 📅 Event Creation & Management
- 📤 Speaker Topic Submission & Approval
- 📝 Feedback Collection & Report Generation
- 📢 Notifications & Email Alerts
- 📊 Dashboards with Analytics and PDF/Excel Exports
- 🧾 Sponsorship Tiers and Management

---

## 👥 User Roles

| Role                  | Capabilities                                                                 |
|-----------------------|-------------------------------------------------------------------------------|
| 👩‍🎓 Student           | Register for events, submit papers/sessions, receive tickets and updates     |
| 👨‍🏫 Faculty/Academia  | Organize events, manage sessions, review papers, monitor reports              |
| 🧑‍💼 Employee           | Approve registrations, manage logistics and speaker sessions                 |
| 🏢 Industry Professional | Attend, speak, sponsor, or review content based on assigned role             |
| 🛠 Admin               | Full system control: users, events, analytics, settings, and notifications   |

---

## 🛠️ Tech Stack

| Layer       | Technologies Used                      |
|-------------|------------------------------------------|
| 🖥 Frontend  | HTML5, CSS3, JavaScript, Bootstrap       |
| ⚙ Backend   | Python, Django Framework                 |
| 🧮 Database  | SQLite (can be upgraded to PostgreSQL/MySQL) |
| 📩 Extras    | Django Email, QRCode Generator, ReportLab |
| ☁ Deployment | Render / Vercel / Heroku (planned)       |

---

## 🧱 Modules & Functionalities

### ✅ Event Management
- Create events with title, venue, banners, track details
- Categorize events (e.g., Hackathon, Seminar, Workshop)

### 🎟️ Registration & Ticketing
- Dynamic forms based on role
- QR-code-based ticket generation
- Admin approval workflow

### 📢 Speaker & Paper Management
- Topic submission portal
- Admin review & feedback
- Scheduled sessions and topic uploads

### 👥 Sponsorship Module
- Tier-based sponsor listing
- Upload logos, materials, and benefits

### 📊 Reporting & Feedback
- Dashboard statistics (role-based)
- Export reports as PDF/Excel
- Post-event feedback analytics

---

## 🗂️ Data Architecture

- `users` – with UUIDs, user_type, and authentication
- `events` – includes categories, tags, QR config, registration link
- `registrations` – ticketing, approval, status, and check-in tracking
- `speakers` – proposals, materials, session mapping
- `sponsors` – sponsor profile, tiers, contract, and benefits
- `blogs`, `notifications`, `feedback` – for engagement and content

> Full data dictionary available in the project documentation.

---

## 📸 Screenshots

| Section            | View                      |
|-------------------|---------------------------|
| Login/Registration| Role-based onboarding     |
| Attendee Dashboard| Tickets, notifications    |
| Organizer Panel   | My Events, Email Attendees|
| Admin Panel       | Full control & analytics  |
| Speaker Dashboard | Uploads & session tracking|
| Sponsor Panel     | Tier benefits & status     |

> 📁 Screenshots available in `/screenshots` or full PDF.

---

## 📈 Future Work

- 🔧 **Hackathon Module**: Team formation, project tracking
- 🤖 **AI Speaker Evaluation**: Plagiarism checks, scoring, approvals
- 🌐 **API Integrations**: Zoom, Google Calendar, LinkedIn
- 📱 **PWA Support**: Mobile-first interface with offline capabilities
- 🔐 **OAuth Login**: Google/GitHub SSO for easier access

---

## 🙏 Acknowledgements

Special thanks to:

- **Dr. Maitri Jhaveri** – Project Guide  
- **Prof. Dr. Hiren Joshi** – HOD, Computer Science Dept.  
- My faculty, friends, and family for constant support & feedback.

---

## 👩‍💻 About Me

I'm **Janvi Chauhan**, a Computer Science student passionate about building practical solutions using full-stack technologies.

- 📍 Gujarat University, MSc CS  
- 💼 Focus: Full Stack, Event Systems, Django  
- 🔗 www.linkedin.com/in/janvi-chauhan145 | [Email](janvi.chauhan4599@gmail.com)

---

> If you found this project insightful, give it a ⭐ on GitHub and feel free to connect!
