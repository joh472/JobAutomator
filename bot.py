import os, re, time, random, shutil, subprocess, requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException, TimeoutException

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_AUDIO_DIR = os.path.join(BASE_DIR, "temp_audio")

if os.path.exists(TEMP_AUDIO_DIR):
    shutil.rmtree(TEMP_AUDIO_DIR)
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

def human_like_delay(min_sec=0.6, max_sec=1.6):
    time.sleep(random.uniform(min_sec, max_sec))

def safe_click(element, driver, retries=3):
    for _ in range(retries):
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            time.sleep(1)
    return False

def download_audio(audio_url, clip_count):
    try:
        resp = requests.get(audio_url, timeout=30)
        resp.raise_for_status()
        path = os.path.join(TEMP_AUDIO_DIR, f"raw_clip_{clip_count}.wav")
        with open(path, "wb") as f:
            f.write(resp.content)
        print(f"📥 Downloaded raw audio: {path}")
        return path
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None

def extract_audio_url(driver):
    """Extract audio URL from Intron page - IMPROVED VERSION"""
    try:
        print("🔍 Searching for audio element...")
        
        # Method 1: Look for audio tag
        try:
            audio_elements = driver.find_elements(By.TAG_NAME, "audio")
            print(f"Found {len(audio_elements)} audio elements")
            for i, audio in enumerate(audio_elements):
                url = audio.get_attribute("src")
                if url:
                    print(f"✅ Method 1: Found audio URL from audio tag #{i}: {url[:80]}...")
                    return url
        except Exception as e:
            print(f"Method 1 error: {e}")
        
        # Method 2: Look for source tags inside audio
        try:
            source_elements = driver.find_elements(By.TAG_NAME, "source")
            print(f"Found {len(source_elements)} source elements")
            for i, source in enumerate(source_elements):
                url = source.get_attribute("src")
                if url and ".wav" in url.lower():
                    print(f"✅ Method 2: Found audio URL from source tag #{i}: {url[:80]}...")
                    return url
        except Exception as e:
            print(f"Method 2 error: {e}")
        
        # Method 3: Look for iframe with audio player
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"Found {len(iframes)} iframes")
            for i, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)
                    # Look for audio inside iframe
                    audio_in_frame = driver.find_elements(By.TAG_NAME, "audio")
                    for audio in audio_in_frame:
                        url = audio.get_attribute("src")
                        if url:
                            print(f"✅ Method 3: Found audio URL in iframe #{i}: {url[:80]}...")
                            driver.switch_to.default_content()
                            return url
                finally:
                    driver.switch_to.default_content()
        except Exception as e:
            print(f"Method 3 error: {e}")
        
        # Method 4: Search page source for .wav files
        try:
            page_source = driver.page_source
            # Look for various patterns that might contain audio URLs
            patterns = [
                r'src="([^"]*\.wav[^"]*)"',
                r'src=\'([^\']*\.wav[^\']*)\'',
                r'url\(\s*["\']?([^"\'\)]*\.wav[^"\'\)]*)["\']?\s*\)',
                r'https://[^"\'\s>]*\.wav[^"\'\s>]*',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    print(f"✅ Method 4: Found {len(matches)} audio URLs in page source")
                    for i, match in enumerate(matches[:3]):  # Show first 3 matches
                        print(f"   Match {i+1}: {match[:80]}...")
                    return matches[0]  # Return first match
        except Exception as e:
            print(f"Method 4 error: {e}")
        
        # Method 5: Look for audio player controls
        try:
            # Common audio player selectors
            audio_selectors = [
                "[data-audio-src]",
                "[data-src*='.wav']",
                ".audio-player",
                "[role='audio']",
                "video[src*='.wav']",  # Sometimes .wav files are in video tags
            ]
            
            for selector in audio_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    url = element.get_attribute("src") or element.get_attribute("data-src") or element.get_attribute("data-audio-src")
                    if url and ".wav" in url.lower():
                        print(f"✅ Method 5: Found audio URL from {selector}: {url[:80]}...")
                        return url
        except Exception as e:
            print(f"Method 5 error: {e}")
        
        print("❌ Could not find audio URL with any method")
        
        # DEBUG: Save page source for analysis
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            debug_file = os.path.join(BASE_DIR, f"debug_page_{timestamp}.html")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"📄 Saved page source to: {debug_file}")
        except:
            pass
            
        return None
        
    except Exception as e:
        print(f"❌ Error extracting audio URL: {e}")
        return None

