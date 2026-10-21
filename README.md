# STS-AI

A simple command-line text summarizer powered by the Google Gemini API.
Paste any text, and the model returns a clear, concise summary.

## Features

- Interactive chat loop in the terminal
- Concise summaries with low randomness (`temperature=0.2`)
- Output capped at 1000 tokens
- API key loaded from a `.env` file, never hardcoded

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## Setup

1. Clone the repository:

```
   git clone https://github.com/rokia776/STS-AI.git
   cd STS-AI
```

2. Install the dependencies:

```
   uv sync
```

3. Create a `.env` file in the project root and add your key:

```
   GEMINI_API_KEY=your_api_key_here
```

   The `.env` file is listed in `.gitignore`, so it will not be pushed to GitHub.

## Usage

```
uv run ai-sts
```

You will see:

```
--- Summarizer Ready (Type 'exit' to quit) ---
>
```

Paste the text you want summarized and press Enter. Type `exit` to quit.

## Configuration

The model settings are in `src/ai_sts/__init__.py`:

| Setting | Value | Description |
|---|---|---|
| `model` | `gemini-3.5-flash` | Gemini model used (change it if your key has access to another one) |
| `temperature` | `0.2` | Lower values give more focused, consistent summaries |
| `max_output_tokens` | `1000` | Maximum length of each summary |
| `system_instruction` | summarizer prompt | Tells the model how to behave |

## Project Structure

```
.
├── src/ai_sts/
│   └── __init__.py     # main application code
├── pyproject.toml      # project and dependency settings
├── uv.lock             # locked dependency versions
├── .env                # your API key (not committed)
└── README.md
```

## Troubleshooting

- **API key not valid:** check that `.env` contains `GEMINI_API_KEY=...` with no spaces or quotes.
- **404 / model not found:** change the model name in `__init__.py` to one available for your key.
- **429 / quota exceeded:** you reached the free usage limit; wait a bit and try again.
- **`uv` is not recognized:** restart VS Code or your terminal so the updated PATH loads.

## Security

Never commit your API key. If it is ever pushed by mistake, delete it in Google AI Studio and create a new one.
