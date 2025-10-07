For setup this run in terminal:

python -m venv .venv

# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -U "autogen-agentchat" "autogen-ext[openai,azure]" requests beautifulsoup4

pip install playwright
playwright install chromium

export OPENAI_API_KEY="sk-..."     # PowerShell: setx OPENAI_API_KEY "sk-..."