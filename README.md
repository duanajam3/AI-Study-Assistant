# ✦ StudyAI — AI Study Assistant
### A Professional Desktop Application built with Python & tkinter

---

## 📋 Overview

StudyAI is a polished desktop study companion that features:

- **Authentication** — Secure login/signup with SQLite-backed user accounts
- **Study Material Generator** — AI-simulated notes tailored to your education level
- **AI Q&A Interface** — Context-aware question answering with chat history
- **Image Gallery** — Upload, describe, preview, and manage study images
- **Progress Tracker** — Per-subject progress bars, session history, and statistics
- **Settings** — Edit your profile, education level, and subject preferences

---

## 🚀 Quick Start

### 1. Prerequisites

Python 3.8 or newer is required. Tkinter is included with most Python distributions.

```bash
python --version   # should be 3.8+
```

### 2. Install optional dependency (recommended)

```bash
pip install Pillow
```

> Without Pillow the app still runs fully — images are stored by path
> and displayed as metadata instead of thumbnails.

### 3. Run

```bash
python study_assistant.py
```

The SQLite database (`study_assistant.db`) is created automatically on first run
in the same directory as the script.

---

## 🗂️ File Structure

```
study_assistant.py      ← Main application (single file, self-contained)
requirements.txt        ← Only lists Pillow (optional)
study_assistant.db      ← Auto-created SQLite database
README.md               ← This file
```

---

## 🧩 Architecture

| Class | Role |
|-------|------|
| `DatabaseManager` | All SQLite CRUD — users, sessions, Q&A, images, progress |
| `AIEngine` | Simulated AI for study-note generation and Q&A |
| `LoginWindow` | Centered, themed sign-in dialog |
| `SignupWindow` | Scrollable registration form |
| `MainApp` | Root `tk.Tk` — controls sidebar, navigation, screen switching |
| `DashboardScreen` | Stats cards, progress overview, quick actions |
| `StudyScreen` | Subject/topic selector + AI content generator |
| `AIScreen` | Chat-style Q&A with persistent history |
| `GalleryScreen` | Image upload, Treeview gallery, Pillow preview |
| `ProgressScreen` | Progress bars, summary cards, session history table |
| `SettingsScreen` | Profile editor, subject checkboxes, about panel |

---

## 🎨 Design Choices

- **Dark theme** throughout (`#0d0d1a` background, `#4361ee` primary accent)
- `ttk.Style` + `clam` theme base for cross-platform consistency
- Hover effects on all interactive buttons via `<Enter>` / `<Leave>` bindings
- `tk.Canvas`-backed scrolling for long pages (signup, dashboard)
- `ttk.PanedWindow` for the gallery split view

---

## 📦 Database Schema

```sql
users          (id, username, email, password [sha256], edu_level, subjects [json], avatar_path)
study_sessions (id, user_id, subject, topic, content, duration, created_at)
qa_history     (id, user_id, question, answer, subject, created_at)
images         (id, user_id, filename, description, image_data [BLOB], file_path, created_at)
progress       (id, user_id, subject, score, sessions, updated_at)
```

---

## ⚠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: tkinter` | Install `python3-tk` (Linux: `sudo apt install python3-tk`) |
| Window doesn't maximise | Resize manually — minimum size is 960 × 620 |
| Images don't preview | Run `pip install Pillow` and restart |
| `study_assistant.db` permission error | Run the script in a writable directory |

---

## 📄 License

Free for educational and personal use.  
Built as a university-level Python desktop-application project.