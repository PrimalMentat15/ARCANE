from setuptools import setup, find_packages

setup(
    name="arcane",
    version="0.9.0",
    packages=find_packages(),
    install_requires=[
        "mesa>=3.5.0",
        "solara>=1.40.0",
        "google-generativeai>=0.8.0",
        "httpx>=0.27.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "networkx>=3.0",
    ],
    python_requires=">=3.10",
)
