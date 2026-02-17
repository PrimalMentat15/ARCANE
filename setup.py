from setuptools import setup, find_packages

setup(
    name="arcane",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "mesa>=3.0.0",
        "google-genai>=1.0.0",
        "httpx>=0.27.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "networkx>=3.0",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
    ],
    python_requires=">=3.10",
)
