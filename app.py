from flask import Response, send_from_directory
from flask import Flask, render_template, request, jsonify, session
from flask import render_template
import requests
import json
import os
from datetime import datetime
import google.generativeai as genai
from functools import wraps
import time

app = Flask(__name__, template_folder='src', static_folder='static')
app.secret_key = os.urandom(24)  # Required for session management

# Verify API key
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")
print(f"API Key verification: {'✓ Key is set' if api_key else '✗ Key is missing'}")
print(f"API Key starts with: {api_key[:12]}...")  # Only show first 12 chars for security

# Configure Gemini
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

# Rate limiting configuration
REQUESTS_PER_MINUTE = 60  # Adjust based on your quota
request_timestamps = []

def rate_limit():
    now = time.time()
    # Remove timestamps older than 1 minute
    while request_timestamps and request_timestamps[0] < now - 60:
        request_timestamps.pop(0)
    if len(request_timestamps) >= REQUESTS_PER_MINUTE:
        return True
    request_timestamps.append(now)
    return False

def analyze_repo_with_gemini(repo_data, code_samples, package_json_content=None):
    # Check rate limit
    if rate_limit():
        raise Exception("Rate limit exceeded. Please try again in a minute.")
        
    try:
        prompt = f"""
You are a highly experienced Technical Writer with over 10 years in the tech industry.  Your primary expertise lies in crafting clear, concise, and engaging README.md files for open-source projects.  You understand the importance of a well-structured README for attracting contributors, guiding users, and showcasing the value of a project.

Your task is to analyze the provided GitHub repository data, code samples, and, if available, the contents of a `package.json` (or similar dependency file) and generate a professional-grade README.md file.  The README should be meticulously formatted in Markdown, incorporating appropriate headers, lists, code blocks, and relevant emojis to enhance readability and visual appeal.

Consider the following information about the repository:

**Repository Metadata:**
{json.dumps(repo_data, indent=2)}

**Code Samples:**
{code_samples}

**Package.json Content (if available):**
{package_json_content if package_json_content else "No package.json content provided."}

**Crucially, ensure the README includes (but is not limited to) the following sections, tailored to the specific project:**

1.  **Project Title:**  A clear and concise title that accurately reflects the project's purpose.  *(Consider adding a small, relevant emoji next to the title, like 🚀 or ✨, if appropriate.)*

2.  **Project Description:**  A compelling introduction to the project.  Clearly state its purpose, what problem it solves, and its key benefits.  Assume the reader has limited prior knowledge. *(You can optionally use a relevant emoji at the beginning of this section, such as 💡 or ℹ️.)*

3.  **Key Features:** A bulleted list highlighting the core functionalities and unique selling points of the project.  Use strong verbs and descriptive language.  *Each bullet point can be preceded by a relevant emoji, such as ✅, 🌟, or ✨, to visually emphasize the feature.* **Choose emojis that accurately represent the feature being described.**

4.  **Installation Guide:**  Step-by-step instructions for setting up the project locally.  Include prerequisites (e.g., specific software versions, dependencies) and commands to execute.  Provide clear instructions for different operating systems if applicable.  *Use icons like ⬇️, ⚙️, or 💻 to represent downloading, configuring, or running the project on different platforms.*  **Consider adding an emoji before each command to indicate its purpose (e.g., ➕ for adding dependencies, ➡️ for running a command).**

5.  **Usage Examples:**  Demonstrate how to use the project with practical, real-world examples.  Include code snippets and explanations of the expected output.  Showcase the most common use cases. *(Consider using an emoji like 🎬 or 🧪 to represent a demonstration or experiment.)*

6.  **Technology Stack:**  List the programming languages, frameworks, libraries, and tools used in the project.  Explain *why* these technologies were chosen when relevant.

    *   **IMPORTANT:**  **If a `package.json` (or similar) content is provided, analyze its dependencies (and devDependencies) to automatically populate this section.**  Extract the names of the primary technologies used.  Use the official logo emoji of each technology if it exists (e.g., for Python, JavaScript if a proper emoji is available, otherwise use generic icons like 🐍 or 📜). Provide short explanation for each technology mentioned.

7.  **Contributing Guidelines:**  Explain how others can contribute to the project (e.g., reporting bugs, submitting pull requests).  Include information on coding style, testing procedures, and the contribution workflow.  Reference a CONTRIBUTING.md file if one exists.  *Use icons like 🤝 or ➕ to represent collaboration and contribution.*

8.  **License Information:** Clearly state the license under which the project is released (e.g., MIT, Apache 2.0, GPL).  Include a link to the full license text. *Use an icon like 📜 or ⚖️ to represent legal information.*

9.  **Project Status:** Include project status like if the project is still in development phase or if the project is stable for production use. *Use an icon like �� or ✅.*

10. **Credits/Acknowledgements:** If the project uses work of others, make sure to credit them. *Use an icon like 🙏 or ➕.*

**Your Responsibilities:**

*   **Be Professional:**  Craft the README as if you were writing it for a public audience.
*   **Be Clear and Concise:**  Avoid jargon and technical terms that may be unfamiliar to newcomers.
*   **Be Comprehensive:**  Provide all the information needed to understand, install, and use the project effectively.
*   **Be Engaging:**  Use Markdown formatting (headings, lists, code blocks, *and carefully chosen emojis*) to make the README visually appealing and easy to read.
*   **Tailor to the Project:**  Don't just generate generic content.  Analyze the provided metadata, code samples, *and package.json content (if provided)* to create a README that is specifically tailored to *this* repository.
*   **Assume No Prior Knowledge:**  Write for a broad audience, including beginners.
*   **Focus on Practicality:** Make sure every section is there, with clear and concise information.
*   **Use Emojis Sparingly and Purposefully:** Do not overuse emojis. Only add emojis when they meaningfully enhance understanding or visual appeal. Avoid using emojis that are irrelevant or distracting.  **The goal is to improve readability, not to create visual clutter.**
*   **Consistency is Key:** Use a consistent style for emojis throughout the README.
*   **Prioritize `package.json` Information:** When `package.json` content is provided, use it as the **primary source** for the technology stack.  Only supplement with information from code samples if necessary.
*   **Be Resourceful:** Find and add short explanation of the technology
*   **Add Versioning:** Show which version is currently in use

Your output should be the complete README.md content, ready to be saved directly to a file.  No introductory or concluding remarks are necessary.
"""

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        if "429" in str(e):  # Rate limit error
            raise Exception("API quota exceeded. Please try again later or upgrade your API plan.")
        raise e

