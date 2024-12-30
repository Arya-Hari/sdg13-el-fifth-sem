import re
import requests
import logging
from flask import Flask, request, jsonify
from typing import List, Tuple
import json
import uuid
import numpy as np
from utils import StopWatch
from pyngrok import ngrok

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
QA_USER_PROMPT_TEMPLATE = """You are an eco-shopping assistant designed to assist users in making better shopping decisions. 
The user will enter the name of an item they are looking to purchase. 
Given the context information and using prior knowledge, precisely provide exactly one simple homemade recipe, as a healthy alternative, for the user to try instead.
Precisely provide information about some brands that sell healthier alternatives in India. Derive this information solely from the context. If no valid information is provided in the context, do not include this component in the answer.
Avoid formal phrases like "based on the context information" or "from the provided data", as well as information about the item. Keep your tone friendly and helpful.
Context information is below. Each line is a separate document from the internet about a specific topic or person.
{context}

Question: {question}

Answer:"""

# SearxNG search function
def search_internet(query: str, searxng_endpoint: str, top_k: int = 5) -> List[dict]:
    """Search the internet using SearxNG."""
    try:
        result = re.findall(r'\((.*?)\)', query)
        query_final = f"Healthy {result[0]} brands in India" if result else query
        response = requests.get(
            f"{searxng_endpoint}/search",
            params={"q": query_final, "format": "json"},
            timeout=5
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return results[:top_k]
    except Exception as e:
        logger.error(f"Error during SearxNG search: {e}")
        return []

# Fetch context documents
def get_context_documents(
    query: str,
    urls: List[str],
    titles: List[str],
    snippets: List[str],
    top_k_documents: int,
    top_k_nodes: int,
    top_k_snippets: int | None,
    num_nodes_rerank: int,
    min_score: float,
) -> Tuple[List[str], List[str], List[bool]]:
    """Fetch context documents for the query."""
    logger.info("Requesting top %d web pages", len(urls[:top_k_documents]))

    with StopWatch() as sw:
        # Simulating webpage fetch as actual fetching is not implemented
        webpages = [snippets[:top_k_documents]]  # Replace with actual webpage fetch logic
        logger.info("Fetched %d web pages in %f ms", len(webpages), sw.elapsed())

    context_titles = []
    context_documents = []
    context_is_snippet = []
    successful_webpages = 0

    for url, title, snippet, full_webpage_nodes in zip(
        urls[:top_k_documents], titles[:top_k_documents], snippets[:top_k_documents], webpages
    ):
        url_id = uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:8]
        if successful_webpages >= top_k_documents:
            break

        if full_webpage_nodes:
            successful_webpages += 1
            top_nodes = full_webpage_nodes[:num_nodes_rerank]
            context_titles.append(title)
            context_documents.append(" ".join([snippet] + top_nodes))
            context_is_snippet.append(False)
        else:
            context_titles.append(title)
            context_documents.append(snippet)
            context_is_snippet.append(True)

    if top_k_snippets is not None:
        num_docs = len(context_documents)
        if num_docs < top_k_snippets:
            context_titles += titles[num_docs:top_k_snippets]
            context_documents += snippets[num_docs:top_k_snippets]
            context_is_snippet += [True] * (top_k_snippets - num_docs)

    return context_titles, context_documents, context_is_snippet

# Process search results
def process_results(results: List[dict], query: str) -> str:
    urls = [r["url"] for r in results]
    titles = [r["title"] for r in results]
    snippets = [r.get("content", "").strip(" ...") + "." for r in results]

    context_titles, context_documents, context_is_snippet = get_context_documents(
        query=query,
        urls=urls,
        titles=titles,
        snippets=snippets,
        top_k_documents=3,
        top_k_nodes=5,
        top_k_snippets=None,
        num_nodes_rerank=100,
        min_score=0.01,
    )

    documents = list(zip(context_titles, context_documents))
    if not documents:
        return "No information found"

    context = "\n".join([f"{title} - {text}" for title, text in documents])
    return context

# Query local LLM using Ollama
def query_ollama_local(context: str, question: str, model_name: str = "llama3.2") -> str:
    """Generate a response locally using an Ollama model."""
    prompt = QA_USER_PROMPT_TEMPLATE.format(context=context, question=question)
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model_name, "prompt": prompt},
            timeout=30,
            stream=True  # Enable streaming
        )
        response.raise_for_status()

        # Process the streamed JSON lines
        final_response = ""
        for line in response.iter_lines():
            if line:
                try:
                    json_line = json.loads(line)
                    final_response += json_line.get("response", "")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON line: {line}. Error: {e}")

        return final_response.strip()

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error querying Ollama: {e}")
        return "Error generating a response."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Error generating a response."

# Flask app
app = Flask(__name__)

@app.route('/query', methods=['POST'])
def query():
    data = request.json
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"error": "Empty query"}), 400

    searxng_endpoint = "http://127.0.0.1:8080/" 
    results = search_internet(query, searxng_endpoint)
    if not results:
        return jsonify({"error": "No results found"}), 404

    context = process_results(results, query)
    response = query_ollama_local(context, query)

    return jsonify({
        "context": context,
        "response": response
    })

if __name__ == "__main__":
    # Expose the Flask app locally
    public_url = ngrok.connect(5000).public_url
    print(f"Ngrok URL: {public_url}")
    app.run(port=5000)