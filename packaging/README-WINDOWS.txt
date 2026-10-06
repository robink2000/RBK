NeuraNova PA — Windows
=====================

START
  Double-click "NeuraNova PA" (Start menu or desktop). Your browser opens at http://localhost:8080.
  The PA keeps working quietly in the background: look for the NeuraNova flower icon in the
  system tray, next to the clock (click the ^ arrow if you don't see it).
  Click the icon to open the PA again; right-click it for "Open my data folder" and "Quit".

FIRST TIME
  1. The browser asks you to create your login (email + password). Only a secure hash of the
     password is stored.
  2. Sign in. A 10-step setup follows: company & hours, NeuraNova application addresses, email,
     WhatsApp, calendar, Google Drive, AI (Claude or OpenAI), notifications, QA test accounts.
     Every step can be skipped and changed later under Settings.

TRY IT WITHOUT CONNECTING ANYTHING
  Start menu → "NeuraNova PA (sample data demo)". Sign in with you@neuranova.demo / neuranova-demo.
  Sample data only, kept separate from your real data.

STOP
  Right-click the tray icon → "Quit NeuraNova PA".

RUN AUTOMATICALLY
  If you ticked "Start automatically when I sign in", the PA starts in the background each time you
  sign in to Windows. To change this: press Win+R, type  shell:startup  and add or delete the
  "NeuraNova PA" shortcut.

YOUR DATA
  %LOCALAPPDATA%\NeuraNova PA  (tasks, settings, encrypted account keys, QA screenshots, .env).
  Uninstalling keeps this folder. Back it up to keep your history. Keep .env private: it holds the
  key that encrypts your connected accounts.

SAFETY
  Safe Mode is ON by default: emails and WhatsApp messages are drafted and wait for your approval.
  Production QA checks never click or change anything.

APPLICATION QA (optional)
  Checks use Microsoft Edge, which every Windows PC has. Nothing else to install.

PORT ALREADY IN USE?
  Starting it twice just opens the running copy. If an older copy or another program uses port
  8080, the PA tells you and opens on the next free address (8081, 8082...).

SOMETHING WRONG?
  The log is in %LOCALAPPDATA%\NeuraNova PA\logs\neuranova-pa.log. Backups of all your data are in
  %LOCALAPPDATA%\NeuraNova PA\data\backups (one a day; download them from Settings → Backups too).
