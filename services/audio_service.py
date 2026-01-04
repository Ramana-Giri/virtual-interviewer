import speech_recognition as sr
from textblob import TextBlob
import numpy as np
import config
import opensmile
import os
import tempfile
import soundfile as sf


class AudioService:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Initialize OpenSMILE with eGeMAPSv02 feature set
        self.smile = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.Functionals,
        )

    def listen_and_analyze(self):
        result = {
            "text": "",
            "sentiment": "Neutral",
            "energy": "Medium",
            "status": "Listening"
        }

        with sr.Microphone() as source:
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print(">>> LISTENING...")

                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=8)
                print(">>> PROCESSING...")

                # 1. Save audio to temp file for OpenSMILE
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                    temp_wav.write(audio.get_wav_data())
                    temp_wav_path = temp_wav.name

                # 2. Extract Features using OpenSMILE
                try:
                    df = self.smile.process_file(temp_wav_path)
                    
                    # Extract Features
                    # Pitch: F0semitoneFrom27.5Hz_sma3nz_amean
                    # Loudness: loudness_sma3_amean
                    # Jitter: jitterLocal_sma3nz_amean
                    # Shimmer: shimmerLocaldB_sma3nz_amean
                    # Rate of Speech: VoicedSegmentsPerSec
                    
                    pitch = df['F0semitoneFrom27.5Hz_sma3nz_amean'].values[0]
                    loudness = df['loudness_sma3_amean'].values[0]
                    jitter = df['jitterLocal_sma3nz_amean'].values[0]
                    shimmer = df['shimmerLocaldB_sma3nz_amean'].values[0]
                    speech_rate = df['VoicedSegmentsPerSec'].values[0]
                    
                    print(f"Pitch: {pitch:.2f}, Loudness: {loudness:.2f}, Jitter: {jitter:.4f}, Shimmer: {shimmer:.2f}, Rate: {speech_rate:.2f}")

                    # Enhanced Heuristic Emotion Classification
                    # Thresholds are estimated and may need tuning
                    
                    # Happy/Excited: High Pitch, High Loudness, Fast Rate, Stable Voice (Low Jitter)
                    if pitch > 30 and loudness > 1.5 and speech_rate > 2.5 and jitter < 0.02:
                        result["sentiment"] = "Happy/Excited"
                        result["energy"] = "High"
                    
                    # Angry: High Pitch, High Loudness, Fast Rate, Rough Voice (High Jitter)
                    elif pitch > 30 and loudness > 1.5 and speech_rate > 2.5 and jitter > 0.03:
                        result["sentiment"] = "Angry"
                        result["energy"] = "High"
                        
                    # Fear/Nervous: High Pitch, Low Loudness, Fast Rate, Shaky Voice (High Jitter)
                    elif pitch > 30 and loudness < 0.5 and speech_rate > 2.5 and jitter > 0.03:
                        result["sentiment"] = "Fear/Nervous"
                        result["energy"] = "Low"
                        
                    # Sad: Low Pitch, Low Loudness, Slow Rate, Shaky Voice
                    elif pitch < 20 and loudness < 0.5 and speech_rate < 1.5:
                        result["sentiment"] = "Sad"
                        result["energy"] = "Low"
                        
                    else:
                        result["sentiment"] = "Neutral"
                        result["energy"] = "Medium"

                except Exception as e:
                    print(f"OpenSMILE Error: {e}")
                    # Fallback to simple energy
                    audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_data ** 2))
                    if rms < config.RMS_THRESHOLD_LOW:
                        result["energy"] = "Low"
                    elif rms > config.RMS_THRESHOLD_HIGH:
                        result["energy"] = "High"
                    else:
                        result["energy"] = "Medium"

                finally:
                    # Cleanup temp file
                    if os.path.exists(temp_wav_path):
                        os.remove(temp_wav_path)

                # 3. STT (Speech to Text)
                try:
                    text = self.recognizer.recognize_google(audio)
                    result["text"] = text
                    
                except sr.UnknownValueError:
                    pass # No speech detected

                result["status"] = "Success"

            except Exception as e:
                print(f"Audio Error: {e}")
                result["status"] = "Error"

        return result