# Setup Instructions

Follow these steps to get Somo running on your machine after extracting the ZIP file.

## Prerequisites

- **Python 3.11 or higher** — Download from https://www.python.org/downloads/
- **A Twilio account** — Free trial at https://www.twilio.com/try-twilio (includes trial SMS credits)
- **A DeepSeek API key** — Via Lightning AI at https://lightning.ai/

## Step 1: Extract and Open the Project

Extract the ZIP file to a folder of your choice, then open a terminal in that folder.

```bash
cd somo-sms-learning
```

## Step 2: Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it:

- **Windows (Command Prompt):**
  ```
  .venv\Scripts\activate
  ```
- **Windows (PowerShell):**
  ```
  .venv\Scripts\Activate.ps1
  ```
- **macOS / Linux:**
  ```
  source .venv/bin/activate
  ```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs: FastAPI, Uvicorn, SQLModel, Twilio SDK, OpenAI client library, python-dotenv, Jinja2, and aiofiles.

## Step 4: Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` in a text editor and set the following values:

```
DEEPSEEK_API_KEY=your-lightning-ai-api-key
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_MESSAGING_SERVICE_SID=your-twilio-messaging-service-sid
TWILIO_PHONE_NUMBER=+1234567890
INSTRUCTOR_PASSCODE=your-chosen-passcode
```

**Where to find these values:**

- **DEEPSEEK_API_KEY**: From your Lightning AI dashboard after enabling the DeepSeek V3.1 model.
- **TWILIO_ACCOUNT_SID** and **TWILIO_AUTH_TOKEN**: Found on your Twilio Console dashboard at https://console.twilio.com/
- **TWILIO_MESSAGING_SERVICE_SID**: Create a Messaging Service in Twilio Console under Messaging > Services.
- **TWILIO_PHONE_NUMBER**: Your Twilio phone number (with country code, e.g., +1234567890).
- **INSTRUCTOR_PASSCODE**: Choose any passcode you'd like for logging into the instructor dashboard.

## Step 5: Run the Application

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start and automatically create the database and seed it with demo data (18 students, 10 topics, 56 questions, 18 clusters).

## Step 6: Open the Dashboard

Open your browser and go to:

```
http://localhost:8000
```

**Login credentials (demo):**
- **Name:** Default Instructor
- **Passcode:** admin123 (or whatever you set in INSTRUCTOR_PASSCODE)

## Step 7: Try the SMS Simulator

You don't need a real phone to test the student experience. In the dashboard sidebar, click **Simulator**. Pick any registered student from the dropdown, type a message, and see how the AI tutor responds — all without sending actual SMS messages or using Twilio credits.

## Step 8: Connect a Real Phone (Optional)

To receive actual SMS from real phones, you need to expose your local server to the internet and point Twilio to it.

1. Use a tunneling service like [ngrok](https://ngrok.com/) or [Pinggy](https://pinggy.io/):
   ```bash
   # Using ngrok
   ngrok http 8000

   # Using Pinggy
   ssh -p 443 -R0:localhost:8000 free.pinggy.io
   ```

2. Copy the public HTTPS URL provided by the tunnel.

3. In your Twilio Console, go to your phone number's configuration and set the **Incoming Message Webhook** to:
   ```
   https://your-tunnel-url.com/webhook
   ```

4. Send an SMS from any phone to your Twilio number. The student must be registered in the dashboard first for the system to recognize their number.

## Project Structure

```
somo-sms-learning/
├── main.py                 # FastAPI app — all endpoints + SMS state machine
├── models.py               # Database models (Student, Cluster, Assignment, etc.)
├── database.py             # SQLite engine + session management
├── llm_service.py          # DeepSeek AI integration (questions, grading, insights)
├── curriculum.py           # Kenya CBC curriculum structure
├── twilio_service.py       # Twilio SMS sending + simulator capture
├── sms_utils.py            # GSM-7 character sanitization + truncation
├── engagement_monitor.py   # Background engagement alert system
├── seed_demo.py            # Demo data generator
├── run_test.py             # Basic integration test
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── templates/
│   ├── dashboard.html      # Instructor dashboard (single-page app)
│   └── login.html          # Login page
└── static/
    └── style.css           # Dashboard styles
```

## Troubleshooting

**"Module not found" errors:** Make sure your virtual environment is activated (you should see `(.venv)` in your terminal prompt).

**Dashboard shows no data:** The demo data is seeded automatically on first run. If the database file (`educator.db`) already exists from a previous run, delete it and restart the server to get fresh demo data.

**SMS not arriving:** Check that your Twilio credentials are correct in `.env`, your tunnel is running, and the webhook URL in Twilio Console matches your current tunnel URL. Free tunnels change URLs on restart.

**AI responses seem slow:** The first request to DeepSeek may take a few seconds to warm up. Subsequent requests are typically faster. If responses consistently fail, verify your DEEPSEEK_API_KEY is valid.
