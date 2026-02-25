from pathlib import Path
from setuptools import setup, find_packages

# Minimal setup.py configured for installing this package from a GitHub repo
# and for declaring dependencies that themselves come from GitHub (PEP 508 direct references).

here = Path(__file__).parent
readme = (here / "README.md").read_text(encoding="utf-8") if (here / "README.md").exists() else ""

setup(
    name="activebi-bigdata-hadoop-dataops",
    version="0.1.1",
    description="ActiveBI Hadoop DataOps utilities",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/Engenharia-Arquitetura-Active/activebi-bigdata-hadoop-dataops",
    author="Leonardo Jeronimo",
    packages=find_packages(exclude=("tests",)),
    python_requires=">=3.8",
    install_requires=[
        # normal PyPI dependency
        "requests>=2.25.1",
        "pandas>=2.0",
        "happybase>=1.3.0",
        "SQLAlchemy"
        # dependency installed directly from a GitHub repository (PEP 508 direct URL)
        # Format: <name> @ git+https://github.com/<owner>/<repo>.git@<ref>
        # Examples:
        # "mypkg @ git+https://github.com/owner/mypkg.git@v1.2.3"
        # "otherpkg @ git+https://github.com/owner/otherpkg.git@main"
        # "examplepkg @ git+https://github.com/owner/examplepkg.git@main",
    ],
    include_package_data=True,
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)