def click_zulu_transcribe_project(driver):
    try:
        # Look for the Transcribe button in the table row containing "Zulu"
        xpath = "//tr[contains(., 'Zulu')]//a[contains(text(), 'Transcribe')]"
        btn = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        if safe_click(btn, driver):
            print("✅ Zulu Transcribe project clicked")
            return True
        return False
    except Exception as e:
        print(f"❌ click_zulu_transcribe_project error: {e}")
        # Alternative: Look for any Transcribe button
        try:
            transcribe_buttons = driver.find_elements(By.LINK_TEXT, "Transcribe")
            for btn in transcribe_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    safe_click(btn, driver)
                    print("✅ Transcribe button clicked")
                    return True
        except:
            pass
        return False

def upload_audio_to_gemini(driver, audio_file_path):
    """Upload audio file to Gemini chat"""
    try:
        print(f"📤 Uploading audio file to Gemini: {os.path.basename(audio_file_path)}")
        
        if not os.path.exists(audio_file_path):
            print(f"❌ Audio file not found: {audio_file_path}")
            return False
            
        file_size = os.path.getsize(audio_file_path)
        if file_size == 0:
            print("❌ Audio file is empty")
            return False
            
        print(f"📊 File size: {file_size} bytes")
        
        # Click plus button
        print("🔍 Looking for plus button...")
        plus_button_selectors = [
            "//mat-icon[@data-mat-icon-name='add_2']",
            "//button[.//mat-icon[@data-mat-icon-name='add_2']]",
            "//button[contains(@aria-label, 'Add')]",
        ]
        
        plus_button = None
        for selector in plus_button_selectors:
            try:
                plus_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                print(f"✅ Found plus button: {selector}")
                break
            except:
                continue
        
        if not plus_button:
            print("❌ Could not find plus button")
            return False
        
        print("➕ Clicking plus button...")
        safe_click(plus_button, driver)
        human_like_delay(1, 2)
        
        # Look for upload button
        print("🔍 Looking for upload button...")
        upload_button_selectors = [
            "//button[@data-test-id='local-images-files-uploader-button']",
            "//button[.//mat-icon[@data-mat-icon-name='attach_file']]",
            "//button[contains(., 'Upload files')]",
        ]
        
        upload_button = None
        for selector in upload_button_selectors:
            try:
                upload_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                print(f"✅ Found upload button: {selector}")
                break
            except:
                continue
        
        if not upload_button:
            print("❌ Could not find upload button")
            return False
        
        print("📎 Clicking upload button...")
        safe_click(upload_button, driver)
        human_like_delay(1, 2)
        
        # Find file input and send file path
        print("🔍 Looking for file input...")
        file_input_selectors = [
            "//input[@type='file']",
            "//input[@accept*='audio']",
            "//input[@accept*='.wav']",
        ]
        
        file_input = None
        for selector in file_input_selectors:
            try:
                file_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                print(f"✅ Found file input: {selector}")
                break
            except:
                continue
        
        if not file_input:
            print("❌ Could not find file input")
            return False
        
        print(f"⬆️  Sending file path to input: {audio_file_path}")
        file_input.send_keys(os.path.abspath(audio_file_path))
        print("✅ File path sent to input")
        
        # Wait for upload to complete
        print("⏳ Waiting for upload to complete...")
        human_like_delay(3, 4)
        
        # Check if upload was successful
        print("🔍 Checking upload confirmation...")
        confirmation_selectors = [
            "//div[contains(text(), 'Audio')]",
            "//div[contains(text(), '.wav')]",
            "//div[contains(@class, 'upload')]",
            "//div[contains(text(), 'Attached')]",
            "//div[contains(text(), 'Processing')]",
        ]
        
        for selector in confirmation_selectors:
            try:
                elem = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if elem:
                    print(f"✅ Upload confirmed: {elem.text[:50]}...")
                    return True
            except:
                continue
        
        print("⚠️ Upload confirmation not found, but continuing...")
        return True
            
    except Exception as e:
        print(f"❌ Error uploading to Gemini: {e}")
        return False

