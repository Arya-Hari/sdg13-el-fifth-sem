from flask import Flask, request, render_template_string, jsonify
import re
import requests
import logging
import os
from typing import List, Tuple
import uuid
from utils import StopWatch
import pytesseract
from PIL import Image
import json
import easyocr
import cv2

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QA_USER_PROMPT_TEMPLATE_SHOPPING = """You are an eco-shopping assistant designed to assist users in making better shopping decisions. 
The user will enter the name of an item they are looking to purchase. 
Given the context information and using prior knowledge, precisely provide exactly one simple homemade recipe, as a healthy alternative, for the user to try instead.
Precisely provide information about some brands that sell healthier alternatives in India. Derive this information solely from the context. If no valid information is provided in the context, do not include this component in the answer.
Avoid formal phrases like "based on the context information" or "from the provided data", as well as information about the item. Keep your tone friendly and helpful.
Context information is below. Each line is a separate document from the internet about a specific topic or person.
{context}

Question: {question}

Answer:"""

QA_USER_PROMPT_TEMPLATE_RECYCLING = """You are an eco-recycling assistant designed to assist users in making more of their waste. 
The user will enter the name of an item they are looking to recycle. 
Given the context information and using prior knowledge, precisely provide exactly one simple method to recycle the item into something innovative.
Precisely provide information about how to dispose of the item so that it is environmentally healthy and safe.
Avoid formal phrases like "based on the context information" or "from the provided data", as well as information about the item. Keep your tone friendly and helpful.
Context information is below. Each line is a separate document from the internet about a specific topic or person.
{context}

Question: {question}

Answer:"""

# Real time webscraping
def get_eco_score(product_name):
    # Search for the product on OpenFoodFacts
    x = requests.get(f'https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&sort_by=unique_scans_n&page_size=50?sort_by=environmental_score_score')
    
    pattern = r'"url":"https://world\.openfoodfacts\.org/product/[^\s">]+"'
    matches = re.finditer(pattern, x.text)

    # Get the 5th product URL // is based on highest clicks
    c = 0
    for match in matches:
        c+=1
        url = match.group(0)
        if(c == 5):
            break
        

    print(f"Product URL: {url[7:-1]}")

    # Fetch the product page
    x = requests.get(url[7:-1])  # Fetch the product page

    # Regex pattern to extract Eco-Score information
    eco_score_pattern = r'\bGreen-Score\b(?:\s+[A-F][+-]?)'
    matches = re.finditer(eco_score_pattern, x.text)

    # Extract and return the Eco-Score
    for match in matches:
        return match.group(0)

    return "Eco-Score not found"

# Function to extract headings using EasyOCR
def extract_heading(image_path):
    # Initialize EasyOCR Reader
    reader = easyocr.Reader(['en'])

    # Load the image using OpenCV
    image = cv2.imread(image_path)

    # Get OCR results with bounding box details
    results = reader.readtext(image, detail=1)

    # Filter results based on text size (to focus on headings)
    headings = []
    for bbox, text, confidence in results:
        # Calculate box height
        box_height = abs(bbox[0][1] - bbox[2][1])
        
        # Consider text with large height as heading
        if box_height > 50:  # Adjust threshold as per image resolution
            headings.append(text)

    # Combine extracted headings
    return " ".join(headings)

# Function to extract text from uploaded image using OCR
def extract_text_from_image(image_path):
    # Initialize EasyOCR Reader
    reader = easyocr.Reader(['en'])

    # Load the image using OpenCV
    image = cv2.imread(image_path)

    # Get OCR results with bounding box details
    results = reader.readtext(image, detail=1)

    # Filter results based on text size (to focus on headings)
    headings = []
    for bbox, text, confidence in results:
        # Calculate box height
        box_height = abs(bbox[0][1] - bbox[2][1])
        
        # Consider text with large height as heading
        if box_height > 50:  # Adjust threshold as per image resolution
            headings.append(text)

    # Combine extracted headings
    return " ".join(headings)


def get_recommendations(eco_score):
    recommendations = {
        "A": "Great choice! This product has a top Eco-Score. Consider recommending it to others!",
        "B": "Good choice! To improve sustainability, look for alternatives with an 'A' Eco-Score.",
        "C": "This product is average in sustainability. Explore options with a higher Eco-Score.",
        "D": "Below average Eco-Score. Consider switching to more eco-friendly alternatives.",
        "E": "Poor Eco-Score. It's highly recommended to find a more sustainable product."
    }
    score = eco_score.split()[-1] if eco_score != "Eco-Score not found" else None
    return recommendations.get(score, "Eco-Score not found. Unable to provide recommendations.")


def query_ollama_local(context: str, question: str, mode: str = "shopping", model_name: str = "llama3.2") -> str:
    """Generate a response locally using an Ollama model."""
    prompt_template = QA_USER_PROMPT_TEMPLATE_SHOPPING if mode == "shopping" else QA_USER_PROMPT_TEMPLATE_RECYCLING
    prompt = prompt_template.format(context=context, question=question)
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model_name, "prompt": prompt},
            timeout=30,
            stream=True
        )
        response.raise_for_status()

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

app = Flask(__name__)

@app.route('/get_eco_score', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        #takes 3 input vars from post
        product_name = request.form.get('query', '')
        Mode = request.form.get('mode', '')
        image = request.files.get('image')
        print(f"product name received: {product_name}")
        extracted_text = ""

        if image:
            try:
                img_path = f"temp_{uuid.uuid4()}.jpg"
                image.save(img_path)

                # Extract heading 
                extracted_text = extract_heading(img_path)
                product_name = extracted_text if extracted_text else product_name

                # Clean up temporary file
                #os.remove(img_path)
            except Exception as e:
                logger.error(f"Error processing image: {e}")

        if not product_name:
            return "no product name or valid image provided"

        if product_name:
            eco_score = get_eco_score(product_name)
        
        recommendations = get_recommendations(eco_score)

        
        context = f"Simulated context for {product_name}"
        ollama_response = query_ollama_local(context, product_name, mode=Mode)
        
        response = {
            "product_name": product_name,
            "eco_score": eco_score,
            "recommendations": recommendations,
            "AI_suggestions": ollama_response
        }

        #response = f"Eco-Score for '{product_name}': {eco_score}\n\nRecommendations: {recommendations}\n\nAI Assistant Suggestions: {ollama_response}"
        return jsonify(response)
    return "main"

if __name__ == '__main__':
    app.run(debug=True)