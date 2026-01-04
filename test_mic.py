import speech_recognition as sr
import numpy as np


def list_microphones():
    print("\n--- AVAILABLE AUDIO DEVICES ---")
    mics = sr.Microphone.list_microphone_names()
    for index, name in enumerate(mics):
        print(f"Index {index}: {name}")
    print("-------------------------------")
    return len(mics)


def test_mic(index):
    recognizer = sr.Recognizer()
    try:
        # We explicitly tell it to use the specific index you chose
        with sr.Microphone(device_index=index) as source:
            print(f"\n🎤 Testing Device Index {index}...")
            print("Please speak into the mic now...")

            # Adjust for noise
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            # Listen for a short burst
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)

            # Calculate RMS
            raw_data = audio.get_raw_data()
            audio_data = np.frombuffer(raw_data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data ** 2))

            print(f"📊 RMS VALUE: {int(rms)}")

            if rms == 0:
                print("❌ RESULT: Dead Silence (Wrong Mic)")
            elif rms < 100:
                print("⚠️ RESULT: Very Quiet (Check Input Volume)")
            else:
                print("✅ RESULT: Working! This is the correct index.")

    except Exception as e:
        print(f"❌ Error accessing device {index}: {e}")


if __name__ == "__main__":
    count = list_microphones()
    while True:
        try:
            choice = input("\nEnter the Index number of your mic to test (or 'q' to quit): ")
            if choice.lower() == 'q': break
            test_mic(int(choice))
        except ValueError:
            print("Please enter a number.")