def send_transcribe_prompt(driver):
    """Send the ZULU transcription prompt to Gemini"""
    try:
        print("📝 Sending ZULU transcription prompt to Gemini...")
        
        specific_prompt = 'Transcribe this video in Zulu only. Do not include any headings, introductions, or English text. Provide only the raw Zulu transcription'
        
        # Find the chat input area
        input_selectors = [
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[@contenteditable='true' and contains(@aria-label, 'prompt')]",
            "//div[@contenteditable='true']",
        ]
        
        chat_input = None
        for selector in input_selectors:
            try:
                chat_input = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                print(f"✅ Found chat input: {selector}")
                break
            except:
                continue
        
        if not chat_input:
            print("❌ Could not find chat input")
            return False
        
        # Type the specific prompt
        print(f"⌨️  Typing Zulu transcription prompt...")
        try:
            chat_input.click()
            human_like_delay(0.5, 1)
            driver.execute_script("arguments[0].innerText = arguments[1];", chat_input, specific_prompt)
            print("✅ Zulu prompt typed")
            human_like_delay(1, 2)
        except Exception as e:
            print(f"⚠️ Error typing: {e}")
            try:
                chat_input.send_keys(specific_prompt)
            except:
                return False
        
        # Find and click send button
        print("🔍 Looking for send button...")
        send_selectors = [
            "//button[@aria-label*='send' or @aria-label*='Send']",
            "//button[contains(@class, 'send')]",
            "//mat-icon[contains(text(), 'send')]/ancestor::button",
        ]
        
        send_button = None
        for selector in send_selectors:
            try:
                send_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                print(f"✅ Found send button: {selector}")
                break
            except:
                continue
        
        if send_button:
            print("🔼 Clicking send button...")
            safe_click(send_button, driver)
            print("✅ Zulu transcription prompt sent!")
            return True
        else:
            print("❌ Could not find send button, trying Enter key...")
            chat_input.send_keys("\n")
            print("✅ Sent with Enter key")
            return True
            
    except Exception as e:
        print(f"❌ Error sending prompt: {e}")
        return False

def wait_for_gemini_transcription(driver, timeout=120):
    """Wait for Gemini's Zulu transcription response"""
    try:
        print("⏳ Waiting for Gemini's Zulu transcription...")
        
        # Wait for Gemini to process
        print("⏳ Waiting 10 seconds for Gemini to process the audio...")
        time.sleep(10)
        
        # Find the input field where we typed the prompt
        print("🔍 Locating our input field...")
        
        input_selectors = [
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[@contenteditable='true' and contains(@aria-label, 'prompt')]",
            "//div[@contenteditable='true']",
        ]
        
        input_field = None
        for selector in input_selectors:
            try:
                input_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                print(f"✅ Found input field: {selector}")
                break
            except:
                continue
        
        if not input_field:
            print("❌ Could not find input field")
            return ""
        
        # Get the location of the input field
        input_location = input_field.location
        input_y = input_location['y']
        print(f"📍 Input field location: Y={input_y}")
        
        # Look for text elements ABOVE the input field
        print("🔍 Looking for transcription text ABOVE the input field...")
        
        message_selectors = [
            "//div[@data-message-author-role='model']",
            "//div[contains(@class, 'model-response')]",
            "//div[contains(@class, 'message-content')]",
            "//div[contains(@class, 'markdown')]",
            "//div[contains(@class, 'message') and not(contains(@class, 'user'))]",
        ]
        
        best_candidate = None
        best_distance = float('inf')
        
        for selector in message_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                print(f"   Found {len(elements)} elements with: {selector}")
                
                for element in elements:
                    try:
                        elem_location = element.location
                        elem_y = elem_location['y']
                        
                        if elem_y < input_y:
                            distance = input_y - elem_y
                            elem_text = element.text.strip()
                            
                            # Skip if empty, too short, or contains unwanted content
                            if (not elem_text or 
                                len(elem_text) < 10 or
                                "Transcribe this video" in elem_text or
                                "Raw_clip_" in elem_text or
                                ".wav" in elem_text):
                                continue
                            
                            # Look for Zulu text
                            if distance < best_distance:
                                best_distance = distance
                                best_candidate = elem_text
                                print(f"   ✓ New best candidate (distance: {distance}px): {elem_text[:80]}...")
                    except:
                        continue
                        
            except Exception as e:
                print(f"   ⚠️ Error with selector {selector}: {e}")
                continue
        
        # If we found a candidate, clean it up
        if best_candidate:
            print(f"✅ Found Zulu transcription text ({len(best_candidate)} chars):")
            print(f"📝 Preview: {best_candidate[:200]}...")
            
            # Clean the transcription text
            zulu_text = clean_zulu_transcription(best_candidate)
            return zulu_text
        
        # Fallback - try to get the most recent model response
        print("🔄 Fallback: Trying to get latest model response...")
        try:
            model_responses = driver.find_elements(By.XPATH, "//div[@data-message-author-role='model']")
            if model_responses:
                last_response = model_responses[-1]
                response_text = last_response.text.strip()
                
                if response_text and len(response_text) > 10:
                    print(f"✅ Using latest model response ({len(response_text)} chars)")
                    return clean_zulu_transcription(response_text)
        except:
            pass
        
        print("❌ Could not find Zulu transcription text")
        return ""
        
    except Exception as e:
        print(f"❌ Error getting transcription: {e}")
        return ""

