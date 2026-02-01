import getpass
from pathlib import Path

from prusa_connect.auth import PrusaConnectCredentials, interactive_login
from prusa_connect.client import PrusaConnectClient

TOKEN_FILE = Path("my_tokens.json")

# 1. Try to load existing credentials
creds = PrusaConnectCredentials.from_file(TOKEN_FILE)

if not creds or not creds.valid:
    print("Login required.")

    # Developer defines how to get the OTP
    def my_otp_prompter():
        return input("Please enter code from your Authenticator app: ")

    email = input("Email: ")
    password = getpass.getpass("Password: ")

    # Perform login
    token_data = interactive_login(email, password, otp_callback=my_otp_prompter)

    # Create credentials and save them
    def save_tokens(data):
        with TOKEN_FILE.open("w") as f:
            import json

            json.dump(data, f)

    creds = PrusaConnectCredentials(token_data, token_saver=save_tokens)
    # Save initially
    save_tokens(token_data)

# 2. Initialize Client
client = PrusaConnectClient(credentials=creds)

# 3. Use it (Token refresh happens automatically in background if needed)
printers = client.get_printers()
