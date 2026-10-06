NeuraNova PA — Windows
=====================

START
  Double-click "NeuraNova PA" (Start menu or desktop). A small black window opens — keep it open
  (minimise it); that is the PA working. Your browser opens at http://localhost:8080.

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
  Close the black window (or press Ctrl+C in it).

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
  Starting it twice just opens the running copy. If another program uses port 8080, start it from a
  Command Prompt with:  "NeuraNova PA.exe" --port 8085
