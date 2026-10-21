from ollama import chat

text = input(" Write here : ")

response = chat(
    model='llama3.1',
    messages=[
        {'role': 'system', 'content': 'Summarize the following text in a few simple and clear sentences.'},
        {'role': 'user', 'content': text},
    ],
)

print("/n Summary:")
print(response.message.content)