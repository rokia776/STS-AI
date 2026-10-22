# Text Summarizer (Ollama + Python)

A simple Python script that takes text from the user at runtime and summarizes it in English using a local LLM running through [Ollama](https://ollama.com). No API key and no internet connection are needed after the model is downloaded.

## Requirements

- Windows, macOS, or Linux
- Python 3.9+
- [Ollama](https://ollama.com/download) installed and running
- About 2 GB of free disk space for the `llama3.2:1b` model

## Setup

1. **Install Ollama**

   On Windows (PowerShell):
   ```
   irm https://ollama.com/install.ps1 | iex
   ```

2. **Install the Python library** (use the same Python you run the script with):
   ```
   python -m pip install ollama
   ```
   If you use `uv`:
   ```
   uv pip install ollama
   ```

3. **Download the model:**
   ```
   ollama pull llama3.2:1b
   ```
   Wait until it prints `success`. Check with `ollama list`.

### Optional: store models on another drive

If your C: drive is low on space, set the models folder before starting Ollama:

```
mkdir D:\ollama
setx OLLAMA_MODELS "D:\ollama"
```

Then fully quit Ollama, restart VS Code (or your terminal), and start Ollama again.

## Usage

Run the script from the project folder:

```
python src\ai_sts\assignment1.py
```

Paste your text when prompted and press Enter. The summary is printed in the terminal.

Example:
```
 Write here : <your text>

 Summary:
<short summary in English>
```

## How it works

```python
from ollama import chat

text = input(" Write here : ")

response = chat(
    model='llama3.2:1b',
    messages=[
        {'role': 'system', 'content': 'Summarize the following text in a few simple and clear sentences.'},
        {'role': 'user', 'content': text},
    ],
)

print("\n Summary:")
print(response.message.content)
```

- The `system` message tells the model what to do.
- The `user` message is the text you typed.
- `response.message.content` is the generated summary.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'ollama'` | Install the library with `python -m pip install ollama` using the same Python as the script. |
| `model 'llama3.2:1b' not found (404)` | The model is not downloaded yet. Run `ollama pull llama3.2:1b`. |
| `ollama` is not recognized | Restart VS Code/terminal, make sure Ollama is installed and running. |
| `There is not enough space on the disk` | Free space on C: or set `OLLAMA_MODELS` to another drive (see above). |
| Only the first line of a pasted text is summarized | `input()` reads one line only. Paste the text as a single line. |

## Notes

- You can switch to a stronger model (e.g. `llama3.2:3b` or `llama3.1`) by pulling it and changing the `model=` value in the script.
- `.env` is not needed for this project, since no API key is used.