def clean_zulu_transcription(text):
    """Clean up Zulu transcription text - remove English, headings, etc."""
    if not text:
        return ""
    
    # Remove common prefixes and English text
    prefixes_to_remove = [
        "Transcription:",
        "Zulu Transcription:",
        "Zulu:",
        "Here is",
        "Sure,",
        "Okay,",
        "Alright,",
        "Here's",
        "The transcription",
    ]
    
    for prefix in prefixes_to_remove:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    
    # Remove any English sentences
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip lines that are clearly English
        if line.startswith(("Transcribe", "Please", "Note:", "Remember:")):
            continue
        
        # Keep the line
        cleaned_lines.append(line)
    
    cleaned_text = ' '.join(cleaned_lines)
    
    # Clean punctuation and spacing
    cleaned_text = re.sub(r'\s+\.', '.', cleaned_text)
    cleaned_text = re.sub(r'\s+,', ',', cleaned_text)
    cleaned_text = re.sub(r'\s+\?', '?', cleaned_text)
    cleaned_text = re.sub(r'\s+!', '!', cleaned_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    return cleaned_text

def fill_intron_textarea(driver, zulu_text):
    """Fill the single Intron textarea with Zulu transcription"""
    try:
        print("📝 Filling Intron textarea with Zulu transcription...")
        
        # Find textarea on the page
        textarea = None
        
        # Try different selectors for the textarea
        textarea_selectors = [
            "//textarea[@id='textBoxArea']",
            "//textarea[@id='predicted']",
            "//textarea",
            "//textarea[@placeholder]",
        ]
        
        for selector in textarea_selectors:
            try:
                textarea = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                print(f"✅ Found textarea: {selector}")
                break
            except:
                continue
        
        if not textarea:
            print("❌ Could not find textarea")
            return False
        
        # Clear and fill the textarea
        print("🇿🇦 Filling Zulu transcription into textarea...")
        driver.execute_script("arguments[0].value = '';", textarea)
        driver.execute_script("arguments[0].value = arguments[1];", textarea, zulu_text)
        print(f"✅ Zulu text filled: {zulu_text[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error filling textarea: {e}")
        return False

def click_submit_button(driver):
    """Click the submit button on Intron - UPDATED with correct ID"""
    try:
        print("🔼 Looking for submit button...")
        
        # UPDATED: Using the correct ID from your HTML
        submit_selectors = [
            "//span[@id='submit_btn_text']",  # NEW: Your correct ID
            "//button[contains(., 'Submit Transcript')]",  # Also look for button with this text
            "//button[contains(., 'Submit')]",
            "//input[@type='submit']",
            "//button[@type='submit']",
            "//button[contains(@class, 'submit')]",
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                print(f"   Trying selector: {selector}")
                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                print(f"✅ Found submit button: {selector}")
                break
            except Exception as e:
                print(f"   Not found with {selector}: {e}")
                continue
        
        if not submit_button:
            print("❌ Could not find submit button with any selector")
            
            # Additional debugging: Look for any element with id containing 'submit'
            try:
                all_elements = driver.find_elements(By.XPATH, "//*[contains(@id, 'submit')]")
                print(f"🔍 Found {len(all_elements)} elements with 'submit' in ID:")
                for elem in all_elements:
                    elem_id = elem.get_attribute('id') or ''
                    elem_text = elem.text or ''
                    print(f"   - ID: {elem_id}, Text: {elem_text[:50]}")
            except:
                pass
                
            return False
        
        print("📤 Clicking submit button...")
        safe_click(submit_button, driver)
        print("✅ Submission sent!")
        
        # Wait for submission to process
        human_like_delay(2, 3)
        
        # Check for any alerts
        try:
            alert = driver.switch_to.alert
            alert.accept()
            print("✅ Alert accepted")
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"❌ Error clicking submit: {e}")
        return False

def wait_for_new_audio_url(driver, previous_url=None, timeout=60):
    """Wait for a new audio URL to appear"""
    print("⏳ Waiting for new audio clip...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            current_url = extract_audio_url(driver)
            
            if current_url and current_url != previous_url:
                print(f"🎵 New audio URL detected: {current_url[:50]}...")
                return current_url
            
        except Exception as e:
            print(f"⚠️ Error checking audio URL: {e}")
        
        time.sleep(3)
    
    print("❌ No new audio URL found")
    return None

def main():
    print("🤖 Starting Zulu Transcription Bot with Gemini")
    print("=" * 70)
    print("WORKFLOW: Download → Gemini Transcribe (Zulu only) → Fill → Submit → Repeat")
    print("=" * 70)
    
    # Create a custom Chrome profile
    chrome_profile_dir = os.path.join(BASE_DIR, "chrome_profile")
    os.makedirs(chrome_profile_dir, exist_ok=True)
    
    options = Options()
    options.add_argument(f"user-data-dir={chrome_profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("detach", True)
    
    driver = None
    
    try:
        # STEP 1: Open Chrome
        print("\n" + "="*60)
        print("🔵 STEP 1: Opening Chrome browser...")
        print("="*60)
        
        print("🚀 Launching Chrome...")
        driver = webdriver.Chrome(options=options)
        print("✅ Chrome opened successfully!")
        
        # STEP 2: Open Intron website
        print("\n" + "="*60)
        print("🔵 STEP 2: Opening Intron website...")
        print("="*60)
        
        print("🌐 Navigating to Intron...")
        driver.get("https://speech.intron.health/")
        print("✅ Intron website loaded")
        
        print("\n" + "="*60)
        print("🟡 MANUAL ACTION REQUIRED!")
        print("Please LOGIN to Intron website manually")
        print("="*60)
        
        # Wait for user to login
        print("⏳ Waiting for you to login to Intron...")
        WebDriverWait(driver, 300).until(EC.presence_of_element_located((By.LINK_TEXT, "Transcribe")))
        print("✅ Intron login successful!")
        
        # STEP 3: Navigate to Zulu Transcribe project
        print("\n" + "="*60)
        print("🔵 STEP 3: Navigating to Zulu Transcribe project...")
        print("="*60)
        
        if not click_zulu_transcribe_project(driver):
            print("❌ Could not open Zulu Transcribe project. Stopping.")
            return
            
        # Click Start Transcribing button
        start_btn = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.LINK_TEXT, "Start Transcribing")))
        safe_click(start_btn, driver)
        print("✅ On transcription page")
        
        # Wait for the page to fully load
        print("⏳ Waiting for page to load fully...")
        time.sleep(5)
        
        # Check if we're on the right page
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//audio | //textarea | //span[@id='submit_btn_text']"))
            )
            print("✅ Transcription interface loaded")
        except:
            print("⚠️ Could not confirm transcription interface loaded, but continuing...")
        
        clip_count = 0
        previous_audio_url = None
        
        while True:
            clip_count += 1
            print(f"\n{'='*60}")
            print(f"🎯 PROCESSING CLIP #{clip_count}")
            print(f"{'='*60}")
            
            # STEP 4: Get audio URL and download
            print("🔍 Looking for audio URL...")
            audio_url = None
            max_wait_time = 30
            start_time = time.time()
            
            while not audio_url and (time.time() - start_time < max_wait_time):
                audio_url = extract_audio_url(driver)
                if not audio_url:
                    print("⏳ Waiting for audio URL...")
                    time.sleep(2)
            
            if not audio_url:
                print("❌ Failed to find audio URL after multiple attempts")
                print("🔄 Refreshing page and trying again...")
                driver.refresh()
                human_like_delay(3, 5)
                
                # Try one more time after refresh
                audio_url = extract_audio_url(driver)
                if not audio_url:
                    print("❌ Still no audio URL found, skipping this clip")
                    continue
            
            if audio_url == previous_audio_url and clip_count > 1:
                print("⚠️ Same audio URL, waiting for new clip...")
                time.sleep(5)
                
                if clip_count > 3 and audio_url == previous_audio_url:
                    print("🔄 Refreshing page to get new clip...")
                    driver.refresh()
                    human_like_delay(3, 5)
                continue
            
            previous_audio_url = audio_url
            
            # Download the audio
            print("📥 Downloading audio...")
            raw_audio_file = download_audio(audio_url, clip_count)
            if not raw_audio_file:
                print("❌ Failed to download audio")
                continue
            
            print(f"✅ Downloaded: {os.path.basename(raw_audio_file)}")
            
            # STEP 5: Open/switch to Gemini tab
            if len(driver.window_handles) < 2:
                print("🌐 Opening Gemini tab...")
                driver.execute_script("window.open('', '_blank');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get("https://gemini.google.com")
                print("✅ Gemini tab opened")
                
                print("\n" + "="*60)
                print("🟡 MANUAL ACTION REQUIRED!")
                print("Please LOGIN to Gemini/Google manually")
                print("Wait for Gemini to fully load")
                print("="*60)
                try:
                    input("Press ENTER when you're logged into Gemini and ready to continue...")
                except EOFError:
                    print("⚠️ Input interrupted, continuing automatically...")
            else:
                print("🔄 Switching to Gemini tab...")
                driver.switch_to.window(driver.window_handles[1])
                print("✅ Switched to Gemini tab")
            
            # STEP 6: Upload audio to Gemini
            print("\n" + "="*60)
            print("🔵 UPLOADING TO GEMINI...")
            print("="*60)
            
            if not upload_audio_to_gemini(driver, raw_audio_file):
                print("❌ Failed to upload to Gemini")
                driver.switch_to.window(driver.window_handles[0])
                continue
            
            # STEP 7: Send Zulu transcribe prompt
            print("\n" + "="*60)
            print("🔵 SENDING ZULU TRANSCRIBE PROMPT...")
            print("="*60)
            
            if not send_transcribe_prompt(driver):
                print("❌ Failed to send transcribe prompt")
                driver.switch_to.window(driver.window_handles[0])
                continue
            
            # STEP 8: Wait for Zulu transcription
            print("\n" + "="*60)
            print("🔵 WAITING FOR ZULU TRANSCRIPTION...")
            print("="*60)
            
            zulu_text = wait_for_gemini_transcription(driver, timeout=120)
            
            if not zulu_text:
                print("❌ No Zulu transcription received")
                driver.switch_to.window(driver.window_handles[0])
                continue
            
            print(f"✅ Zulu transcription received ({len(zulu_text)} chars):")
            print(f"   🇿🇦 Zulu: {zulu_text[:150]}...")
            
            # STEP 9: Switch back to Intron
            print("\n" + "="*60)
            print("🔵 RETURNING TO INTRON...")
            print("="*60)
            
            driver.switch_to.window(driver.window_handles[0])
            print("✅ Switched back to Intron tab")
            
            # STEP 10: Fill single textarea and submit
            print("\n" + "="*60)
            print("🔵 FILLING & SUBMITTING...")
            print("="*60)
            
            if fill_intron_textarea(driver, zulu_text):
                print("✅ Textarea filled successfully")
                
                if click_submit_button(driver):
                    print(f"✅ Clip #{clip_count} completed successfully!")
                else:
                    print("⚠️ Submit failed")
            else:
                print("❌ Failed to fill textarea")
            
            # Clean up audio file
            if os.path.exists(raw_audio_file):
                try:
                    os.remove(raw_audio_file)
                    print(f"🗑️  Cleaned up: {os.path.basename(raw_audio_file)}")
                except:
                    pass
            
            # Wait before next clip
            print("⏳ Waiting before next clip...")
            human_like_delay(3, 5)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return
    except Exception as e:
        print(f"❌ Bot encountered an error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        print("\n🛑 Bot execution completed.")
        print(f"📁 Files saved in: {TEMP_AUDIO_DIR}")

if __name__ == "__main__":
    main()