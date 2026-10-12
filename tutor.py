#!/usr/bin/env python3
"""Voice language tutor agent (Sarvam AI: chat + text-to-speech).

Flow: name -> your language -> language to learn -> section -> lesson loop.
Run:   export SARVAM_API_KEY=...   then   python tutor.py
Flags: --no-voice (text only), --save-audio DIR (keep the mp3/wav files)
"""
import argparse, base64, os, re, subprocess, sys, tempfile, shutil, time
import requests

API = "https://api.sarvam.ai"
CHAT_MODEL = "sarvam-m"
TTS_MODEL = "bulbul:v2"

LANGS = {  # name -> (BCP-47 code for TTS, default speaker)
    "english": ("en-IN", "anushka"), "hindi": ("hi-IN", "anushka"),
    "bengali": ("bn-IN", "anushka"), "tamil": ("ta-IN", "anushka"),
    "telugu": ("te-IN", "anushka"), "kannada": ("kn-IN", "anushka"),
    "malayalam": ("ml-IN", "anushka"), "marathi": ("mr-IN", "anushka"),
    "gujarati": ("gu-IN", "anushka"), "punjabi": ("pa-IN", "anushka"),
    "odia": ("od-IN", "anushka"),
}
SECTIONS = {
    "1": "Greetings & introductions",
    "2": "Alphabet / script & pronunciation",
    "3": "Numbers, days & time",
    "4": "Everyday phrases (shopping, travel, food)",
    "5": "Basic grammar",
    "6": "Vocabulary builder",
    "7": "Conversation practice (role-play)",
    "8": "Quiz me",
}

# ---------------------------------------------------------------- helpers
def key():
    k = os.environ.get("SARVAM_API_KEY")
    if not k:
        sys.exit("Set SARVAM_API_KEY first:  export SARVAM_API_KEY=your_key")
    return k

def hdr():
    return {"api-subscription-key": key(), "Content-Type": "application/json"}

def pick_language(text):
    t = text.strip().lower()
    if t in LANGS:
        return t
    for name in LANGS:
        if name.startswith(t) and t:
            return name
    return None

def ask_language(prompt):
    while True:
        a = input(prompt).strip()
        l = pick_language(a)
        if l:
            return l
        print("  Supported:", ", ".join(n.title() for n in LANGS))

# ---------------------------------------------------------------- voice
PLAYER = None
def find_player():
    for cmd in (["afplay"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
                ["mpg123", "-q"], ["aplay", "-q"], ["paplay"]):
        if shutil.which(cmd[0]):
            return cmd
    return None

def play(path):
    global PLAYER
    if sys.platform.startswith("win"):
        import winsound; winsound.PlaySound(path, winsound.SND_FILENAME); return
    if PLAYER is None:
        PLAYER = find_player() or []
    if PLAYER:
        subprocess.run(PLAYER + [path], check=False)

def chunks(text, n=450):
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?।])\s+", text):
        if len(cur) + len(s) + 1 > n and cur:
            parts.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur: parts.append(cur)
    return parts

def speak(text, lang_code, speaker, voice_on, save_dir=None, counter=[0]):
    if not voice_on or not text.strip():
        return
    for part in chunks(text):
        try:
            r = requests.post(f"{API}/text-to-speech", headers=hdr(), timeout=60, json={
                "text": part, "target_language_code": lang_code,
                "speaker": speaker, "model": TTS_MODEL, "pace": 0.95,
                "speech_sample_rate": 22050})
            r.raise_for_status()
            audio = base64.b64decode(r.json()["audios"][0])
        except Exception as e:
            print(f"  (voice unavailable: {e})"); return
        counter[0] += 1
        if save_dir:
            path = os.path.join(save_dir, f"line_{counter[0]:03d}.wav")
        else:
            fd, path = tempfile.mkstemp(suffix=".wav"); os.close(fd)
        with open(path, "wb") as f: f.write(audio)
        play(path)
        if not save_dir: os.remove(path)

