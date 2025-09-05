from flask import Flask, render_template, request, jsonify
import threading
import bot  # your bot.py

app = Flask(__name__)

@app.route("/")
def home():
    # Loads templates/index.html
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    language = data.get("language", "sw")  # default Swahili if none picked
    thread = threading.Thread(target=bot.run_bot, args=(language,))
    thread.start()
    return jsonify({"status": "started", "language": language})

if __name__ == "__main__":
    app.run(debug=True)
