import requests
from pprint import pprint

url = "https://api.intelligence.io.solutions/api/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": "",
}

data = {
    "model": "mistralai/Ministral-8B-Instruct-2410",
    "messages": [
        {
            "role": "system",
            "content": "Your name is Legend. You are a chatbot created by DeepSeek AI. You are a friendly chatbot that can help users with their questions and provide information on a variety of topics. You are always learning and improving to provide the best experience for users. How can I help you today?"
        },
        {
            "role": "user",
            "content": "how are you doing"
        }
    ],
}

response = requests.post(url, headers=headers, json=data)
data = response.json()
pprint(data) 

text = data['choices'][0]['message']['content']
print(text)
