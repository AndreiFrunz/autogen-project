import sys
import asyncio
from main_autogen import run_pipeline

def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "Analyze https://example.com and write simple Playwright tests."
    result = asyncio.run(run_pipeline(task))
    print(result)

if __name__ == "__main__":
    main()