# ---------------------------------------------------------------- brain
def system_prompt(user, native, target, section):
    return f"""You are a warm, patient voice language tutor.
Student: {user}. Their language: {native.title()}. Learning: {target.title()}.
Current section: {section}.

You are heard aloud, so keep every turn SHORT (max ~6 lines), friendly, no markdown, no emojis.
Explain in {native.title()}. Give {target.title()} examples in the {target.title()} script,
followed by an easy romanization in brackets when the script differs from Latin.
Format EVERY line with a prefix so it can be spoken in the right voice:
  N: <text in {native.title()}>   (explanations)
  T: <text in {target.title()}>   (words/phrases to pronounce)
Teach one small chunk at a time (3-5 items), then ask the student to repeat or answer one
tiny question. Correct mistakes gently. Never output <think> text."""

def chat(history):
    for attempt in range(3):
        try:
            r = requests.post(f"{API}/v1/chat/completions", headers=hdr(), timeout=90, json={
                "model": CHAT_MODEL, "messages": history, "temperature": 0.5, "max_tokens": 700})
            r.raise_for_status()
            out = r.json()["choices"][0]["message"]["content"]
            return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
        except Exception as e:
            if attempt == 2: raise
            time.sleep(1.5)

def render(reply, native, target, voice_on, save_dir):
    ncode, nspk = LANGS[native]; tcode, tspk = LANGS[target]
    for line in reply.splitlines():
        line = line.strip()
        if not line: continue
        m = re.match(r"^([NT])\s*[:：]\s*(.*)$", line)
        who, text = (m.group(1), m.group(2)) if m else ("N", line)
        print(("  " if who == "N" else "  ▶ ") + text)
        # strip romanization in brackets for speech so it isn't read twice
        spoken = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", text) if who == "T" else text
        speak(spoken or text, tcode if who == "T" else ncode,
              tspk if who == "T" else nspk, voice_on, save_dir)

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--save-audio", metavar="DIR")
    a = ap.parse_args()
    voice_on = not a.no_voice
    if a.save_audio: os.makedirs(a.save_audio, exist_ok=True)
    key()

    print("=== Voice Language Tutor ===")
    user = input("Hi! What's your name? ").strip() or "Friend"
    native = ask_language(f"Nice to meet you, {user}! Which language do you speak? ")
    target = ask_language("Which language do you want to learn? ")
    if target == native:
        print("  Those are the same — pick a different language to learn.")
        target = ask_language("Which language do you want to learn? ")

    speak(f"Hello {user}! Let's learn {target.title()} together.", "en-IN", "anushka",
          voice_on, a.save_audio)

    while True:
        print(f"\nWhat would you like to learn, {user}?")
        for k, v in SECTIONS.items(): print(f"  {k}. {v}")
        print("  q. Quit")
        c = input("> ").strip().lower()
        if c in ("q", "quit", "exit"): break
        section = SECTIONS.get(c) or (c if len(c) > 2 else None)
        if not section:
            continue
        history = [{"role": "system", "content": system_prompt(user, native, target, section)},
                   {"role": "user", "content": "Start the lesson."}]
        print(f"\n--- {section} --- (type your answer or a question; 'next', 'repeat', 'menu', 'quit')")
        while True:
            try:
                reply = chat(history)
            except Exception as e:
                print(f"  Tutor error: {e}"); break
            history.append({"role": "assistant", "content": reply})
            render(reply, native, target, voice_on, a.save_audio)
            msg = input("\nyou> ").strip()
            low = msg.lower()
            if low in ("menu", "m"): break
            if low in ("quit", "q", "exit"): return
            if low == "repeat":
                render(reply, native, target, voice_on, a.save_audio); msg = "repeat"
                history.append({"role": "user", "content": "Please repeat that more slowly."})
                continue
            history.append({"role": "user", "content": "Next item." if low in ("", "next", "n") else msg})
    print(f"Goodbye {user}! Keep practising.")

if __name__ == "__main__":
    main()
