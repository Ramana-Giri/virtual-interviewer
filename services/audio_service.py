import os
import json
import numpy as np
import parselmouth
from parselmouth.praat import call
from groq import Groq
from moviepy import VideoFileClip
import config


class AudioService:
    def __init__(self):
        print("⏳ Initializing Audio Service (Groq + Parselmouth)...")
        # Ensure you have GROQ_API_KEY in your config.py
        self.client = Groq(api_key=config.GROQ_API_KEY)

    def extract_audio_from_video(self, video_path):
        """Extracts audio from video file and saves as .wav"""
        try:
            audio_path = video_path.replace(".mp4", ".wav").replace(".webm", ".wav")
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, logger=None)
            video.close()  # Good practice to close the handle
            return audio_path
        except Exception as e:
            print(f"❌ Audio Extraction Error: {e}")
            return None

    def analyze(self, video_path):
        print(f"🎙️ Analyzing Audio: {video_path}")

        # 1. Extract .wav (Required for Praat & Groq)
        audio_path = self.extract_audio_from_video(video_path)
        if not audio_path: return {"error": "Audio extraction failed"}

        # 2. Groq Transcription (The Speed & Timestamps)
        # We request 'verbose_json' to get the "Game Tape" timestamps
        try:
            with open(audio_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_path, file.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )

            # Extract text and the 'words' list (critical for timeline)
            transcript_text = transcription.text
            # Depending on Groq SDK version, this might be an object or dict.
            # We handle both.
            groq_json = transcription.to_dict() if hasattr(transcription, 'to_dict') else transcription

        except Exception as e:
            print(f"❌ Groq API Error: {e}")
            # Fallback for offline testing if needed
            transcript_text = ""
            groq_json = {}

        # 3. Scientific Metrics (The Physics - Global Averages)
        # Keeping your existing logic
        global_metrics = self._get_acoustic_metrics(audio_path, transcript_text)

        # 4. Frame-Level Metrics (The "Timeline" Data)
        # New: Get Pitch/Volume for every 100ms (10fps) to match video
        frame_log = self._get_frame_metrics(audio_path)

        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)

        return {
            "transcript": transcript_text,
            "groq_json": groq_json,  # Contains the timestamped words
            "global_metrics": global_metrics,  # For the "Scoreboard"
            "frame_log": frame_log  # For the "Timeline"
        }

    def _get_acoustic_metrics(self, audio_path, transcript):
        """Existing Logic: Global Averages for Jitter, Pitch, WPM"""
        sound = parselmouth.Sound(audio_path)
        duration = sound.get_total_duration()

        word_count = len(transcript.split())
        wpm = (word_count / duration) * 60 if duration > 0 else 0

        pitch = sound.to_pitch()
        pitch_values = pitch.selected_array['frequency']
        pitch_values = pitch_values[pitch_values != 0]  # Remove silence

        if len(pitch_values) == 0:
            return {"wpm": 0, "avg_pitch": 0, "pitch_var": 0, "jitter": 0}

        avg_pitch = np.mean(pitch_values)
        pitch_std = np.std(pitch_values)

        # Jitter (Micro-tremors)
        point_process = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100

        return {
            "wpm": int(wpm),
            "avg_pitch_hz": round(avg_pitch, 2),
            "pitch_variance": round(pitch_std, 2),
            "jitter_percent": round(jitter, 2),
            "duration_seconds": round(duration, 2)
        }

    def _get_frame_metrics(self, audio_path):
        """
        New Logic: Slices audio into 100ms chunks (10fps)
        to sync perfectly with the video analysis.
        """
        sound = parselmouth.Sound(audio_path)
        pitch_obj = sound.to_pitch(time_step=0.1)  # 0.1s = 10fps step
        intensity_obj = sound.to_intensity(time_step=0.1)

        frames = []
        duration = sound.get_total_duration()

        # Iterate every 0.1s (100ms)
        for t in np.arange(0, duration, 0.1):
            # Get Pitch at this moment
            p = pitch_obj.get_value_at_time(t)
            p = p if not np.isnan(p) else 0  # 0 means Silence/Unvoiced

            # FIX: Use get_value(t) for Intensity, not get_value_at_time
            v = intensity_obj.get_value(t)
            v = v if not np.isnan(v) else 0

            frames.append({
                "timestamp": round(t, 2),
                "pitch": round(p, 1),
                "volume": round(v, 1)
            })

        return frames


if __name__ == '__main__':
    # Update this path to a real video file you have!
    test_video = "uploads/sample.mp4"

    if not os.path.exists(test_video):
        print(f"❌ Error: File '{test_video}' not found. Please check the path.")
    else:
        print(f"🚀 Testing AudioService on {test_video}...")
        service = AudioService()
        result = service.analyze(test_video)

        # --- DUMP THE FULL JSON ---
        print("\n" + "=" * 60)
        print("📜 FULL JSON OUTPUT")
        print("=" * 60)

        # This prints everything indented nicely
        print(json.dumps(result, indent=2))

        print("=" * 60)