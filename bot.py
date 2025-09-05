import time
import requests
import whisper
import os
import re
import shutil
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# -------------------------------
# CONFIG
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_AUDIO_DIR = os.path.join(BASE_DIR, "temp_audio")

# Clean up old audio files each run
if os.path.exists(TEMP_AUDIO_DIR):
    shutil.rmtree(TEMP_AUDIO_DIR)
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

# -------------------------------
# DOWNLOAD AUDIO FUNCTION
# -------------------------------
def download_audio_from_url(audio_url, clip_count):
    """Download audio from a given URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://speech.intron.health/'
        }

        print(f"📥 Downloading: {audio_url}")
        response = requests.get(audio_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Extension guess
        if '.wav' in audio_url.lower():
            ext = '.wav'
        elif '.mp3' in audio_url.lower():
            ext = '.mp3'
        elif '.ogg' in audio_url.lower():
            ext = '.ogg'
        else:
            ext = '.wav'

        raw_audio_path = os.path.join(TEMP_AUDIO_DIR, f"clip_{clip_count}{ext}")

        with open(raw_audio_path, 'wb') as f:
            f.write(response.content)

        print(f"💾 Audio downloaded: {raw_audio_path}")
        return raw_audio_path

    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None


# -------------------------------
# CONVERT AUDIO FUNCTION
# -------------------------------
def convert_audio_to_wav(input_file, clip_count):
    """Convert any format to clean 16kHz mono WAV using ffmpeg"""
    output_file = os.path.join(TEMP_AUDIO_DIR, f"clean_clip_{clip_count}.wav")
    try:
        command = [
            "ffmpeg", "-y", "-i", input_file,
            "-ar", "16000", "-ac", "1", output_file
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(f"🎧 Converted to clean WAV: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ Audio conversion failed: {e}")
        return input_file  # fallback


# -------------------------------
# EXTRACT AUDIO URL FUNCTION
# -------------------------------
def extract_audio_url_from_page(driver):
    """Extract the actual audio URL from the page source"""
    print("🔍 Extracting audio URL from page...")

    page_source = driver.page_source
    s3_pattern = r'https://speech-app\.s3\.eu-west-2\.amazonaws\.com/static/audio/[^"\']+\.wav'
    matches = re.findall(s3_pattern, page_source)

    if matches:
        print(f"🎵 Found audio URL in page source: {matches[0]}")
        return matches[0]

    print("❌ Could not find audio URL in page source")
    return None


# -------------------------------
# TRANSCRIBE FUNCTION
# -------------------------------
def transcribe_audio(filename, model):
    """Transcribe audio with Whisper (forced English)"""
    if not os.path.exists(filename):
        print(f"❌ File not found: {filename}")
        return ""

    time.sleep(0.5)

    print("📝 Transcribing with Whisper...")
    try:
        file_size = os.path.getsize(filename)
        if file_size == 0:
            print("❌ Empty audio file")
            return ""

        print(f"📊 Audio file size: {file_size} bytes")
        # Force language to English
        result = model.transcribe(filename, language="en")
        transcript = result["text"].strip()

        if transcript:
            print(f"✅ Transcript: {transcript}")
        else:
            print("⚠️ Empty transcript received")

        return transcript

    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return ""


# -------------------------------
# MAIN BOT FUNCTION
# -------------------------------
def main():
    # Load Whisper model
    print("Loading Whisper model... (This may take a moment)")
    model = whisper.load_model("base")
    print("Model loaded.")

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Navigate to site
        driver.get("https://speech.intron.health")
        print("👉 Please log in manually...")

        WebDriverWait(driver, 300).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Transcribe"))
        )
        print("✅ Login successful")

        driver.find_element(By.LINK_TEXT, "Transcribe").click()
        print("✅ Clicked Transcribe button")

        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Start Transcribing"))
        ).click()
        print("✅ On transcription page")

        time.sleep(3)

        last_audio_url = None
        clip_count = 0
        while True:
            clip_count += 1
            print(f"\n--- Processing Clip #{clip_count} ---")

            try:
                # Wait for new URL
                for _ in range(30):
                    audio_url = extract_audio_url_from_page(driver)
                    if audio_url and audio_url != last_audio_url:
                        break
                    print("⏳ Waiting for new clip URL...")
                    time.sleep(1)
                else:
                    print("❌ No new clip URL detected (timeout)")
                    break

                last_audio_url = audio_url

                # Download + convert + transcribe
                audio_file = download_audio_from_url(audio_url, clip_count)
                if audio_file:
                    clean_wav = convert_audio_to_wav(audio_file, clip_count)
                    transcript_text = transcribe_audio(clean_wav, model)
                    os.remove(audio_file)
                    if clean_wav != audio_file:
                        os.remove(clean_wav)
                else:
                    transcript_text = "# Download failed #"

                if not transcript_text:
                    transcript_text = "# Transcription failed #"

                # Insert transcript
                textarea = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.ID, "feedbackBox"))
                )
                textarea.clear()
                textarea.send_keys(transcript_text)
                print("✅ Transcript inserted")

                # Submit
                submit_btn = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.ID, "submitBtn"))
                )
                submit_btn.click()
                print("📤 Transcript submitted")

                time.sleep(2)

                if "transcribe" not in driver.current_url.lower():
                    print("❌ Session ended")
                    break

            except Exception as e:
                print(f"⚠️ Error in clip processing: {e}")
                break

        print(f"\n✅ Completed {clip_count} clips!")

    except Exception as e:
        print(f"❌ Fatal error: {e}")

    finally:
        print("Script finished. Browser remains open.")


def run_bot(*args, **kwargs):
    main()


if __name__ == "__main__":
    main()
