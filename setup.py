from setuptools import setup, find_packages

setup(
    name="savypost",
    version="1.0.0",
    description="SavyPost — Local AI Social Media Manager & Multi-Channel Publisher",
    author="Savio Mohan",
    author_email="saviomohan2002@gmail.com",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "savypost.web": ["templates/*.html"],
    },
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.29.0",
        "sqlalchemy>=2.0.25",
        "httpx>=0.27.0",
        "pydantic>=2.6.0",
        "typer>=0.12.0",
        "rich>=13.7.0",
        "loguru>=0.7.2",
        "python-dotenv>=1.0.1",
        "requests>=2.31.0",
        "yt-dlp>=2024.3.10",
    ],
    entry_points={
        "console_scripts": [
            "savypost=savypost.cli:cli_app",
        ],
    },
    python_requires=">=3.10",
)
