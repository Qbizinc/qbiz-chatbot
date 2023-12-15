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
import requests
import weaviate
from weaviate.exceptions import UnexpectedStatusCodeException
import PyPDF2


def main():


  # Google API scopes: If modifying these scopes, delete the file token.json.
  SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.metadata.readonly"]

  """Drive v3 API.
  Prints the names and ids of the first n files the user has access to.
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

    with open(f"qbiz_drive_files_file.jsonl", "w") as f:
      f.write(json.dumps(text_blocks))
    
    create_weaviate_data(text_blocks)



  except HttpError as error:
    # TODO(developer) - Handle errors from drive API.
    print(f"An error occurred: {error}")

def create_weaviate_data(text_blocks):
  
    client = weaviate.Client(
      url = "https://weviate-cluster-xom22sd6.weaviate.network",  # Replace with your endpoint
      auth_client_secret=weaviate.AuthApiKey(api_key=os.environ["WEVIATE_API_KEY"]),  # Replace w/ your Weaviate instance API key
      additional_headers = {
          "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]  # Replace with your inference API key
      }
    )

   # ===== define collection =====
    class_obj = {
        "class": "Text_block",
        "vectorizer": "text2vec-openai",  # If set to "none" you must always provide vectors yourself. Could be any other "text2vec-*" also.
        "moduleConfig": {
            "text2vec-openai": {},
            "generative-openai": {}  # Ensure the `generative-openai` module is used for generative queries
        }
    }
    client.schema.delete_class("Text_block")
    try:
      client.schema.create_class(class_obj)
    except UnexpectedStatusCodeException as exception:
      print(exception)
      pass

    client.batch.configure(batch_size=100)  # Configure batch
    with client.batch as batch:  # Initialize a batch process
        for i, d in enumerate(text_blocks):  # Batch import data
            print(f"importing text-block: {i+1}", d["block_id"])
            properties = {
                "text_block": d["block_id"],
                "text_block": d["text_block"],
            }
            batch.add_data_object(
                data_object=properties,
                class_name="Text_block"
            )
      
def text_blocks_for_drive_content(service):

    # Call the Drive v3 API
    query_str = "not ('aino.nyblom@qbizinc.com' in owners)" \
    + "and (name contains '.pdf' or mimeType='application/vnd.google-apps.document')" \
    + "and modifiedTime > '2020-01-01T12:00:00'"
    
    results = (
        service.files()
#        .list(q=query_str, pageSize=1000, fields="nextPageToken, files(id, name, mimeType)") #max page size = 1000
        .list(pageSize=1000, fields="nextPageToken, files(id, name, mimeType)") #max page size = 1000
        .execute()
    )
    items = results.get("files", [])
    print(len(items), " files found")

    if not items:
      print("No files found.")
      return
    text_blocks = []
    print("Files:")
    for item in items:
      print(f"{item['name']} ({item['id']}) ({item['mimeType']})")
      text_blocks.extend(text_blocks_for_google_docs(item, service))
      text_blocks.extend(text_blocks_for_pdfs(item, service))                     

    return text_blocks

def text_blocks_for_google_docs(item, service):
  #https://medium.com/@matheodaly.md/using-google-drive-api-with-python-and-a-service-account-d6ae1f6456c2
  if item['mimeType'] == "application/vnd.google-apps.document":
    request_file = service.files().export_media(fileId=item['id'], mimeType='text/html').execute()
    text = html2text.html2text(str(request_file))
    return text_blocks_for_a_file(item['name'], text, 300, 10, True)
  else:
    return []
  
def text_blocks_for_pdfs(item, service):
  if item['name'][-3:] == "pdf":
    request_file = service.files().get_media(fileId=item['id'])
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request_file)
    done = False
    while done is False:
      status, done = downloader.next_chunk()
      file_retrieved: str = file.getvalue()
      file_io = io.BytesIO(file_retrieved)
      pdf_file = PyPDF2.PdfReader(file_io)
      text = ""

      # Loop through each page and extract text
      for page_num in range(len(pdf_file.pages)):
        page = pdf_file.pages[page_num]
        text += page.extract_text()
        return text_blocks_for_a_file(item['name'], text, 300, 10, True)
  else:
    return []

        
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
            "text_block": file_name + ': ' + ' '.join(list_of_words[start_word:end_word])
        }
        array_of_blocks.append(block)
    return array_of_blocks
    
            
if __name__ == "__main__":
  main()
