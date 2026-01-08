from flask import Flask, render_template, request, jsonify
import threading
import subprocess
import sys
import os

app = Flask(__name__)

# Global variable to track if bot is running
bot_running = False

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global bot_running
    
    if bot_running:
        return jsonify({"status": "error", "message": "Bot is already running"})
    
    data = request.get_json()
    language = data.get("language", "sw")
    
    try:
        # Start the bot in a separate thread
        thread = threading.Thread(target=run_bot_script)
        thread.daemon = True  # This allows the thread to exit when the main program exits
        thread.start()
        
        bot_running = True
        return jsonify({"status": "started", "language": language, "message": "Bot started successfully"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to start bot: {str(e)}"})

def run_bot_script():
    """Run the bot script as a separate process"""
    global bot_running
    try:
        # Run the bot script directly
        subprocess.run([sys.executable, "bot.py"], check=True)
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        bot_running = False

if __name__ == "__main__":
    app.run(debug=True)