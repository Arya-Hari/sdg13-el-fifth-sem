import re
import requests
import logging
from typing import List
import json

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
QA_SYSTEM_PROMPT = "You are an eco-shopping assistant designed to assist users in making better shopping decisions."
QA_USER_PROMPT_TEMPLATE = """Context information is below. Each line is a separate document from the internet about a specific topic or person.
{context}
The user will enter the name of an item they are looking to purchase. Do not make assumptions about the brand of the item.
Given the context information and using prior knowledge, precisely provide exactly one simple healthy homemade recipe for the user to try instead.
Also, if there exists brands within India that sell healthy versions of the item, precisely mention them. Derive this information solely on the context provided. If nothing is appropriate, do not mention them. Only mention them if available.
Avoid formal phrases like "based on the context information" or "from the provided data", as well as information about the item. Keep your tone friendly and helpful.

Question: {question}

Answer:"""

# SearxNG search function
def search_internet(query: str, searxng_endpoint: str, top_k: int = 3) -> List[dict]:
    """Search the internet using SearxNG."""
    try:
        result = query.split("-")[-1].strip()
        query_final = "Healthy"+result+"brands in India"
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

# Process search results
def process_results(results: List[dict]) -> str:
    """Extract context from search results."""
    context = []
    for result in results:
        title = result.get("title", "No title")
        snippet = result.get("content", "No content")
        context.append(f"{title}: {snippet}")
    return "\n".join(context)

# Query local LLM using Ollama
def query_ollama_local(context: str, question: str, model_name: str = "llama3.2") -> str:
    """Generate a response locally using an Ollama model."""
    prompt = QA_USER_PROMPT_TEMPLATE.format(context=context, question=question)
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",  # Replace with your Ollama API endpoint
            json={"model": model_name, "prompt": prompt},
            timeout=30,
            stream=True  # Enable streaming
        )
        response.raise_for_status()

        # Process the streamed JSON lines
        final_response = ""
        for line in response.iter_lines():
            if line:  # Skip empty lines
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


def main():
    # User inputs
    searxng_endpoint = "http://127.0.0.1:8080/"  # Replace with your SearxNG instance

    query = input("Enter the item: ").strip()
    if not query:
        print("Empty question. Exiting.")
        return

    # Step 1: Search the internet
    results = search_internet(query, searxng_endpoint)
    if not results:
        print("No results found.")
        return

    # Step 2: Process search results into context
    context = process_results(results)

    # Step 3: Generate response using Ollama
    response = query_ollama_local(context, query)

    # Print the response
    print("\nLlama Response:\n")
    print(response)

if __name__ == "__main__":
    main()