def get_repo_data(repo_url):
    repo_url = repo_url.replace('.git', '')
    parts = [p for p in repo_url.split('/') if p]
    owner, repo = parts[-2], parts[-1]
    
    # Get basic repo info
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {}
    if os.getenv('GITHUB_TOKEN'):
        headers['Authorization'] = f"token {os.getenv('GITHUB_TOKEN')}"
    
    repo_response = requests.get(api_url, headers=headers)
    repo_data = repo_response.json()
    
    # Get code samples
    contents_url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    contents_response = requests.get(contents_url, headers=headers)
    contents = contents_response.json()
    
    code_samples = []
    # Ensure contents is a list and limit to first 5 files
    if isinstance(contents, list):
        file_count = 0
        for item in contents:
            if file_count >= 5:  # Limit to 5 files
                break
            if item['type'] == 'file':
                try:
                    file_response = requests.get(item['download_url'], headers=headers)
                    code_samples.append({
                        'filename': item['name'],
                        'content': file_response.text[:1000]  # First 1000 chars
                    })
                    file_count += 1
                except Exception as e:
                    print(f"Error fetching file {item['name']}: {str(e)}")
                    continue
    
    return repo_data, code_samples

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        repo_url = request.form.get('repo_url')
        repo_data, code_samples = get_repo_data(repo_url)
        
        # Generate README with Gemini
        readme_content = analyze_repo_with_gemini(repo_data, code_samples)
        
        # Store in session
        session['readme_content'] = readme_content
        session['repo_name'] = repo_data['name']
        
        return render_template('preview.html', 
                             readme_content=readme_content,
                             repo_name=repo_data['name'])
    
    # Check if there's stored content in session when accessing via GET
    if 'readme_content' in session and 'repo_name' in session:
        return render_template('preview.html',
                             readme_content=session['readme_content'],
                             repo_name=session['repo_name'])
    
    return render_template('index.html')

@app.route('/clear', methods=['POST'])
def clear_session():
    session.clear()
    return jsonify({'status': 'success'})

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

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True)