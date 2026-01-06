import whisper
import parselmouth
from parselmouth.praat import call
import numpy as np
import librosa
import os
import config

class AudioService:
    def __init__(self):
        print("⏳ Loading Whisper Model (Base)... This happens only once.")
        # 'base' is a good balance of speed vs accuracy. 
        # Use 'tiny' if your PC is very slow, or 'small' if you have a GPU.
        self.model = whisper.load_model("base")

    def extract_audio_from_video(self, video_path):
        """
        Extracts audio from video file and saves as .wav for Praat analysis
        """
        try:
            audio_path = video_path.replace(".mp4", ".wav").replace(".webm", ".wav")
            # Librosa load automatically converts to mono/wav format in memory
            # But Praat needs a physical file. We use ffmpeg via system command or moviepy.
            # For MVP simplicity, let's assume ffmpeg is installed or use moviepy if needed.
            # Here is a robust way using moviepy (which installs with librosa usually)
            from moviepy import VideoFileClip
            
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, logger=None)
            return audio_path
        except Exception as e:
            print(f"❌ Audio Extraction Error: {e}")
            return None

    def analyze(self, video_path):
        """
        Main function that coordinates the lab analysis.
        """
        print(f"🎙️ Analyzing Audio: {video_path}")
        
        # 1. Extract .wav file (Required for Praat)
        audio_path = self.extract_audio_from_video(video_path)
        if not audio_path: return {"error": "Audio extraction failed"}

        # 2. Transcription (The Content)
        result = self.model.transcribe(audio_path)
        transcript = result["text"].strip()
        print(f"📝 Transcript: {transcript[:50]}...")

        # 3. Scientific Metrics (The Physics)
        metrics = self._get_acoustic_metrics(audio_path, transcript)
        
        # Cleanup temp file
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return {
            "transcript": transcript,
            "metrics": metrics
        }

    def _get_acoustic_metrics(self, audio_path, transcript):
        """
        Uses Parselmouth (Praat) to detect Jitter/Shimmer/Pitch
        """
        sound = parselmouth.Sound(audio_path)
        duration = sound.get_total_duration()
        
        # A. Speaking Rate (WPM)
        word_count = len(transcript.split())
        wpm = (word_count / duration) * 60 if duration > 0 else 0
        
        # B. Pitch Analysis (F0)
        pitch = sound.to_pitch()
        pitch_values = pitch.selected_array['frequency']
        # Remove zeros (unvoiced parts like silence)
        pitch_values = pitch_values[pitch_values != 0]
        
        if len(pitch_values) == 0:
            return {"wpm": 0, "jitter": 0, "pitch_var": 0}

        avg_pitch = np.mean(pitch_values)
        pitch_std = np.std(pitch_values) # High SD = Expressive; Low SD = Monotone

        # C. Jitter (Nervousness Micro-Tremors)
        # We create a "PointProcess" to analyze the pulses of the vocal cords
        point_process = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        
        # "Local Jitter" is the standard metric for vocal stability
        # Normal is < 1%. Stress/Pathology is > 1.04%
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100

        # D. Pauses (Silence detection)
        # Simple logic: count segments with zero pitch that are longer than 0.5s
        # (For MVP, we stick to basic WPM as the fluency proxy)

        return {
            "wpm": int(wpm),
            "avg_pitch_hz": round(avg_pitch, 2),
            "pitch_variance": round(pitch_std, 2),
            "jitter_percent": round(jitter, 2),
            "duration_seconds": round(duration, 2)
        }