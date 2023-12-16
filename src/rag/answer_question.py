import weaviate
import json
import os
from openai import OpenAI


query_string = input("Enter your question regarding QBiz's internal documentation: ")

weaviate_client = weaviate.Client(
    url = "https://weviate-cluster-xom22sd6.weaviate.network",  # Replace with your endpoint
    auth_client_secret=weaviate.AuthApiKey(api_key=os.environ["WEVIATE_API_KEY"]),  # Replace w/ your Weaviate instance API key
    additional_headers = {
        "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]  # Replace with your inference API key
    }
)

openai_client = OpenAI(
   api_key=os.environ["OPENAI_API_KEY"],
)

weaviate_response = (
    weaviate_client.query
    .get("Text_block", ["text_block"])
    .with_near_text({"concepts": [query_string]})
    .with_limit(3)
    .do()
)

additional_context = [w["text_block"] for w in  weaviate_response["data"]["Get"]["Text_block"]]
joined_texts = '\n\n'.join([a for a in additional_context])

system_prompt = f"""I want you to answer a user query using only the following source texts as references: {joined_texts}.
Include the referenced document in the answer."""


completion = openai_client.chat.completions.create(
  model="gpt-3.5-turbo",
  messages=[
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": query_string}
  ]
)
print(completion.choices[0].message)

