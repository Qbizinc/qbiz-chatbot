import streamlit as st
import os
from llama_index import StorageContext, load_index_from_storage
import json
from openai import OpenAI
from llama_index.vector_stores import DeepLakeVectorStore
from llama_index.storage.storage_context import StorageContext
from llama_index import VectorStoreIndex

def get_llama_index():

    vector_store = DeepLakeVectorStore(
        dataset_path="hub://coursestudent/LlamaIndex_main",
        runtime={"tensor_db": True},
        read_only=True
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context)

    return index

def run_app():

    st.title("QBiz Chatbot \n LlamaIndex and DeepLake")

    if "messages" not in st.session_state.keys():
        st.session_state.messages = [
            {"role": "assistant",
             "content": "Ask Me Anything about QBiz internal Documentation!"}
        ]

    st.write('---')

    # Load index from the storage context
    new_index = get_llama_index()
    new_query_engine = new_index.as_query_engine()
    
    openai_client = OpenAI(
       api_key=os.environ["OPENAI_API_KEY"],
    )

    if query_string := st.chat_input("Your Question"):
        st.session_state.messages.append({"role": "user",
                                          "content": query_string})
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            


    


    # If last message is not from assistant, generate a new response
    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                llama_response = new_query_engine.query(query_string)

                st.write(llama_response.response)
                message = {"role": "assistant", "content": llama_response}
                st.session_state.messages.append(message)  # Add response to message history



if __name__ == "__main__":
    run_app()
