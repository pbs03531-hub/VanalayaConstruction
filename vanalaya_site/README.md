# Vanalaya Studio website

Flask + SQLite. Public site plus admin panel at `/admin`.

## Run locally
Windows: double-click `start.bat` (admin password there: `ChangeMe-123`, change it in Admin > Password).
Other: `pip install -r requirements.txt && ADMIN_PASSWORD=yourpass python app.py`

First run seeds 19 projects, 9 services and site text. If `ADMIN_PASSWORD` is not set, a password is generated and saved in `data/first_admin_login.txt`.

## Add photos
Admin > Projects > edit a project > Photos > upload. Until then cards show a placeholder.

## Deploy on Render
Push to GitHub, create a Blueprint from `render.yaml`. Set `ADMIN_PASSWORD`, `SITE_URL`, and optionally SMTP vars for enquiry emails. A persistent disk (paid plan) keeps the database and photos; the free plan loses them on redeploy.

## Tests
`python -m unittest discover -s tests`

## Phase 2 (not built)
WhatsApp Business (Meta Cloud API) and Instagram DM automation.
