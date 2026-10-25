from ollama import chat

text = input(" Write here : ")

response = chat(
    model='llama3.2:1b',
    messages=[
        {
            'role': 'system',
            'content': 'Summarize the following text in exactly three sentences.',
        },
        {'role': 'user', 'content': text},
    ],
    options={
        'temperature': 0.3,
        'num_predict': 150,
    },
)

print("\n Summary:")
print(response.message.content)
