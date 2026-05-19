# El-Manara Academy

El-Manara Academy is a full-stack Django educational platform built with multi-language support (Arabic & English), RTL/LTR CSS logical properties, dark mode, subject card grid, test-prep (SAT/IELTS/TOEFL) section, hourly package purchasing, parent accounts, and an abuse-resistant referral system.

## How to Run the Site Locally

Follow these steps to get the project up and running in your local environment.

### Prerequisites

Ensure you have Python 3 installed on your system.

### 1. Open Terminal

Open a terminal and navigate to the root directory of the project:
```bash
cd /El-Manara
```

### 2. Activate Virtual Environment

A Python virtual environment is included in the project directory. Activate it using the following command:

```bash
source venv/bin/activate
```
*(Your terminal prompt should change to show `(venv)` at the beginning).*

### 3. Initial Setup (First Time Only)

If this is your first time setting up the project, you need to prepare the database and translations. Run the following commands in order:

```bash
# 1. Create the new migration for price_aed field
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

## Additional Commands

If you need to make changes to the database or translations in the future, you can use these commands (make sure the virtual environment is active):

- **Create migrations:** `python manage.py makemigrations`
- **Apply migrations:** `python manage.py migrate`
- **Seed initial data:** `python manage.py seed_data`
- **Compile translations:** `python manage.py compilemessages`
- **Create superuser (Admin):** `python manage.py createsuperuser`
