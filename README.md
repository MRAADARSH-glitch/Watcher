# FocusWatch
#### Video Demo: <https://youtu.be/9I4BXbtpzmE>
#### Description:

FocusWatch is a web app that tracks how long I actually study and shows me where I am going wrong.

## Why I built this

The idea came from my own studying. When I sit down to study, I get distracted every minute, and I have no track of any of those minutes. Some days I do 6 or 7 hours of study, and some days I don't, and I never knew why. That is the real issue: I had no data. I needed something that tracks my study time and shows me what I am actually doing wrong, instead of me guessing. So I decided to build it as my final project.

FocusWatch uses the webcam to check whether I am looking at the screen. While I am looking, a counter runs, so I can see my real study time instead of the time I just sat at the desk. When I look away or leave, an alert plays after 5 seconds and a louder second alert plays after 25 seconds. Not too much, just enough to pull me back. Every 25 minutes it announces a break so I don't get exhausted, and then it announces when the break is over. Every session is saved, so the History page shows how long I worked, how many times I got distracted, and how focused I really was.

## How it works

The project is a Flask web app written in Python with a SQLite database, and a camera module that runs in the background while the page shows the live counter. Each user registers with a username and password and only sees their own history and settings.

## What each file does

**app.py** is the main Flask application. It creates the database tables (users, settings, sessions) and has all the routes: register, login and logout, the home page, `/start` and `/stop` to begin and end tracking, `/status` which the page asks every second for live numbers, `/video` which streams the camera preview, `/camera` which is the separate camera window, `/history`, and `/settings`. Passwords are hashed and never stored as plain text, and a login_required function keeps pages private. When I press stop, it saves the session's totals into the database.

**watcher.py** is the camera part, and it grew out of my original script `WakeOrFace.py`. It has a Watcher class that opens the camera in a background thread so the web page doesn't freeze. It finds my face and eyes with OpenCV Haar cascades and draws a green box around the face and blue boxes around the eyes. If a face and eyes are visible I count as focused, and focus time goes up. If not, an away timer starts and plays the first sound at 5 seconds and the second at 25 seconds (both changeable in settings). It also counts the distractions, decides when a break is due, and pauses the checking during the break so it does not nag me. If the camera can't open, it reports a clear error instead of failing silently.

**study.db** is the SQLite database, created automatically the first time the app runs. It has a users table, a settings table (one row per user) and a sessions table with the start time, duration, focused seconds, away seconds, distractions and breaks.

**templates/layout.html** is the shared page layout with the navigation bar. The other pages extend it, so I don't repeat the same HTML.

**templates/login.html** and **templates/register.html** are the login and sign-up forms.

**templates/index.html** is the main tracking page: the big study counter, the distraction count, total time away, the time until the next break, the Start/Stop button and the corner camera preview.

**templates/history.html** lists every past session for the logged-in user, with a total of focused time and a focus percentage for each session. This is the page that answers my original question about what I am doing wrong.

**templates/settings.html** lets each user change the first and second alert times, how often the break comes, how long it lasts, and whether eyes must be detected. The eye option exists because glasses or poor light can stop the eye detector from working.

**templates/camera.html** is a tiny page that only shows the camera, used for the "Pop out" window.

**static/script.js** is the browser-side code. It asks `/status` every second, updates the counters, announces the start and end of breaks with the browser's speech, shows errors, and handles the Start/Stop button and the pop-out window.

**static/styles.css** has all the styling, including the floating camera box in the corner.

**sounds/** holds the two alert audio files, `voice1.mp3` and `voice2.mp3`.

**requirements.txt** lists the packages to install: flask, opencv-python and pygame.

## Design choices

I used Haar cascades because they are light, run on a normal laptop without a GPU, and I already had them working in my first script. Their weakness is glasses and dim light, which is why the eye check can be switched off. I chose 5 and 25 seconds as defaults so a short glance away doesn't trigger a loud sound, but a real distraction does. I made the alerts and breaks per-user settings in the database because everyone studies differently. I put the camera in a background thread, and the page polls for its state, so the web app stays simple. I played break announcements in the browser because that is easier than doing it in Python. I kept the camera in the corner so I can see what the detector sees without leaving the tracking page.

## How to run

Run `pip install -r requirements.txt`, put `voice1.mp3` and `voice2.mp3` in the `sounds` folder, then run `python app.py` and open http://127.0.0.1:5000. It must run on a computer with a webcam, so a cloud Codespace will not work for the camera. On Windows it uses the DirectShow camera backend first.

## AI assistance

I used an AI assistant (Claude) as a helper while building this project, The idea, the problem, and the original script are mine, refinments, suggestions from AI.
