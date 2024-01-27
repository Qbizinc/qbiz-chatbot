import os.path
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io
from openai import OpenAI
import re
import math
import json
import requests
import PyPDF2
from llama_index.schema import Document
from llama_index.vector_stores import DeepLakeVectorStore
from llama_index.storage.storage_context import StorageContext
from llama_index import VectorStoreIndex


def main():
  
  service = get_google_drive_api_service()
  
  documents_as_llama_docs = []
  for filetype in ['document', 'presentation', 'spreadsheet', 'pdf']:
      items = get_drive_metadata_list_by_filetype(service, filetype)
      documents_as_llama_by_type = load_documents_as_llama(service, items, filetype)
      #print(documents_as_llama_by_type)
      documents_as_llama_docs.extend(documents_as_llama_by_type)

  create_llama_index(documents_as_llama_docs)


def create_llama_index(docs):

    vector_store = DeepLakeVectorStore(
        token=os.environ["ACTIVELOOP_TOKEN"],
        dataset_path="hub://coursestudent/LlamaIndex_main",
        overwrite=True,
        runtime={"tensor_db": True})

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(docs, storage_context=storage_context)

#Define parameters and variables needed for Google Drive API  connection and return Google Drive API service.
def get_google_drive_api_service():

  # Google API scopes: If modifying these scopes, delete the file token.json.
  SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.metadata.readonly"]

  #Drive v3 API. Prints the names and ids of the first n files the user has access to.
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    print("token.json found")
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

  return build("drive", "v3", credentials=creds)


# Call the Google drive API to retrieve a list of filenames (and other metadata).
# List returned only includes metadata, not the content of the file.
def get_drive_metadata_list_by_filetype(service, filetype):

    if filetype == 'pdf':
        query_str_filetype = "and name contains '.pdf'"
    else:
        query_str_filetype = f"and mimeType='application/vnd.google-apps.{filetype}'"
        
    query_str = "not ('aino.nyblom@qbizinc.com' in owners)" \
              + "and not (name contains 'career development' or name contains 'Career Development' or name contains 'Snowflake Program Acceleration') " \
              + query_str_filetype + "and (modifiedTime > '2020-01-01')"

    results = (
        service.files()
        .list(q=query_str, pageSize=1, includeItemsFromAllDrives=True, supportsAllDrives=True, fields="nextPageToken, files(id, name, mimeType)") #max page size = 1000
        .execute()
    )

    items = results.get("files", [])
    print(len(items), " files found")

    if not items:
      print("No files found.")
      return None

    else:
      return items

      
def load_documents_as_llama(service, items, filetype):

  if filetype in ('document', 'presentation'):
    text_files = google_doc_and_presentation_as_llama_doc(service, items)
  elif filetype == 'spreadsheet':
    text_files = google_spreadsheet_as_llama_doc(service, items)
  elif filetype == 'pdf':
    text_files = pdf_in_google_drive_as_llama_doc(service, items)
  return text_files

      
def google_doc_and_presentation_as_llama_doc(service, items):
  
    llama_docs = []
    print("Files:")
    for item in items:
      print(f"{item['name']} ({item['id']}) ({item['mimeType']})")
      request_file = service.files().export_media(fileId=item['id'], mimeType='text/plain').execute()
      text = str(request_file)
      llama_docs.append(Document(id_=item['id'], text=text, metadata=item))
                  
    return llama_docs

def google_spreadsheet_as_llama_doc(service, items):
  
    llama_docs = []
    print("Files:")
    for item in items:
      print(f"{item['name']} ({item['id']}) ({item['mimeType']})")
      request_file = service.files().export_media(fileId=item['id'], mimeType='text/csv').execute()
      text = str(request_file)
      llama_docs.append(Document(id_=item['id'], text=text, metadata=item))

    return llama_docs

def pdf_in_google_drive_as_llama_doc(service, items):
  
    llama_docs = []
    print("Files:")
    for item in items:
      print(f"{item['name']} ({item['id']}) ({item['mimeType']})")
      text = read_pdf_from_google_drive(service, item)
      llama_docs.append(Document(id_=item['id'], text=text, metadata=item))

    return llama_docs
  
def read_pdf_from_google_drive(service, item):
  
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
    return text

  
            
if __name__ == "__main__":
  main()
