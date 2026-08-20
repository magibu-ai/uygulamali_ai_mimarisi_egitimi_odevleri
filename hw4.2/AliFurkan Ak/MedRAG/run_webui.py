import sys
import os
import uvicorn
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MedRAG.Launcher")

def main():
    print("=" * 75)
    print("  MedRAG Interactive Chatbot Web UI & REST API Server")
    print("=" * 75)
    print("  • Web UI Interface : http://localhost:8000")
    print("  • REST API Endpoint: http://localhost:8000/api/v1/search")
    print("  • API Documentation: http://localhost:8000/docs")
    print("=" * 75)
    
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
