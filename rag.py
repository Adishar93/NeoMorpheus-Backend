import os
from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import QdrantClient
import dotenv

from kindo_api import KindoAPI

dotenv.load_dotenv()

def retrieve_relevant_documents(query, top_k=5):
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_KEY"),
    )

    embed_model = OpenAIEmbedding(api_key=os.getenv("OPENAI_API_KEY"))

    # Generate query embedding
    query_embedding = embed_model.get_text_embedding(query)
    
    # Search in Qdrant
    search_result = qdrant_client.search(
        collection_name="arxiv_papers",
        query_vector=query_embedding,
        limit=top_k
    )
    
    # Extract and return the text of relevant documents
    relevant_docs = [hit.payload["text"] for hit in search_result]
    return relevant_docs

# 5. Generate article based on user prompt
def generate_article(prompt):
    kindo_api = KindoAPI(api_key=os.getenv("KINDO_API_KEY"))

    relevant_docs = retrieve_relevant_documents(prompt)
    print(f"Found {len(relevant_docs)} relevant documents")
    
    # Combine relevant documents into a single context
    context = "\n\n".join(relevant_docs)

    summarized_context = kindo_api.call_kindo_api(model="azure/gpt-4o", messages=[{"role": "user", "content": f"Summarize this content into 100 words. Content: {context}"}], max_tokens=200).json()['choices'][0]['message']['content']
    
    # Generate article using OpenAI
    rabbit_prompt = f"Give keywords related to this information: {summarized_context}. Dont give any excess output."
    response = kindo_api.call_kindo_api(
        model="/models/WhiteRabbitNeo-33B-DeepSeekCoder", 
        messages=[{"role": "user", "content": rabbit_prompt}], 
        max_tokens=500
    )

    if 'error' not in response:
        rabbit_response = response.json()['choices'][0]['message']['content']
    else:
        print(f"API call failed: {response['error']}, details: {response.get('details')}")
        rabbit_response = ""

    gpt_prompt = f"User question: {prompt} Generate a well designed course as paragraphs(word limit on each paragraph is 20) on topic. Strictly use only the following information as reference: Knowledge Source 1: {context} Knowledge Source 2: {rabbit_response}. The reader is a subject expert in the field so the article should be detailed and informative. avoid special characters like '*' or '#' keep it plain text with basic formatting."
    messages = [
        {
            "role": "user", 
            "content": gpt_prompt 
        }
    ]
    article = kindo_api.call_kindo_api(model="azure/gpt-4o", messages=messages, max_tokens=2000).json()['choices'][0]['message']['content']

    return article