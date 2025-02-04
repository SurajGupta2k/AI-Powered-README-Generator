
from flask import Response
from flask import Flask, render_template, request, jsonify
from flask import render_template
import requests
import json
import os
from datetime import datetime
import google.generativeai as genai

app = Flask(__name__, template_folder='src')

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

def analyze_repo_with_gemini(repo_data, code_samples):
    prompt = f"""Analyze this GitHub repository and generate a comprehensive README.md file. Follow these guidelines:
    
    Repository Metadata:
    {json.dumps(repo_data, indent=2)}
    
    Code Samples:
    {code_samples}
    
    Include these sections:
    1. Project Description
    2. Key Features
    3. Installation Guide
    4. Usage Examples
    5. Technology Stack
    6. Contributing Guidelines
    7. License Information
    
    Use markdown formatting with proper emojis and section headers."""
    
    response = model.generate_content(prompt)
    return response.text

def get_repo_data(repo_url):
    repo_url = repo_url.replace('.git', '')
    parts = [p for p in repo_url.split('/') if p]
    owner, repo = parts[-2], parts[-1]
    
    # Get basic repo info
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_response = requests.get(api_url)
    repo_data = json.loads(repo_response.text)
    
    # Get code samples
    contents_url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    contents_response = requests.get(contents_url)
    contents = json.loads(contents_response.text)
    
    code_samples = []
    for item in contents[:5]:  # Get first 5 files
        if item['type'] == 'file':
            file_response = requests.get(item['download_url'])
            code_samples.append({
                'filename': item['name'],
                'content': file_response.text[:1000]  # First 1000 chars
            })
    
    return repo_data, code_samples

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        repo_url = request.form.get('repo_url')
        repo_data, code_samples = get_repo_data(repo_url)
        
        # Generate README with Gemini
        readme_content = analyze_repo_with_gemini(repo_data, code_samples)
        
        return render_template('preview.html', 
                             readme_content=readme_content,
                             repo_name=repo_data['name'])
    
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    content = request.form.get('readme_content')
    repo_name = request.form.get('repo_name').replace(' ', '_')
    filename = f"{repo_name}_README.md"
    
    return Response(
        content,
        mimetype="text/markdown",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

if __name__ == '__main__':
    app.run(debug=True)