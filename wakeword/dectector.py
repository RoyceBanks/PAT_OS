# PAT OS v0.1
# Wake Word Detection Module
# Uses OpenWakeWord

import openwakeword
from openwakeword.model import Model

import sounddevice as sd
import numpy as np


SAMPLE_RATE = 16000
CHANNELS = 1

WAKE_WORD = "hey_pat"


class WakeWordDetector:

    def __init__(self):
        print("Loading PAT wake word system...")

        self.model = Model(
            wakeword_models=[
                WAKE_WORD
            ]
        )

        print("Wake word system ready.")


    def listen(self):

        print("Waiting for 'Hey Pat'...")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16"
        ) as microphone:

            while True:

                audio, _ = microphone.read(1280)

                audio = np.squeeze(audio)

                prediction = self.model.predict(audio)

                score = prediction[WAKE_WORD]

                if score > 0.5:

                    print("Wake word detected!")

                    return True



def listen_for_wake_word():

    detector = WakeWordDetector()

    while True:

        if detector.listen():

            return True