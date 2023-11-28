import os.path
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io
import html2text
from openai import OpenAI
import re
import math
import json

client = OpenAI(
  
   api_key=os.environ["OPENAI_API_KEY"],
)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.metadata.readonly"]


def main():
  """Shows basic usage of the Drive v3 API.
  Prints the names and ids of the first 10 files the user has access to.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("drive", "v3", credentials=creds)
    
    text_blocks = text_blocks_for_drive_content(service)
    
    embedding_list = create_embeddings(text_blocks)
    
    print(embedding_list[:100])



  except HttpError as error:
    # TODO(developer) - Handle errors from drive API.
    print(f"An error occurred: {error}")

def create_embeddings(text_blocks):

    embedding_list = []
    for text_block in text_blocks:
        embeddings = client.embeddings.create(
            input= text_block["text_block"],
            model="text-embedding-ada-002"
        )
        embedding_list.append(embeddings)
    return embedding_list
      
def text_blocks_for_drive_content(service):

    # Call the Drive v3 API
    results = (
        service.files()
        .list(q="visibility != 'limited' and mimeType='application/vnd.google-apps.document'", pageSize=1, fields="nextPageToken, files(id, name, mimeType)")
        .execute()
    )
    items = results.get("files", [])

    if not items:
      print("No files found.")
      return
    
    text_blocks = []
    print("Files:")
    for item in items:
      print(f"{item['name']} ({item['id']}) ({item['mimeType']})")
      #https://medium.com/@matheodaly.md/using-google-drive-api-with-python-and-a-service-account-d6ae1f6456c2
      try:
        request_file = service.files().export_media(fileId=item['id'], mimeType='text/html').execute()
        text = html2text.html2text(str(request_file))
        text_blocks.extend(text_blocks_for_a_file(item['name'], text, 300, 10, True))
        #with open(f"downloaded_file_{item['name']}.jsonl", "w") as f:
        #    f.write(json.dumps(record) + "\n")
      except HttpError as error:
         # TODO(developer) - Handle errors from drive API.
        print(f"An error occurred: {error}")
      pass
    return text_blocks
  

def text_blocks_for_a_file(file_name, text_content, words_per_block, buffer_length, remove_urls):

    if remove_urls:
        text_content = re.sub(r'http\S+', '', text_content)
    list_of_words = text_content.split()
    # create word blocks
    n_o_blocks = math.ceil(len(list_of_words)/words_per_block)
    array_of_blocks = []
    for i in range(n_o_blocks):
        start_word = i*words_per_block
        end_word = (i+1)*words_per_block + buffer_length #take extra words (These will be overlapping between blocks, which is intended. Imperfect effort not to cut blocks in the middle of sentence) 
        block = {
            "block_id": f"{file_name}_block_{i}",
            "text_block": ' '.join(list_of_words[start_word:end_word])
        }
        array_of_blocks.append(block)
    return array_of_blocks
    
            
if __name__ == "__main__":
  main()
