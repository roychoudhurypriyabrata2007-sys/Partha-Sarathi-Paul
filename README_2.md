# Voice Language Tutor

Asks your name → your language → language to learn → section, then teaches aloud.
Uses Sarvam AI (`sarvam-m` for teaching, `bulbul:v2` for voice).

```bash
pip install requests
export SARVAM_API_KEY="your_key"     # Windows: set SARVAM_API_KEY=your_key
python tutor.py                      # --no-voice for text only, --save-audio out/ to keep clips
```

Languages: English, Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Odia.
Audio plays through afplay / ffplay / mpg123 / aplay / paplay (or winsound on Windows).
In a lesson: type an answer or question, or `next`, `repeat`, `menu`, `quit`.
