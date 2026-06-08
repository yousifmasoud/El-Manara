# Khotaa Academy

Khotaa Academy is a full-stack Django educational platform built with multi-language support (Arabic & English), RTL/LTR CSS logical properties, dark mode, subject card grid, test-prep (SAT/IELTS/TOEFL) section, hourly package purchasing, parent accounts, and an abuse-resistant referral system.

## Key Features

- **Multi-language Support (i18n):** Complete localized English (LTR) and Arabic (RTL) interfaces.
- **Session Scheduling System:**
  - Teachers can schedule sessions with any student (filtered by active subjects).
  - Students can schedule sessions with any verified tutor (if they have a positive hourly balance).
  - Automatic balance deduction (duration of session in hours subtracted from student's hourly balance upon scheduling).
  - Session cancellation restores/refunds the exact hours back to the student's balance.
  - Interactive calendars on student and teacher dashboards.
- **Google Meet Integration:**
  - Users can link their Google Accounts via Google OAuth.
  - Generates live Google Meet links programmatically and sends invites to both participants' Google Calendars.
  - Falls back to a mock Google Meet preview link if Google OAuth is not connected or in development.
- **Abuse-Resistant Referral System:** Auto-grants free hours to referrers when a referred user makes their first purchase, subject to validation caps.

## How to Run the Site Locally

Follow these steps to get the project up and running in your local environment.

### Prerequisites

Ensure you have Python 3 installed on your system.

### 1. Open Terminal

Open a terminal and navigate to the root directory of the project:
```bash
cd /Khotaa
```

### 2. Create & Activate Virtual Environment

Create a virtual environment and install the project dependencies from `requirements.txt`:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

*(Your terminal prompt should change to show `(venv)` at the beginning).*

### 3. Initial Setup (First Time Only)

If this is your first time setting up the project, you need to prepare the database and translations. Run the following commands in order:

```bash
# 1. Create the migrations
python manage.py makemigrations accounts courses

# 2. Apply all migrations
python manage.py migrate

# 3. Seed subjects + packages
python manage.py seed_data

# 4. Compile Arabic translations (needs gettext)
sudo apt install gettext -y
python manage.py compilemessages

# 5. Create superuser
python manage.py createsuperuser
```

### 4. Run the Development Server

Start the Django development server by running:

```bash
python manage.py runserver
```

### 5. Access the Site

Open your web browser and navigate to:
- **English version (LTR):** [http://127.0.0.1:8000/en/](http://127.0.0.1:8000/en/)
- **Arabic version (RTL):** [http://127.0.0.1:8000/ar/](http://127.0.0.1:8000/ar/)

*(To stop the server, press `Ctrl+C` in your terminal).*

## Running Tests

To run the automated test suite (including OAuth flows, scheduling constraints, meeting creation, and cancellation refunds):

```bash
python manage.py test
```

## Additional Commands

- **Create migrations:** `python manage.py makemigrations`
- **Apply migrations:** `python manage.py migrate`
- **Seed initial data:** `python manage.py seed_data`
- **Compile translations:** `python manage.py compilemessages`
- **Create superuser (Admin):** `python manage.py createsuperuser`
