from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

def main():
    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=1000,
        system_instruction="You are a professional summarizer. Summarize the given text clearly and concisely."
    )


    chat = client.chats.create(model="gemini-3.5-flash", config=config)

    print("--- Summarizer Ready (Type 'exit' to quit) ---")
    while True:
        msg = input("> ")
        if msg.lower() == "exit":
            break
        
        response = chat.send_message(msg)
        print("\nSummary:")
        print(response.text)
        print("-" * 30)

if __name__ == "__main__":
    main()