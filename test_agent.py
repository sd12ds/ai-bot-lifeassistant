from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI

load_dotenv("api.env")

print("KEY:", os.getenv("OPENAI_API_KEY"))

llm = ChatOpenAI(model="gpt-4o-mini")

response = llm.invoke("Скажи привет с сервера Ubuntu")

print(response.content)
