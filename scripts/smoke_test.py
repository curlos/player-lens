"""Smoke test: one tiny Azure OpenAI call and one tiny Azure Speech call, with the cost of each.

Run from the repo root:  python scripts/smoke_test.py [output.mp3] [--only llm|speech]

Reads the keys from .env (never printed). Standard library only, so there is nothing to install.
Expected cost: a fraction of a cent. Prices come from .env (LLM) and Azure's pricing page (Speech).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEECH_PRICE_PER_1M_CHARS = 15.0  # standard Neural voices, East US (azure.microsoft.com/pricing/details/speech)
SPEECH_BITRATE = 48_000  # bits per second of the "audio-24khz-48kbitrate-mono-mp3" format
TEXT = "GOAL! Lima fires it home, and Azure lead 3-2!"


def load_env() -> None:
    """Copies KEY=value lines from .env into os.environ (values already set win)."""
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def require(*names: str) -> None:
    """Exits with the names of any variables that are missing or empty (never their values)."""
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        sys.exit("Missing or empty in .env: " + ", ".join(missing) + "\nFill them in, save the file, and run again.")


def post(url: str, headers: dict[str, str], body: bytes) -> bytes:
    """POST and return the response bytes; on an HTTP error print its status and message, then exit."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        sys.exit(f"HTTP {err.code} from {url.split('?')[0]}\n{err.read().decode()[:500]}")


def test_llm() -> None:
    require("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT", "LLM_PRICE_IN_PER_1M", "LLM_PRICE_OUT_PER_1M")
    # The v1 API needs no api-version. Only the host of the pasted endpoint is used, so a full
    # ".../openai/v1/responses" URL works too.
    host = urllib.parse.urlparse(os.environ["AZURE_OPENAI_ENDPOINT"])
    url = f"{host.scheme}://{host.netloc}/openai/v1/chat/completions"
    body = {
        "model": os.environ["AZURE_OPENAI_DEPLOYMENT"],  # on this API the deployment name goes in the body
        "messages": [{"role": "user", "content": "Write one short football commentary line for a late winning goal."}],
        "max_tokens": 40,
    }
    key = os.environ["AZURE_OPENAI_API_KEY"]
    headers = {"api-key": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    reply = json.loads(post(url, headers, json.dumps(body).encode()))

    tokens_in = reply["usage"]["prompt_tokens"]
    tokens_out = reply["usage"]["completion_tokens"]
    cost = (tokens_in * float(os.environ["LLM_PRICE_IN_PER_1M"]) + tokens_out * float(os.environ["LLM_PRICE_OUT_PER_1M"])) / 1e6
    print("LLM reply:", reply["choices"][0]["message"]["content"])
    print(f"LLM tokens: {tokens_in} in, {tokens_out} out -> ${cost:.6f}")


def test_speech(out_path: Path) -> None:
    require("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")
    region = os.environ["AZURE_SPEECH_REGION"]
    voice = os.environ.get("SPEECH_VOICE_EN_CASUAL") or "en-US-GuyNeural"
    ssml = f"<speak version='1.0' xml:lang='en-US'><voice name='{voice}'>{TEXT}</voice></speak>"
    headers = {
        "Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "player-lens-smoke-test",
    }
    audio = post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1", headers, ssml.encode())
    out_path.write_bytes(audio)

    chars = len(TEXT)  # Speech bills the spoken text, not the SSML tags
    print(f"Speech: voice {voice}, {chars} characters -> ${chars * SPEECH_PRICE_PER_1M_CHARS / 1e6:.6f}")
    print(f"Speech clip: {len(audio)} bytes, about {len(audio) * 8 / SPEECH_BITRATE:.1f} s, saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", default="smoke_test.mp3", help="where to save the Speech clip")
    parser.add_argument("--only", choices=["llm", "speech"], help="run just one of the two calls")
    args = parser.parse_args()

    load_env()
    if args.only != "speech":
        test_llm()
    if args.only != "llm":
        test_speech(Path(args.output))
