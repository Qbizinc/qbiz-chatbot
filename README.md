Qbiz-chatbot

This repo includes implementation for creating a questions answering machine using a RAG model. Model utilizes OpenAI gpt-3.5-turbo model for the text generation and understanging, and text2vec-openai for searching relevant content from additional data, which in our case is QBiz internal documentation. 
Code reads QBiz Google Drive content, creates and stores vectors in Weaviate database and answers questions.

In order to run the code you need to:

Create a Service Account with the Google Cloud Platform

Enable Google Drive API on your Google Cloud Platform Project

Install and import needed Libraries

Create the connection to the Drive API and create Google Drive API key

Create OpenAI account and API key.

Create Weaviate account and API key.

Reference for using Drive API: https://medium.com/@matheodaly.md/using-google-drive-api-with-python-and-a-service-account-d6ae1f6456c2

